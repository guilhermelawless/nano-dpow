#!/usr/bin/env python3
from config_parse import DpowConfig
config = DpowConfig() # takes a while to --help if this goes after imports

import json
import hashlib
import asyncio
from aiohttp import web
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

import nanolib
from redis_db import DpowRedis
from mqtt_client import DpowMQTT
from websocket_client import WebsocketClient
import dpow_logger


loop = asyncio.get_event_loop()
config = DpowConfig()
logger = dpow_logger.get_logger()


def hash_key(x: str):
    m = hashlib.blake2b()
    m.update(x.encode("utf-8"))
    return m.digest()


def difficulty_hex(t: int):
    return hex(t)[2:]


class DpowServer(object):
    WORK_PENDING = "0"

    def __init__(self):
        self.work_futures = dict()
        self.database = DpowRedis(config.redis_uri, loop)
        self.mqtt = DpowMQTT(config.mqtt_uri, loop, self.client_callback_handle, logger=logger)
        if config.use_websocket:
            self.websocket = WebsocketClient(config.websocket_uri, self.block_arrival_websocket_handle)
        else:
            self.websocket = None

    async def setup(self):
        await asyncio.gather(
            self.database.setup(),
            self.mqtt.setup(),
        )

    async def close(self):
        await asyncio.gather(
            self.database.close(),
            self.mqtt.close()
        )

    async def loop(self):
        aws = [
            self.mqtt.message_receive_loop(),
            self.mqtt.heartbeat_loop(),
            self.statistics_loop()
        ]
        if self.websocket:
            aws.append(self.websocket.loop())
        await asyncio.gather(*aws)

    async def statistics_loop(self):
        try:
            while 1:
                stats = await self.database.all_statistics()
                await self.mqtt.send("statistics", json.dumps(stats))
                await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"Statistics update loop failure: {e}")

    async def client_update(self, account: str, work_type: str):
        # Increment work type
        await self.database.hash_increment(f"client:{account}", work_type, by=1)
        # Get all fields for client account
        stats = await self.database.hash_getall(f"client:{account}")
        # Send feedback to client
        await self.mqtt.send(f"client/{account}", json.dumps(stats))

    async def client_callback_handle(self, topic, content):
        try:
            # We expect result/{work_type} as topic
            work_type = topic.split('/')[-1]
            if work_type not in ('precache', 'ondemand'):
                logger.warn(f"Wrong topic? {topic} -> Extracted work_type {work_type}")
                return
            # Content is expected as CSV block,work,client
            block_hash, work, client = content.split(',')
            # logger.info(f"Message {block_hash} {work} {client}")
        except Exception as e:
            logger.warn(f"Could not parse message: {e}")
            return

        # Check if work is needed
        # - Block is removed from DB once account frontier that contained it is updated
        # - Block corresponding value is WORK_PENDING if work is pending
        available = await self.database.get(f"block:{block_hash}")
        if not available:
            logger.debug(f"Client {client} provided work for a removed or non-existing hash {block_hash}")
            return
        elif available != DpowServer.WORK_PENDING:
            logger.debug(f"Client {client} provided work for hash {block_hash} with existing work {available}")
            return

        try:
            nanolib.validate_work(block_hash, work, threshold=nanolib.work.WORK_THRESHOLD)
        except nanolib.InvalidWork:
            # Invalid work, ignore
            logger.debug(f"Client {client} provided invalid work {work} for {block_hash}")
            return

        # Set Future result if in memory
        if block_hash in self.work_futures:
            resulting_work = self.work_futures[block_hash]
            if not resulting_work.done():
                resulting_work.set_result(work)

        # Account information and DB update
        await asyncio.gather(
            self.client_update(client, work_type),
            self.database.insert(f"block:{block_hash}", work)
        )

        # As we've got work now send cancel command to clients and do a stats update
        # No need to wait on this here
        asyncio.ensure_future(asyncio.gather(
            self.mqtt.send(f"cancel/{work_type}", block_hash, qos=QOS_1),
            self.database.increment(f"stats:{work_type}"),
            self.database.set_add(f"clients", client)
        ))

    async def block_arrival_handle(self, block_hash, account):
        account_exists = await self.database.exists(f"account:{account}")

        if account_exists:
            frontier = await self.database.get(f"account:{account}")
            if frontier != block_hash:
                await asyncio.gather(
                    # Account frontier
                    self.database.insert(f"account:{account}", block_hash),
                    # Work for old frontier no longer needed
                    self.database.delete(f"block:{frontier}"),
                    # Set incomplete work for new frontier
                    self.database.insert(f"block:{block_hash}" , DpowServer.WORK_PENDING),
                )
                await self.mqtt.send("work/precache", f"{block_hash},{difficulty_hex(nanolib.work.WORK_THRESHOLD)}")
            else:
                logger.debug(f"Duplicate hash {block_hash}")

        else:
            # logger.debug(f"New account: {account}")
            aws = [
                # Account frontier
                self.database.insert(f"account:{account}", block_hash),
                # Set incomplete work for new frontier
                self.database.insert(f"block:{block_hash}", DpowServer.WORK_PENDING)
            ]
            if config.debug:
                aws.append(self.mqtt.send("work/precache", f"{block_hash},{difficulty_hex(nanolib.work.WORK_THRESHOLD)}"))
            await asyncio.gather(*aws)

    async def block_arrival_websocket_handle(self, data):
        block_hash, account = data['hash'], data['account']
        await self.block_arrival_handle(block_hash, account)

    async def block_arrival_callback_handle(self, request):
        peername = request.transport.get_extra_info('peername')
        if peername is not None:
            host, port = peername
            if host == config.callback_remote_ip:
                data = await request.json()
                block_hash, account = data['hash'], data['account']
                await self.block_arrival_handle(block_hash, account)
        return web.Response()

    async def request_handle(self, request):
        data = await request.json()
        # logger.info(f"Request:\n{data}")
        if {'hash', 'account', 'user', 'api_key'} <= data.keys():
            service, api_key = data['user'], data['api_key']
            api_key = hash_key(api_key)

            #Verify API Key
            db_key = await self.database.hash_get(f"service:{service}", "api_key")
            if db_key is None:
                logger.info(f"Received request with non existing service {service}")
                return web.json_response({"error" : "User does not exist"})
            elif not api_key == db_key:
                logger.info(f"Received request with non existing api key {api_key} for service {service}")
                return web.json_response({"error" : "Incorrect api key"})

            block_hash, account = data['hash'], data['account'].replace("xrb_", "nano_")

            try:
                block_hash = nanolib.validate_block_hash(block_hash)
                nanolib.validate_account_id(account)
            except nanolib.InvalidBlockHash:
                return web.json_response({"error" : "Invalid hash"})
            except nanolib.InvalidAccount:
                return web.json_response({"error" : "Invalid account"})


            #Check if hash in redis db, if so return work
            work = await self.database.get(f"block:{block_hash}")

            if work is None:
                await asyncio.gather(
                    # Account frontier
                    self.database.insert(f"account:{account}", block_hash),
                    # Set incomplete work for new frontier
                    self.database.insert(f"block:{block_hash}" , DpowServer.WORK_PENDING),
                )

            work_type = "precache"
            #Request on demand work, return it
            if work is None or work == DpowServer.WORK_PENDING:
                work_type = "ondemand"
                # Insert account into DB if not yet there
                asyncio.ensure_future(self.database.insert_if_noexist(f"account:{account}", block_hash))

                # Create a Future to be set with work when complete
                self.work_futures[block_hash] = loop.create_future()

                # TODO dynamic difficulty
                difficulty = difficulty_hex(nanolib.work.WORK_THRESHOLD)

                # Ask for work on demand
                await self.mqtt.send(f"work/ondemand", f"{block_hash},{difficulty}", qos=QOS_1)

                # Wait on the work for some time
                timeout = max(int(data.get('timeout', 5)), 1)
                try:
                    work = await asyncio.wait_for(self.work_futures[block_hash], timeout=timeout)
                except asyncio.TimeoutError:
                    logger.warn(f"Timeout reached for {block_hash}")
                    return web.json_response({"error" : "Timeout reached without work"})
                # logger.info(f"Work received: {work}")
            else:
                # logger.info(f"Work in cache: {work}")
                pass

            # Increase the work type counter for this service
            asyncio.ensure_future(self.database.hash_increment(f"service:{service}", work_type))

            # If this is reached, work was obtained
            return web.json_response({"work" : work})
        else:
            return web.json_response({"error" : "Incorrect submission. Required information: user, api_key, hash, account"})


def main():
    server = DpowServer()

    async def startup(app):
        logger.info("Server starting")
        await server.setup()
        asyncio.ensure_future(server.loop(), loop=loop)

    async def cleanup(app):
        logger.info("Server shutting down")
        await server.close()

    app = web.Application()
    if not config.use_websocket:
        app.router.add_post('/', server.block_arrival_callback_handle)
    app.router.add_post('/service/', server.request_handle)
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)

    web.run_app(app, host=config.web_host, port=config.web_port)


if __name__ == "__main__":
    main()
