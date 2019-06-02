from sys import argv
import json
import asyncio
from time import time
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from work_handler import WorkHandler

host = "localhost"
#host = "dangilsystem.zapto.org"
port = 1883
account = "nano_1dpowtestdpowtest11111111111111111111111111111111111icw1jiw5"

loop = asyncio.get_event_loop()

time_last_heartbeat = time()

@asyncio.coroutine
async def heartbeat_loop():
    while 1:
        try:
            await asyncio.sleep(10)
            if time () - time_last_heartbeat > 10:
                print(f"Server appears to be offline... {int(time () - time_last_heartbeat)} seconds since last message")
        except Exception as e:
            print(f"Hearbeat check failure: {e}")

@asyncio.coroutine
async def dpow_client():

    work_handler_ok = True

    async def send_work_result(client, work_type, block_hash, work):
        await client.publish(f"result/{work_type}", str.encode(f"{block_hash},{work},{account}", 'utf-8'), qos=QOS_1)

    async def work_server_error_callback():
        pass

    def handle_work(message):
        try:
            work_type = message.topic.split('/')[-1]
            block_hash = message.data.decode("utf-8")
        except Exception as e:
            print(f"Could not parse message: {e}")
            print(message)
            return

        if len(block_hash) == 64:
            asyncio.ensure_future(work_handler.queue_work(work_type, block_hash, 'ffffffc000000000'), loop=loop)
            print(f"Work request for hash {block_hash}")
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
                print(f"Cancelling hash {block_hash}")
            else:
                print(f"Ignoring cancel for work that we did {block_hash}")
        else:
            print(f"Invalid hash {block_hash}")

    def handle_stats(message):
        try:
            print("Stats", json.loads(message.data))
        except Exception as e:
            print(f"Could not parse stats: {e}")
            print(message.data)

    def handle_heartbeat(message):
        time_last_heartbeat = time()

    def handle_message(message):
        # print("Message: {}: {}".format(message.topic, message.data.decode("utf-8")))
        if "cancel" in message.topic:
            handle_cancel(message)
        elif "work" in message.topic:
            handle_work(message)
        elif "client" in message.topic:
            handle_stats(message)
        elif "heartbeat" == message.topic:
            handle_heartbeat(message)


    client = MQTTClient(
        loop=loop,
        config={
            "auto_reconnect": True,
            "reconnect_retries": 3,
            "reconnect_max_interval": 60,
            "default_qos": 0
        }
    )

    try:
        await client.connect(f"mqtt://{host}:{port}", cleansession=True)
    except ConnectException as e:
        print("Connection exception: {}".format(e))
        return
    client.config['reconnect_retries'] = 5000

    # Receive a heartbeat before continuing, this makes sure server is up
    await client.subscribe([("heartbeat", QOS_1)])
    try:
        print("Checking for server availability...", end=' ', flush=True)
        await client.deliver_message(timeout=2)
        print("Server online!")
        time_last_heartbeat = time()
    except asyncio.TimeoutError:
        print("Server is offline :(")
        await client.disconnect()
        return

    await client.subscribe([
        ("work/#", QOS_0),
        ("cancel/#", QOS_1),
        (f"client/{account}", QOS_0)
    ])

    # Main
    try:
        work_handler = WorkHandler('127.0.0.1:7000', client, send_work_result, work_server_error_callback)
        await work_handler.start()
        while work_handler_ok:
            message = await client.deliver_message()
            handle_message(message)

    except ClientException as e:
        print("Client exception: {}".format(e))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(e)
    finally:
        await client.disconnect()
        await work_handler.stop()

try:
    loop.run_until_complete(asyncio.gather(dpow_client(), heartbeat_loop()))
    loop.close()
except KeyboardInterrupt:
    pass
except Exception as e:
    print(e)
