#!/usr/bin/env python3

from functools import wraps
import asyncio
from aiohttp import web
import time
import aioredis
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2


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
            loop=loop)

        self.mqttc = MQTTClient(
            loop=loop,
            config={
                "auto_reconnect": True,
                "reconnect_retries": 3,
                "reconnect_max_interval": 10,
                "default_qos": 0
            }
        )
        self.mqtt_connect = self.mqttc.connect("mqtt://localhost:1883", cleansession=True)

    async def wait_init(self):
        self.redis_pool = await self.redis_pool
        await self.mqtt_connect

    async def setup(self):
        await self.mqttc.subscribe([
                ("result/#", QOS_1)
            ])

    async def close(self):
        self.redis_pool.close()
        mqtt_disconect = self.mqttc.disconnect()
        await asyncio.gather((
                self.redis_pool.wait_closed(),
                mqtt_disconnect
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
            block_hash = message.topic.split('result/')[1]
            work = message.data.decode("utf-8")
            print(block_hash, work)
        except:
            print("Could not parse message")
            return
        #TODO work validate, use nanolib?
        #TODO need to send cancel command

    @asyncio.coroutine
    async def mqtt_loop(self):
        try:
            while 1:
                message = await self.mqttc.deliver_message()
                self.handle_message(message)
        except ClientException as e:
            print("Client exception: {}".format(e))

    @asyncio.coroutine
    def send_mqtt(self, topic, message, qos=QOS_0):
        yield from self.mqttc.publish(topic, str.encode(message), qos=qos)

    async def post_handle(self, request):
        data = await request.json()
        account_exists = await self.redis_exists(data['account'])
        if account_exists == 1:
            if display: display.set_decimal(1,True)

            print("Old account: {}".format(data['account']))
            frontier = await self.redis_getkey(data['account'])
            print("Account Frontier: {} {}".format(frontier, data['hash']))
            if frontier != data['hash']:
                print("New Hash, updating")
                await asyncio.gather(
                    self.redis_insert(data['account'], data['hash']),
                    self.redis_delete(frontier),
                    self.redis_insert(data['hash'] , "0")
                )
                print("Deleted")
                print("New Entry Inserted")
                await self.send_mqtt("work/precache", data['hash'])
            else:
                print("Duplicate")

            if display: display.set_decimal(0,False)

        else:
            if display: display.set_decimal(0,True)

            print("New account: {}".format(data['account']))
            await asyncio.gather(
                self.redis_insert(data['account'], data['hash']),
                self.redis_insert(data['hash'], "0"),
                self.send_mqtt("work/precache", data['hash'])
            )
            print("Inserted")

            if display: display.set_decimal(0,False)

        return web.Response(text="test")

server = DpowServer()

async def startup(app):
    init = server.wait_init()
    if display:
        display.print_str('dPoW')
        display.show()
    await init
    await server.setup()
    print("Server created, looping")
    task = loop.create_task(server.mqtt_loop())
    asyncio.ensure_future(task, loop=loop)



async def cleanup(app):
    await server.close()

app = web.Application(loop=loop)
app.router.add_post('/', server.post_handle)
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)

web.run_app(app, port=5030)
