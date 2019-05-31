#!/usr/bin/env python3

# Definitions
#    client - pow calculators, they subscribe to a particular work topic and process the hashes, returning work
#    service - system that uses dpow for calculating pow, access is via POST

import sys
import time
import logging
import asyncio
from aiohttp import web
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2
import nanolib

from redis_db import DpowRedis
from mqtt_client import DpowMQTT

# CONFIG
# host = "dangilsystem.zapto.org"
redis_server = "redis://localhost"
mqtt_broker = "mqtt://localhost:1883"
DEBUG_WORK_ALL_BLOCKS = True


loop = asyncio.get_event_loop()

# Logging
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s@%(funcName)s:%(lineno)s - %(message)s')
logger = logging.getLogger("dpow")
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.WARN)
handler.setFormatter(formatter)
logger.addHandler(handler)

filehandler = logging.FileHandler("log.txt", 'a', 'utf-8')
filehandler.setLevel(logging.DEBUG)
filehandler.setFormatter(formatter)
logger.addHandler(filehandler)


class DpowServer(object):

    def __init__(self):
        self.work_futures = dict()

        self.database = DpowRedis(redis_server, loop)
        self.mqtt = DpowMQTT(mqtt_broker, loop, self.client_cb, logger=logger)

    async def setup(self):
        await asyncio.gather(
            self.database.setup(),
            self.mqtt.setup()
        )

    async def close(self):
        await asyncio.gather(
            self.database.close(),
            self.mqtt.close()
        )

    async def loop(self):
        await asyncio.gather(
            self.mqtt.message_receive_loop(),
            self.mqtt.heartbeat_loop()
        )

    async def client_cb(self, topic, content):
        try:
            work_type = topic.split('/')[-1]
            if work_type not in ('precache', 'ondemand'):
                logger.warn(f"Wrong topic? {topic} -> Extracted work_type {work_type}")
                return
            block_hash, work, account = content.split(',')
            logger.info(f"Message {block_hash} {work} {account}")
        except Exception as e:
            logger.warn(f"Could not parse message: {e}")
            return

        #TODO Check if we needed this work, and handle the case where multiple clients return work at the same time

        try:
            nanolib.validate_work(block_hash, work, threshold=nanolib.work.WORK_THRESHOLD)
        except nanolib.InvalidWork:
            # Invalid work, ignore
            logger.debug("Invalid work")
            return

        # Set Future result if in memory
        if block_hash in self.work_futures:
            resulting_work = self.work_futures[block_hash]
            if not resulting_work.done():
                resulting_work.set_result(work)

        # As we've got work now send cancel command to clients
        # No need to wait on this here
        asyncio.ensure_future(self.mqtt.send(f"cancel/{work_type}", block_hash, qos=QOS_1))

        # Update redis database
        await self.database.insert(block_hash , work)

    async def block_arrival_handle(self, request):
        data = await request.json()
        block_hash, account = data['hash'], data['account']

        account_exists = await self.database.exists(account)

        if account_exists:
            frontier = await self.database.get(account)
            if frontier != block_hash:
                await asyncio.gather(
                    self.database.insert(account, block_hash),
                    self.database.delete(frontier),
                    self.database.insert(block_hash , "0"),
                    self.mqtt.send("work/precache", block_hash)
                )
            else:
                logger.debug(f"Duplicate hash {block_hash}")

        else:
            logger.debug(f"New account: {data['account']}")
            aws = [
                self.database.insert(account, block_hash),
                self.database.insert(block_hash, "0")
            ]
            if DEBUG_WORK_ALL_BLOCKS:
                aws.append(self.mqtt.send("work/precache", block_hash))
            await asyncio.gather(*aws)

        return web.Response(text="test")

    async def request_handle(self, request):
        data = await request.json()
        logger.info(f"Request:\n{data}")
        if 'hash' in data and 'account' in data and 'api_key' in data:
            block_hash, account, api_key = data['hash'], data['account'], data['api_key']

            #TODO secure api key

            #Verify API Key
            service_exists = await self.database.exists(api_key)
            if not service_exists:
                logger.warn(f"Received request with non existing api key {api_key}")
                return web.Response(text="Error, incorrect api key")
            logger.info(f"Request for {block_hash}")

            #Check if hash in redis db, if so return work
            work = await self.database.get(block_hash)
            logger.info(f"Work in cache: {work}")

            #If not in db, request on demand work, return it
            if work is None or work is '0':
                # Insert account into DB if not yet there
                asyncio.ensure_future(self.database.insert_if_noexist(account, block_hash))

                # Create a Future to be set with work when complete
                self.work_futures[block_hash] = loop.create_future()

                # Ask for work on demand
                await self.mqtt.send("work/ondemand", block_hash, qos=QOS_1)

                # Wait on the work for some time
                ON_DEMAND_TIMEOUT = 10
                try:
                    work = await asyncio.wait_for(self.work_futures[block_hash], timeout=ON_DEMAND_TIMEOUT)
                except asyncio.TimeoutError:
                    logger.warn(f"Timeout reached for {block_hash}")
                    return web.json_response({"error" : "Timeout reached without work"})

            # If this is reached, work was obtained
            logger.info(f"Work received: {work}")
            return web.json_response({"work" : work})

            #TODO Log stats
        else:
            return web.Response(text="Error, incorrect submission")

server = DpowServer()

async def startup(app):
    logger.info("Server starting")
    await server.setup()
    asyncio.ensure_future(server.loop(), loop=loop)

async def cleanup(app):
    logger.info("Server shutting down")
    await server.close()

app = web.Application()
app.router.add_post('/', server.block_arrival_handle)
app.router.add_post('/service/', server.request_handle)
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)

web.run_app(app, host="127.0.0.1", port=5030)
