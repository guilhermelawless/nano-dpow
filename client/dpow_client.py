#!/usr/bin/env python3

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


async def send_work_result(client, work_type, block_hash, work):
    await client.publish(f"result/{work_type}", str.encode(f"{block_hash},{work},{account}", 'utf-8'), qos=QOS_1)


async def work_server_error_callback():
    pass

class DpowClient(object):

    def __init__(self):
        self.client = MQTTClient(
            loop=loop,
            config={
                "auto_reconnect": True,
                "reconnect_retries": 3,
                "reconnect_max_interval": 60,
                "default_qos": 0
            }
        )
        self.work_handler = WorkHandler('127.0.0.1:7000', self.client, send_work_result, work_server_error_callback)
        self.running = False
        self.server_online = False

    def handle_work(self, message):
        try:
            work_type = message.topic.split('/')[-1]
            block_hash = message.data.decode("utf-8")
        except Exception as e:
            print(f"Could not parse message: {e}")
            print(message)
            return

        if len(block_hash) == 64:
            asyncio.ensure_future(self.work_handler.queue_work(work_type, block_hash, 'ffffffc000000000'), loop=loop)
            print(f"Work request for hash {block_hash}")
        else:
            print(f"Invalid hash {block_hash}")

    def handle_cancel(self, message):
        try:
            block_hash = message.data.decode("utf-8")
        except:
            print("Could not parse message")
            return
        if len(block_hash) == 64:
            if self.work_handler.is_queued(block_hash):
                asyncio.ensure_future(self.work_handler.queue_cancel(block_hash), loop=loop)
                print(f"Cancelling hash {block_hash}")
            else:
                print(f"Ignoring cancel for work that we did {block_hash}")
        else:
            print(f"Invalid hash {block_hash}")

    def handle_stats(self, message):
        try:
            print("Stats", json.loads(message.data))
        except Exception as e:
            print(f"Could not parse stats: {e}")
            print(message.data)

    def handle_heartbeat(self, message):
        self.time_last_heartbeat = time()

    def handle_message(self, message):
        # print("Message: {}: {}".format(message.topic, message.data.decode("utf-8")))
        if "cancel" in message.topic:
            self.handle_cancel(message)
        elif "work" in message.topic:
            self.handle_work(message)
        elif "client" in message.topic:
            self.handle_stats(message)
        elif "heartbeat" == message.topic:
            self.handle_heartbeat(message)

    async def setup(self):
        try:
            await self.client.connect(f"mqtt://{host}:{port}", cleansession=True)
        except ConnectException as e:
            print("Connection exception: {}".format(e))
            return False
        self.client.config['reconnect_retries'] = 5000
        # Receive a heartbeat before continuing, this makes sure server is up
        await self.client.subscribe([("heartbeat", QOS_1)])
        try:
            print("Checking for server availability...", end=' ', flush=True)
            await self.client.deliver_message(timeout=2)
            print("Server online!")
            self.time_last_heartbeat = time()
        except asyncio.TimeoutError:
            print("Server is offline :(")
            await self.client.disconnect()
            return False
        self.server_online = True
        await self.client.subscribe([
            ("work/#", QOS_0),
            ("cancel/#", QOS_1),
            (f"client/{account}", QOS_0)
        ])
        await self.work_handler.start()
        self.running = True
        return True

    async def close(self):
        self.running = False
        await self.client.disconnect()
        await self.work_handler.stop()

    @asyncio.coroutine
    async def run(self):
        await self.setup()
        await asyncio.gather(
            self.message_loop(),
            self.heartbeat_check_loop()
        )

    @asyncio.coroutine
    async def heartbeat_check_loop(self):
        while self.running:
            try:
                await asyncio.sleep(10)
                if time () - self.time_last_heartbeat > 10:
                    print(f"Server appears to be offline... {int(time () - self.time_last_heartbeat)} seconds since last heartbeat")
                    self.server_online = False
                elif not self.server_online:
                    print(f"Server is back online")
                    self.server_online = True
            except Exception as e:
                if self.running:
                    print(f"Hearbeat check failure: {e}")

    @asyncio.coroutine
    async def message_loop(self):
        try:
            while self.running:
                message = await self.client.deliver_message()
                self.handle_message(message)
        except ClientException as e:
            print("Client exception: {}".format(e))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(e)
        finally:
            await self.close()


if __name__ == "__main__":
    dpow_client = DpowClient()
    try:
        loop.run_until_complete(dpow_client.run())
        loop.close()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(e)
