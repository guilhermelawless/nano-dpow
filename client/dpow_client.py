import asyncio
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from work_handler import WorkHandler
import work_server

host = "dangilsystem.zapto.org"
port = 1883
handle_work_server = False

loop = asyncio.get_event_loop()

@asyncio.coroutine
async def dpow_client():

    async def send_work(client, block_hash, work):
        await client.publish(f"result/{block_hash}", str.encode(work, 'utf-8'), qos=QOS_1)

    def handle_work(message):
        try:
            block_hash = message.data.decode("utf-8")
        except:
            print("Could not parse message")
            return

        if len(block_hash) == 64:
            asyncio.ensure_future(work_handler.queue_work(block_hash, 'ffffffc000000000'), loop=loop)
        else:
            print(f"Invalid hash {block_hash}")

    def handle_cancel(message):
        try:
            block_hash = message.data.decode("utf-8")
        except:
            print("Could not parse message")
            return
        if len(block_hash) == 64:
            if work_handler.is_queued(block_hash):
                asyncio.ensure_future(work_handler.queue_cancel(block_hash), loop=loop)
        else:
            print(f"Invalid hash {block_hash}")

    def handle_message(message):
        print("Message: {}: {}".format(message.topic, message.data.decode("utf-8")))
        if "cancel" in message.topic:
            handle_cancel(message)
        elif "work" in message.topic:
            handle_work(message)


    client = MQTTClient(
            loop=loop,
            config={
                "auto_reconnect": True,
                "reconnect_retries": 3,
                "reconnect_max_interval": 60,
                "default_qos": 0
            }
        )

    if handle_work_server:
        work_server.create()

    try:
        work_handler = WorkHandler('127.0.0.1:7000', client, send_work)
    except Exception as e:
        print(e)
        return

    try:
        await client.connect(f"mqtt://{host}:{port}", cleansession=True)
    except ConnectException as e:
        print("Connection exception: {}".format(e))
        return
    client.config['reconnect_retries'] = 5000

    await client.subscribe([
            ("work/precache/#", QOS_0),
            ("cancel/#", QOS_1)
        ])

    try:
        while 1:
            message = await client.deliver_message()
            handle_message(message)
    except ClientException as e:
        print("Client exception: {}".format(e))
    except KeyboardInterrupt:
        pass
    finally:
        await client.unsubscribe("work/precache/#")
        await client.disconnect()

try:
    loop.run_until_complete(dpow_client())
    loop.close()
except:
    pass
finally:
    if handle_work_server:
        work_server.destroy()
