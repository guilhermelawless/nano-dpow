import asyncio
import aiomqtt
import aiohttp
import aiohttp_requests
import requests
import json

host = "dangilsystem.zapto.org"
port = 1883

loop = asyncio.get_event_loop()

async def dpow_client():
    class WorkHandler(object):
        def __init__(self, worker_uri):
            self.worker_uri = f"http://{worker_uri}"
            try:
                requests.post(self.worker_uri, json={"action": "invalid"}).json()['error']
            except:
                raise Exception("Worker not available at {}".format(self.worker_uri))

        def set_callback(self, cb):
            self.callback = cb

        async def queue_work(self, block_hash: str, difficulty: str):
            async with aiohttp.ClientSession(json_serialize=json.dumps) as session:
                res = await session.post(self.worker_uri, json={
                    "action": "work_generate",
                    "hash": block_hash,
                    "difficulty": difficulty
                })
                res_js = await res.json()
                if 'work' in res_js:
                    await self.callback(block_hash, res_js['work'])


    def on_connect(client, userdata, flags, rc):
        print("Connected")
        client.subscribe("work/precache")

    def on_subscribe(client, userdata, mid, granted_ops):
        print("Subscribed")

    def on_message(client, userdata, message):
        print("Message: {}: {}".format(message.topic, message.payload.decode("utf-8")))
        try:
            block_hash, amount = message.payload.decode("utf-8").split(',')
        except:
            print("Could not parse message")
            return

        if len(block_hash) == 64:
            task = loop.create_task(work_handler.queue_work(block_hash, 'ffffffc000000000'))
            asyncio.ensure_future(task, loop=loop)
        else:
            print(f"Invalid hash {block_hash}")

    async def callback(block_hash, work):
        message_info = client.publish(f"result/{block_hash}", work)
        await message_info.wait_for_publish()

    work_handler = WorkHandler('127.0.0.1:7000')
    work_handler.set_callback(callback)

    client = aiomqtt.Client(loop)
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message

    await client.connect(host, port=port, keepalive=60)
    await client.loop_forever()

try:
    loop.run_until_complete(dpow_client())
finally:
    loop.close()