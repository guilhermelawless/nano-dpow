#!/usr/bin/env python3

# Definitions
#    client - pow calculators, they subscribe to a particular work topic and process the hashes, returning work
#    service - system that uses dpow for calculating pow, access is via POST

from functools import wraps
import asyncio
from aiohttp import web
import time
import aioredis
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
import nanolib

# host = "dangilsystem.zapto.org"
redis_server = "redis://localhost"
loop = asyncio.get_event_loop()

class DpowServer(object):

    def __init__(self):
        self.work_futures = dict()

        self.redis_pool = aioredis.create_pool(
            redis_server,
            minsize=5, maxsize=15,
            loop=loop
        )

        self.mqttc = MQTTClient(
            loop=loop,
            config={
                "auto_reconnect": True,
                "reconnect_retries": 3,
                "reconnect_max_interval": 10,
                "default_qos": 0
            }
        )
        self.mqttc_connect = self.mqttc.connect("mqtt://localhost:1883", cleansession=True)

    async def setup(self):
        self.redis_pool = await self.redis_pool
        await self.mqttc_connect
        await self.mqttc.subscribe([
            ("result/#", QOS_1)
        ])

    async def close(self):
        self.redis_pool.close()
        await asyncio.gather((
            self.redis_pool.wait_closed(),
            self.mqttc.disconnect()
        ))

    async def redis_insert(self, key: str, value: str):
        await self.redis_pool.execute('set', key, value )

    async def redis_delete(self, key: str):
        outcome = await self.redis_pool.execute('del', key)
        print(f"Delete: {outcome} {key}")

    async def redis_getkey(self, key: str):
        val = await self.redis_pool.execute('get', key)
        if val == None:
            return None
        else:
            return val.decode("utf-8")

    async def redis_exists(self, key: str):
        exists = await self.redis_pool.execute('exists', key)
        return exists == 1

    @asyncio.coroutine
    async def heartbeat_loop(self):
        try:
            while 1:
                await self.send_mqtt("heartbeat", "", qos=QOS_1)
                await asyncio.sleep(1)
        except:
            print("Hearbeat failure")
            pass

    @asyncio.coroutine
    async def mqtt_loop(self):
        try:
            while 1:
                message = await self.mqttc.deliver_message()
                await self.mqtt_message_handle(message)

        except ClientException as e:
            print(f"Client exception: {e}")

    async def send_mqtt(self, topic, message, qos=QOS_0):
        await self.mqttc.publish(topic, str.encode(message), qos=qos)

    @asyncio.coroutine
    async def check_and_insert(self, account, block_hash):
        account_exists = await self.redis_exists(account)
        if not account_exists:
            await self.redis_insert(account, block_hash)

    async def mqtt_message_handle(self, message):
        contents = message.data.decode("utf-8")
        print(f"Message: {message.topic}: {contents}")
        work_type = message.topic.split('/')[-1]
        if work_type not in ('precache', 'ondemand'):
            print(f"Wrong topic? {message.topic} -> Extracted work_type {work_type}")
            return

        try:
            block_hash, work, account = contents.split(',')
            print(block_hash, work, account)
        except:
            print("Could not parse message")
            return

        #TODO Check if we needed this work, and handle the case where multiple clients return work at the same time

        try:
            nanolib.validate_work(block_hash, work, threshold=nanolib.work.WORK_THRESHOLD)
        except nanolib.InvalidWork:
            # Invalid work, ignore
            print("Invalid work")
            return

        # Set Future result if in memory
        if block_hash in self.work_futures:
            resulting_work = self.work_futures[block_hash]
            if not resulting_work.done():
                resulting_work.set_result(work)

        # As we've got work now send cancel command to clients
        # No need to wait on this here
        asyncio.ensure_future(self.send_mqtt(f"cancel/{work_type}", block_hash, qos=QOS_1))

        # Update redis database
        await asyncio.gather(
            self.redis_insert(block_hash , work)
        )

    async def block_arrival_handle(self, request):
        data = await request.json()
        account_exists = await self.redis_exists(data['account'])

        if account_exists:
            frontier = await self.redis_getkey(data['account'])
            if frontier != data['hash']:
                print("New Hash, updating")
                await asyncio.gather(
                    self.redis_insert(data['account'], data['hash']),
                    self.redis_delete(frontier),
                    self.redis_insert(data['hash'] , "0"),
                    self.send_mqtt("work/precache", data['hash'])
                )
            else:
                print("Duplicate")

        else:
            print(f"New account: {data['account']}")
            await asyncio.gather(
                self.redis_insert(data['account'], data['hash']),
                self.redis_insert(data['hash'], "0"),
                self.send_mqtt("work/precache", data['hash'])
            )

        return web.Response(text="test")

    async def request_handle(self, request):
        data = await request.json()
        print(data)
        if 'hash' in data and 'account' in data and 'api_key' in data:
            block_hash, account, api_key = data['hash'], data['account'], data['api_key']

            #Verify API Key
            service_exists = await self.redis_exists(api_key)
            if not service_exists:
                return web.Response(text="Error, incorrect api key")
            print("Found key")
            #Check if hash in redis db, if so return work
            work = await self.redis_getkey(block_hash)
            print(f"Work: {work}")

            #If not in db, request on demand work, return it
            if work is None or work is '0':
                # Insert account into DB if not yet there
                asyncio.ensure_future(self.check_and_insert(account, block_hash))

                # Create a Future to be set with work when complete
                self.work_futures[block_hash] = loop.create_future()

                # Ask for work on demand
                await self.send_mqtt("work/ondemand", block_hash, qos=QOS_1)
                print("On Demand - waiting for work...")

                # Wait on the work for some time
                ON_DEMAND_TIMEOUT = 10
                try:
                    work = await asyncio.wait_for(self.work_futures[block_hash], timeout=ON_DEMAND_TIMEOUT)
                except asyncio.TimeoutError:
                    print(f"Timeout reached for {block_hash}")
                    return web.json_response({"error" : "Timeout reached without work"})

            # If this is reached, work was obtained
            print(f"Work received: {work}")
            return web.json_response({"work" : work})

            #TODO Log stats
        else:
            return web.Response(text="Error, incorrect submission")

server = DpowServer()

async def startup(app):
    await server.setup()
    print("Server created, looping")
    asyncio.ensure_future(server.heartbeat_loop(), loop=loop)
    asyncio.ensure_future(server.mqtt_loop(), loop=loop)


async def cleanup(app):
    await server.close()


app = web.Application()
app.router.add_post('/', server.block_arrival_handle)
app.router.add_post('/service/', server.request_handle)
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)

web.run_app(app, port=5030)
