import asyncio
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from work_handler import WorkHandler
import work_server

host = "dangilsystem.zapto.org"
port = 1883
handle_work_server = True

loop = asyncio.get_event_loop()

@asyncio.coroutine
async def dpow_client():

    async def send_work(client, block_hash, work):
        await client.publish(f"result/{block_hash}", str.encode(work, 'utf-8'), qos=QOS_1)

    def handle_message(message):
        print("Message: {}: {}".format(message.topic, message.data.decode("utf-8")))
        try:
            block_hash = message.data.decode("utf-8")
        except:
            print("Could not parse message")
            return

        if len(block_hash) == 64:
            task = loop.create_task(work_handler.queue_work(block_hash, 'ffffffc000000000'))
            asyncio.ensure_future(task, loop=loop)
        else:
            print(f"Invalid hash {block_hash}")

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
            ("work/precache/#", QOS_0)
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
