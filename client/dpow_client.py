#!/usr/bin/env python3
from config_parse import DpowClientConfig
config = DpowClientConfig()

import os
from sys import argv
import json
import asyncio
from time import time
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from logger import get_logger
from work_handler import WorkHandler

log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

loop = asyncio.get_event_loop()
logger = get_logger(log_dir)


WELCOME = f"""

=====Nano Community DPoW=====

- Payouts to {config.payout}
- Doing {config.work_type} work
- Server at {config.server}
- Work server at {config.worker}

=============================

"""


async def send_work_result(client, work_type, block_hash, work):
    await client.publish(f"result/{work_type}", str.encode(f"{block_hash},{work},{config.payout}", 'utf-8'), qos=QOS_0)


async def work_server_error_callback():
    pass


class DpowClient(object):

    def __init__(self):
        self.client = MQTTClient(
            loop=loop,
            config={
                "auto_reconnect": True,
                "reconnect_retries": 5000,
                "reconnect_max_interval": 120,
                "keep_alive": 60,
                "default_qos": 0
            }
        )
        self.work_handler = WorkHandler(config.worker, self.client, send_work_result, work_server_error_callback, logger=logger)
        self.running = False
        self.server_online = False

    def handle_work(self, message):
        try:
            work_type = message.topic.split('/')[-1]
            content = message.data.decode("utf-8")
            block_hash, difficulty = content.split(',')
        except Exception as e:
            logger.error(f"Could not parse message {message}:\n{e}")
            return

        if len(block_hash) == 64:
            asyncio.ensure_future(self.work_handler.queue_work(work_type, block_hash, difficulty), loop=loop)
        else:
            logger.warn(f"Invalid hash {block_hash}")

    def handle_cancel(self, message):
        try:
            block_hash = message.data.decode("utf-8")
        except:
            logger.error(f"Could not parse message {message}")
            return
        if len(block_hash) == 64:
            asyncio.ensure_future(self.work_handler.queue_cancel(block_hash), loop=loop)
        else:
            logger.warn(f"Invalid hash {block_hash}")

    def handle_stats(self, message):
        try:
            logger.info(f"STATS {json.loads(message.data)}")
        except Exception as e:
            logger.warn(f"Could not parse stats message {message}:\n{e}")

    def handle_heartbeat(self, message):
        self.time_last_heartbeat = time()

    def handle_message(self, message):
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
            await self.client.connect(config.server, cleansession=False)
        except ConnectException as e:
            logger.critical("Connection exception: {}".format(e))
            return False

        # Receive a heartbeat before continuing, this makes sure server is up
        await self.client.subscribe([("heartbeat", QOS_0)])
        try:
            logger.info("Checking for server availability...")
            await self.client.deliver_message(timeout=2)
            logger.info("Server online!")
            self.time_last_heartbeat = time()
        except asyncio.TimeoutError:
            logger.critical("Server is offline :(")
            return False
        self.server_online = True

        # Subscribe to all necessary topics
        await self.subscribe()

        try:
            await self.work_handler.start()
        except Exception as e:
            logger.critical(e)
            return False
        self.running = True
        return True

    async def subscribe(self):
        if config.work_type == "any":
            desired_work = "#"
        else:
            desired_work = config.work_type # precache or ondemand

        await self.client.subscribe([
            (f"work/{desired_work}", QOS_0),
            (f"cancel/{desired_work}", QOS_1),
            (f"client/{config.payout}", QOS_1)
        ])

    async def close(self):
        self.running = False
        if self.client:
            await self.client.disconnect()
        if self.work_handler:
            await self.work_handler.stop()

    async def run(self):
        logger.info(WELCOME)
        if not await self.setup():
            return await self.close()
        logger.info("Setup successful, waiting for work")
        await asyncio.gather(
            self.message_loop(),
            self.heartbeat_check_loop(),
            self.work_handler.loop()
        )

    async def heartbeat_check_loop(self):
        while self.running:
            try:
                await asyncio.sleep(10)
                if time () - self.time_last_heartbeat > 10:
                    logger.warn(f"Server appears to be offline... {int(time () - self.time_last_heartbeat)} seconds since last heartbeat")
                    self.server_online = False
                elif not self.server_online:
                    logger.info(f"Server is back online")
                    self.server_online = True
            except Exception as e:
                if self.running:
                    logger.error(f"Heartbeat check failure: {e}")

    async def message_loop(self):
        while self.running:
            try:
                message = await self.client.deliver_message()
                self.handle_message(message)
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                logger.critical(f"Unknown exception: {e}")
                logger.info(f"Sleeping a bit before retrying")
                await asyncio.sleep(20)
                try:
                    await self.client.reconnect(cleansession=False)
                    logger.info("Successfully reconnected")
                except ConnectException as e:
                    logger.error(f"Connection exception: {e}")
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
