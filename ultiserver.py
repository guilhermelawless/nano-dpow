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


def display_wrapper():
    try:
        import fourletterphat
        obj = fourletterphat
    except ImportError as e:
        print(e)
        obj = None
    except PermissionError as e:
        print(e)
        obj = None
    return obj


# host = "dangilsystem.zapto.org"
display = display_wrapper()
redis_server = "redis://localhost"
loop = asyncio.get_event_loop()

class DpowServer(object):

    def __init__(self):
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
        print("Delete: {} {}".format(outcome, key))

    async def redis_getkey(self, key: str):
        val = await self.redis_pool.execute('get', key)
        return val.decode("utf-8")

    async def redis_exists(self, key: str):
        exists = await self.redis_pool.execute('exists', key)
        return exists

    async def handle_message(self, message):
        print("Message: {}: {}".format(message.topic, message.data.decode("utf-8")))
        try:
            block_hash, work, account = message.data.decode("utf-8").split()
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

        # As we've got work now send cancel command to clients
        # No need to wait on this here
        asyncio.ensure_future(self.send_mqtt("cancel/precache", block_hash, qos=QOS_1))

        #TODO Return work to service

        # Update redis database
        await asyncio.gather(
            self.redis_insert(block_hash , work)
        )


    @asyncio.coroutine
    async def mqtt_loop(self):
        try:
            while 1:
                message = await self.mqttc.deliver_message()
                await self.handle_message(message)

        except ClientException as e:
            print("Client exception: {}".format(e))

    async def send_mqtt(self, topic, message, qos=QOS_0):
        await self.mqttc.publish(topic, str.encode(message), qos=qos)

    async def post_handle(self, request):
        data = await request.json()
        account_exists = await self.redis_exists(data['account'])
        if account_exists == 1:
            if display: display.set_decimal(1,True); display.show()

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

            if display: display.set_decimal(1,False); display.show()

        else:
            if display: display.set_decimal(0,True); display.show()

            print("New account: {}".format(data['account']))
            await asyncio.gather(
                self.redis_insert(data['account'], data['hash']),
                self.redis_insert(data['hash'], "0"),
                self.send_mqtt("work/precache", data['hash'])
            )

            if display: display.set_decimal(0,False); display.show()

        return web.Response(text="test")


server = DpowServer()

async def startup(app):
    if display:
        display.print_str('dPoW')
        display.show()
    await server.setup()
    print("Server created, looping")
    asyncio.ensure_future(server.mqtt_loop(), loop=loop)


async def cleanup(app):
    await server.close()


app = web.Application()
app.router.add_post('/', server.post_handle)
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)

web.run_app(app, port=5030)
