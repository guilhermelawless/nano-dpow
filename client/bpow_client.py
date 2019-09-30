#!/usr/bin/env python3
from config_parse import BpowClientConfig
config = BpowClientConfig()

from sys import argv
import json
import asyncio
import math
from time import time
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

from logger import get_logger
from work_handler import WorkHandler

loop = asyncio.get_event_loop()
logger = get_logger()


WELCOME = f"""

=======BoomPow (bPow)========

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


class BpowClient(object):

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
        self.priority = {}
        self.running = False
        self.server_online = False

    def handle_work(self, message):
        try:
            topics = message.topic.split('/')
            work_type = topics[1]
            # If the message comes from a numbered queue, check if it's a priority queue or not.
            if len(topics) == 3:
                priority = (self.priority[work_type] == topics[2])
            else:
                priority = False
            content = message.data.decode("utf-8")
            block_hash, difficulty = content.split(',')
        except Exception as e:
            logger.error(f"Could not parse message {message}:\n{e}")
            return

        if len(block_hash) == 64:
            asyncio.ensure_future(self.work_handler.queue_work(work_type, block_hash, difficulty, priority), loop=loop)
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

    def format_stat_message(self, block_rewarded: str, total_work_accepted: int, ondemand: int, precache: int, paid_units: int, paid_amount: float, paid_pending: float):
        paid_amount = math.floor(paid_amount*100)/100
        paid_pending = math.floor(paid_pending*100)/100
        return f"""Block Rewarded: {block_rewarded}
---------------------
BoomPow Stats Update:
---------------------
Overall {total_work_accepted} of your work units have been accepted by BoomPow (ondemand: {ondemand}, precache: {precache})

You have been paid for {paid_units} of those work units and have received {paid_amount} BANANO so far.

So far you've earned {paid_pending} BANANO towards your next reward
---"""
        

    def handle_stats(self, message):
        try:
            stats = json.loads(message.data)
            ondemand = int(stats['ondemand']) if 'ondemand' in stats else 0
            precache = int(stats['precache']) if 'precache' in stats else 0
            total_work = ondemand + precache
            total_credited = int(stats['total_credited']) if 'total_credited' in stats else 0
            total_paid = float(stats['total_paid']) if 'total_paid' in stats else 0.0
            payment_factor = float(stats['payment_factor']) if 'payment_factor' in stats else 0.0
            # Figure out estimated payout
            estimated_payout = (total_work - total_credited) * payment_factor
            logger.info(self.format_stat_message(stats['block_rewarded'], total_work, ondemand, precache, total_credited, total_paid, estimated_payout))
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
        elif "priority_response" == message.topic:
            self.handle_priority(message)

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

        await self.get_priority()

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
            await self.client.subscribe([(f"work/#", QOS_0)])
        else:
            desired_work = config.work_type # precache or ondemand
            await self.client.subscribe([(f"work/{desired_work}/#", QOS_0)])
            
        await self.client.subscribe([
            (f"cancel/{desired_work}", QOS_1),
            (f"client/{config.payout}", QOS_1)
        ])

    async def get_priority(self):
        # subscribe to the topic the server will respond on with the priority queue
        await self.client.subscribe([(f"priority_response/{config.payout}", QOS_0)])
        # send a message to the server to provide you the priority queue
        await self.client.publish(f"get_priority/{config.work_type}", str.encode(f"{config.payout}", 'utf-8'), qos=QOS_0)
        try:
            message = await self.client.deliver_message(timeout=2)
            await self.handle_priority(message)
        except asyncio.TimeoutError:
            logger.error("Timeout while assigning priority for client")

    async def handle_priority(self, message):
        # user receives a topic in the message to prioritize, set that as their priority queue.
        prio = json.loads(message.data)
        if 'ondemand' in prio:
            self.priority['ondemand'] = prio['ondemand']
        if 'precache' in prio:
            self.priority['precache'] = prio['precache']

    async def close(self):
        self.running = False
        await self.client.publish(f"disconnect/{config.payout}", json.dumps(self.priority).encode('utf-8'))
        if self.client:
            await self.client.disconnect()
        if self.work_handler:
            await self.work_handler.stop()

    @asyncio.coroutine
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

    @asyncio.coroutine
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

    @asyncio.coroutine
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
    bpow_client = BpowClient()
    try:
        loop.run_until_complete(bpow_client.run())
        loop.close()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(e)
