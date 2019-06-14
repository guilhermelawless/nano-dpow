#!/usr/bin/env python3
from dpow import *
config = DpowConfig() # takes a while to --help if this goes after imports

import sys
import ujson
import datetime
import hashlib
import asyncio
import uvloop
from aiohttp import web
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

import nanolib

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.get_event_loop()
config = DpowConfig()
logger = get_logger()


def hash_key(x: str):
    m = hashlib.blake2b()
    m.update(x.encode("utf-8"))
    return m.digest()


def difficulty_hex(t: int) -> str:
    return hex(t)[2:]


def to_multiplier(difficulty: int, base_difficulty: int = nanolib.work.WORK_THRESHOLD) -> float:
    return float((1 << 64) - base_difficulty) / float((1 << 64) - difficulty)


class DpowServer(object):
    WORK_PENDING = "0"
    BLOCK_EXPIRY = 4*30*24*60*60 # approximately 4 months
    ACCOUNT_EXPIRY = 365*24*60*60 # approximately 1 year
    MAX_DIFFICULTY_MULTIPLIER = 5.0

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
                await self.mqtt.send("statistics", ujson.dumps(stats))
                await asyncio.sleep(300)
        except Exception as e:
            if not e.args:
                logger.debug("Empty exception, returned silently")
                return
            logger.error(f"Statistics update loop failure: {e}")

    async def client_update(self, account: str, work_type: str):
        # Increment work type
        await self.database.hash_increment(f"client:{account}", work_type, by=1)
        # Get all fields for client account
        stats = await self.database.hash_getall(f"client:{account}")
        # Send feedback to client
        await self.mqtt.send(f"client/{account}", ujson.dumps(stats))

    async def client_callback_handle(self, topic, content):
        try:
            # Content is expected as CSV block,work,client
            block_hash, work, client = content.split(',')

            # We expect result/{work_type} as topic
            work_type = topic.split('/')[-1]
            if work_type not in ('precache', 'ondemand'):
                logger.error(f"Unexpected topic {topic} -> Extracted work_type {work_type}")
                return
            # logger.info(f"Message {block_hash} {work} {client}")
        except Exception as e:
            # logger.warn(f"Could not parse message: {e}")
            return

        # Check if work is needed
        # - Block is removed from DB once account frontier that contained it is updated
        # - Block corresponding value is WORK_PENDING if work is pending
        available = await self.database.get(f"block:{block_hash}")
        if not available or available != DpowServer.WORK_PENDING:
            return

        try:
            nanolib.validate_work(block_hash, work, threshold=nanolib.work.WORK_THRESHOLD)
        except nanolib.InvalidWork:
            # logger.debug(f"Client {client} provided invalid work {work} for {block_hash}")
            return

        # Used as a lock - if value already existed, then some other client finished before
        if not await self.database.insert_if_noexist_expire(f"block-lock:{block_hash}", '1', 5):
            return

        # Set Future result if in memory
        try:
            resulting_work = self.work_futures[block_hash]
            if not resulting_work.done():
                resulting_work.set_result(work)
        except KeyError:
            pass
        except Exception as e:
            logger.error(f"Unknown error when setting work future: {e}")

        # Account information and DB update
        await asyncio.gather(
            self.client_update(client, work_type),
            self.database.insert_expire(f"block:{block_hash}", work, DpowServer.BLOCK_EXPIRY)
        )

        # As we've got work now send cancel command to clients and do a stats update
        # No need to wait on this here
        asyncio.ensure_future(asyncio.gather(
            self.mqtt.send(f"cancel/{work_type}", block_hash, qos=QOS_1),
            self.database.increment(f"stats:{work_type}"),
            self.database.set_add(f"clients", client)
        ))

    async def block_arrival_handle(self, block_hash, account, previous):
        should_precache = config.debug
        previous_exists = None
        old_frontier = await self.database.get(f"account:{account}")

        if old_frontier:
            # Account is registered
            if old_frontier == block_hash:
                # Duplicate hash
                return
            else:
                should_precache = True
        elif previous != None:
            # Account is not registered - but maybe the previous block is there
            previous_exists = await self.database.exists(f"block:{previous}")
            if previous_exists:
                should_precache = True

        # Only precache for accounts in the system (or debug mode)
        if should_precache:
            aws = [
                # Account frontier update
                self.database.insert_expire(f"account:{account}", block_hash, DpowServer.ACCOUNT_EXPIRY),
                # Incomplete work for new frontier
                self.database.insert_expire(f"block:{block_hash}", DpowServer.WORK_PENDING, DpowServer.BLOCK_EXPIRY),
                # Send for precache
                self.mqtt.send("work/precache", f"{block_hash},{difficulty_hex(nanolib.work.WORK_THRESHOLD)}", qos=QOS_0)
            ]
            if old_frontier:
                # Work for old frontier no longer needed
                aws.append(self.database.delete(f"block:{old_frontier}"))
            elif previous_exists:
                aws.append(self.database.delete(f"block:{previous}"))
            await asyncio.gather (*aws)

    async def block_arrival_websocket_handle(self, data):
        try:
            # previous might not exist - open block
            block_hash, account, previous = data['hash'], data['account'], data['block'].get('previous', None)
            await self.block_arrival_handle(block_hash, account, previous)
        except Exception as e:
            logger.error(f"Unable to process block: {e}\nData:\n{data}")

    async def block_arrival_callback_handle(self, request):
        try:
            data = await request.json(loads=ujson.loads)
            # previous might not exist - open block
            block_hash, account, previous = data['hash'], data['account'], ujson.loads(data['block']).get('previous', None)
            await self.block_arrival_handle(block_hash, account, previous)
        except Exception as e:
            logger.error(f"Unable to process block: {e}\nData:\n{data}")
        return web.Response()

    async def request_handle(self, request):
        try:
            try:
                data = await request.json(loads=ujson.loads)
                if type(data) != dict:
                    raise
            except:
                return web.json_response({"error": "Bad request (not json)"}, dumps=ujson.dumps)

            # logger.info(f"Request:\n{data}")
            if {'hash', 'user', 'api_key'} <= data.keys():
                service, api_key = data['user'], data['api_key']
                api_key = hash_key(api_key)

                #Verify API Key
                db_key = await self.database.hash_get(f"service:{service}", "api_key")
                if db_key is None:
                    logger.info(f"Received request with non existing service {service}")
                    return web.json_response({"error" : "User does not exist"}, dumps=ujson.dumps)
                elif not api_key == db_key:
                    logger.info(f"Received request with non existing api key {api_key} for service {service}")
                    return web.json_response({"error" : "Incorrect api key"}, dumps=ujson.dumps)

                block_hash = data['hash']
                account = data.get('account', None)
                difficulty = data.get('difficulty', None)

                try:
                    block_hash = nanolib.validate_block_hash(block_hash)
                    if account:
                        account = account.replace("xrb_", "nano_")
                        nanolib.validate_account_id(account)
                    if difficulty:
                        difficulty = int('0x'+difficulty, 16)
                        nanolib.validate_threshold(difficulty)

                except nanolib.InvalidBlockHash:
                    return web.json_response({"error" : "Invalid hash"}, dumps=ujson.dumps)
                except nanolib.InvalidAccount:
                    return web.json_response({"error" : "Invalid account"}, dumps=ujson.dumps)
                except ValueError:
                    return web.json_response({"error" : "Invalid difficulty"}, dumps=ujson.dumps)
                except nanolib.InvalidThreshold:
                    return web.json_response({"error" : "Difficulty too low"}, dumps=ujson.dumps)

                if difficulty and to_multiplier(difficulty) > DpowServer.MAX_DIFFICULTY_MULTIPLIER:
                    return web.json_response({"error" : "Difficulty too high"}, dumps=ujson.dumps)


                #Check if hash in redis db, if so return work
                work = await self.database.get(f"block:{block_hash}")

                if work is None:
                    # Set incomplete work
                    await self.database.insert_expire(f"block:{block_hash}", DpowServer.WORK_PENDING, DpowServer.BLOCK_EXPIRY)

                work_type = "precache"

                # TODO also check if precached difficulty is close enough to the requested difficulty (Dynamic PoW)
                if work is None or work == DpowServer.WORK_PENDING:
                    #Request on demand work
                    work_type = "ondemand"

                    # If account is not provided, service runs a risk of the next work not being precached for
                    # There is still the possibility we recognize the need to precache based on the previous block
                    if account:
                        # Update account frontier
                        asyncio.ensure_future(self.database.insert_expire(f"account:{account}", block_hash, DpowServer.ACCOUNT_EXPIRY))

                    # Create a Future to be set with work when complete
                    self.work_futures[block_hash] = loop.create_future()

                    # Base difficulty if not provided
                    difficulty = difficulty_hex(difficulty or nanolib.work.WORK_THRESHOLD)

                    # Ask for work on demand
                    await self.mqtt.send(f"work/ondemand", f"{block_hash},{difficulty}", qos=QOS_0)

                    # Wait on the work for some time
                    timeout = max(int(data.get('timeout', 5)), 1)
                    try:
                        work = await asyncio.wait_for(self.work_futures[block_hash], timeout=timeout)
                    except asyncio.TimeoutError:
                        logger.warn(f"Timeout of {timeout} reached for {block_hash}")
                        return web.json_response({"error" : "Timeout reached without work"}, dumps=ujson.dumps)
                    finally:
                        try:
                            future = self.work_futures.pop(block_hash)
                            future.cancel()
                        except:
                            pass
                    # logger.info(f"Work received: {work}")
                else:
                    # logger.info(f"Work in cache: {work}")
                    pass

                # Increase the work type counter for this service
                asyncio.ensure_future(self.database.hash_increment(f"service:{service}", work_type))

                # If this is reached, work was obtained
                return web.json_response({"work" : work}, dumps=ujson.dumps)
            else:
                return web.json_response({"error" : "Incorrect submission. Required information: user, api_key, hash, account"}, dumps=ujson.dumps)
        except Exception as e:
            logger.critical(f"Unknown exception: {e}")
            return web.json_response({"error" : f"Unknown error, please report the following timestamp to the maintainers: {datetime.datetime.now()}"}, dumps=ujson.dumps)


def main():
    server = DpowServer()

    async def startup(app):
        logger.info("Server starting")
        if config.debug:
            logger.warn("Debug mode is on")
        try:
            await server.setup()
            asyncio.ensure_future(server.loop(), loop=loop)
        except Exception as e:
            logger.critical(e)
            sys.exit(1)

    async def cleanup(app):
        logger.info("Server shutting down")
        await server.close()

    # use websockets or callback from the node
    app_blocks = None
    if not config.use_websocket:
        app_blocks = web.Application()
        app_blocks.router.add_post('/block/', server.block_arrival_callback_handle)
        handler_blocks = app_blocks.make_handler()
        coroutine_blocks = loop.create_server(handler_blocks, config.web_host, config.blocks_port)
        server_blocks = loop.run_until_complete(coroutine_blocks)

    # endpoint for service requests
    app_requests = web.Application()
    app_requests.on_startup.append(startup)
    app_requests.on_cleanup.append(cleanup)
    app_requests.router.add_post('/service/', server.request_handle)
    try:
        if config.web_path:
            web.run_app(app_requests, host=config.web_host, port=config.requests_port, path=config.web_path)
        else:
            web.run_app(app_requests, host=config.web_host, port=config.requests_port)
    except KeyboardInterrupt:
        pass
    finally:
        if app_blocks:
            server_blocks.close()
            loop.run_until_complete(handler_blocks.shutdown(60.0))

    loop.close()

if __name__ == "__main__":
    main()
