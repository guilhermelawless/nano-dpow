#!/usr/bin/env python3
from dpow import *
config = DpowConfig() # takes a while to --help if this goes after imports

import traceback
import sys
import ujson
import datetime
import hashlib
import asyncio
import uvloop
import nanolib
from collections import defaultdict
from asyncio_throttle import Throttler
from aiohttp import web, WSMsgType
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.get_event_loop()
config = DpowConfig()
logger = get_logger()


def hash_key(x: str):
    m = hashlib.blake2b()
    m.update(x.encode("utf-8"))
    return m.digest()


class DpowServer(object):
    WORK_PENDING = "0"
    BLOCK_EXPIRY = 4*30*24*60*60 # approximately 4 months
    ACCOUNT_EXPIRY = 365*24*60*60 # approximately 1 year
    DIFFICULTY_EXPIRY = 2*60
    MAX_DIFFICULTY_MULTIPLIER = 5.0
    FORCE_ONDEMAND_THRESHOLD = 0.8 # <= 1
    MAX_SERVICE_REQUESTS_PER_SECOND = 10

    def __init__(self):
        self.work_futures = dict()
        self.service_throttlers = defaultdict(lambda: Throttler(rate_limit=DpowServer.MAX_SERVICE_REQUESTS_PER_SECOND*10, period=10))
        self.database = DpowRedis("redis://localhost", loop)
        self.mqtt = DpowMQTT(config.mqtt_uri, loop, self.client_handler, logger=logger)
        if config.use_websocket:
            self.websocket = WebsocketClient(config.websocket_uri, self.block_arrival_ws_handler, logger=logger)
        else:
            self.websocket = None

    async def setup(self):
        await asyncio.gather(
            self.database.setup(),
            self.mqtt.setup(),
        )
        if self.websocket:
            await self.websocket.setup()

    async def close(self):
        await asyncio.gather(
            self.database.close(),
            self.mqtt.close()
        )
        if self.websocket:
            await self.websocket.close()

    async def loop(self):
        aws = [
            self.mqtt.message_receive_loop(),
            self.mqtt.heartbeat_loop(),
            self.statistics_loop()
        ]
        if self.websocket:
            aws.append(self.websocket.loop())
        await asyncio.gather(*aws)

    @asyncio.coroutine
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

    async def client_update(self, account: str, work_type: str, block_rewarded: str):
        # Increment work type
        await self.database.hash_increment(f"client:{account}", work_type, by=1)
        # Get all fields for client account
        stats = await self.database.hash_getall(f"client:{account}")
        # Convert fields to integer
        stats = {k: int(v) for k,v in stats.items()}
        # Add the block hash that got rewarded
        stats['block_rewarded'] = block_rewarded
        # Send feedback to client
        await self.mqtt.send(f"client/{account}", ujson.dumps(stats))

    async def client_handler(self, topic, content):
        try:
            # Content is expected as CSV block,work,client
            block_hash, work, client = content.split(',')

            # We expect result/{work_type} as topic
            work_type = topic.split('/')[-1]
            if work_type not in ('precache', 'ondemand'):
                logger.error(f"Unexpected topic {topic} -> Extracted work_type {work_type}")
                return
            # logger.info(f"Message {block_hash} {work} {client}")
        except Exception:
            # logger.warn(f"Could not parse message: {e}")
            return

        # Check if work is needed
        # - Block is removed from DB once account frontier that contained it is updated
        # - Block corresponding value is WORK_PENDING if work is pending
        available = await self.database.get(f"block:{block_hash}")
        if not available or available != DpowServer.WORK_PENDING:
            return

        difficulty = await self.database.get(f"block-difficulty:{block_hash}")

        try:
            nanolib.validate_work(block_hash, work, difficulty = difficulty or nanolib.work.WORK_DIFFICULTY)
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

        # As we've got work now send cancel command to clients and do a stats update
        await self.mqtt.send(f"cancel/{work_type}", block_hash, qos=QOS_1)

        # Account information and DB update
        await asyncio.gather(
            self.client_update(client, work_type, block_hash),
            self.database.insert_expire(f"block:{block_hash}", work, DpowServer.BLOCK_EXPIRY),
            self.database.increment(f"stats:{work_type}"),
            self.database.set_add(f"clients", client)
        )

    async def block_arrival_handler(self, block_hash, account, previous):
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
                self.mqtt.send("work/precache", f"{block_hash},{nanolib.work.WORK_DIFFICULTY}", qos=QOS_0)
            ]
            if old_frontier:
                # Work for old frontier no longer needed
                aws.append(self.database.delete(f"block:{old_frontier}"))
            elif previous_exists:
                aws.append(self.database.delete(f"block:{previous}"))
            await asyncio.gather (*aws)

    async def block_arrival_ws_handler(self, data):
        try:
            # previous might not exist - open block
            block_hash, account, previous = data['hash'], data['account'], data['block'].get('previous', None)
            await self.block_arrival_handler(block_hash, account, previous)
        except Exception as e:
            logger.error(f"Unable to process block: {e}\nData:\n{data}")

    @asyncio.coroutine
    async def block_arrival_cb_handler(self, request):
        try:
            data = await request.json(loads=ujson.loads)
            # previous might not exist - open block
            block_hash, account, previous = data['hash'], data['account'], ujson.loads(data['block']).get('previous', None)
            await self.block_arrival_handler(block_hash, account, previous)
        except Exception as e:
            logger.error(f"Unable to process block: {e}\nData:\n{data}")
        return web.Response()

    async def service_handler(self, data):
        if not {'hash', 'user', 'api_key'} <= data.keys():
            raise InvalidRequest("Incorrect submission. Required information: user, api_key, hash")

        service, api_key = data['user'], data['api_key']
        api_key = hash_key(api_key)

        #Verify API Key
        db_key = await self.database.hash_get(f"service:{service}", "api_key")
        if db_key is None:
            logger.info(f"Received request with non existing service {service}")
            raise InvalidRequest("Invalid credentials")
        elif not api_key == db_key:
            logger.info(f"Received request with non existing api key {api_key} for service {service}")
            raise InvalidRequest("Invalid credentials")

        async with self.service_throttlers[service]:
            block_hash = data['hash']
            account = data.get('account', None)
            difficulty = data.get('difficulty', None)

            try:
                block_hash =    nanolib.validate_block_hash(block_hash)
                if account:
                    account = account.replace("xrb_", "nano_")
                    nanolib.validate_account_id(account)
                if difficulty:
                    nanolib.validate_difficulty(difficulty)
            except nanolib.InvalidBlockHash:
                raise InvalidRequest("Invalid hash")
            except nanolib.InvalidAccount:
                raise InvalidRequest("Invalid account")
            except ValueError:
                raise InvalidRequest("Invalid difficulty")
            except nanolib.InvalidDifficulty:
                raise InvalidRequest("Difficulty too low")

            if difficulty:
                difficulty_multiplier = nanolib.work.derive_work_multiplier(difficulty)
                if difficulty_multiplier > DpowServer.MAX_DIFFICULTY_MULTIPLIER:
                    raise InvalidRequest(f"Difficulty too high. Maximum: {nanolib.work.derive_work_difficulty(DpowServer.MAX_DIFFICULTY_MULTIPLIER)} ( {DpowServer.MAX_DIFFICULTY_MULTIPLIER} multiplier )")

            #Check if hash in redis db, if so return work
            work = await self.database.get(f"block:{block_hash}")

            if work is None:
                # Set incomplete work
                await self.database.insert_expire(f"block:{block_hash}", DpowServer.WORK_PENDING, DpowServer.BLOCK_EXPIRY)

            work_type = "ondemand"
            if work and work != DpowServer.WORK_PENDING:
                work_type = "precache"
                if difficulty:
                    precached_multiplier = nanolib.work.derive_work_multiplier(hex(nanolib.work.get_work_value(block_hash, work))[2:])
                    if precached_multiplier < DpowServer.FORCE_ONDEMAND_THRESHOLD * difficulty_multiplier:
                        # Force ondemand since the precache difficulty is not close enough to requested difficulty
                        work_type = "ondemand"
                        await self.database.insert(f"block:{block_hash}", DpowServer.WORK_PENDING)
                        logger.warn(f"Forcing ondemand: precached {precached_multiplier} vs requested {difficulty_multiplier}")

            if work_type == "ondemand":
                # If account is not provided, service runs a risk of the next work not being precached for
                # There is still the possibility we recognize the need to precache based on the previous block
                if account:
                    # Update account frontier
                    asyncio.ensure_future(self.database.insert_expire(f"account:{account}", block_hash, DpowServer.ACCOUNT_EXPIRY))

                # Create a Future to be set with work when complete
                self.work_futures[block_hash] = loop.create_future()

                # Set difficulty in DB if provided
                if difficulty:
                    await self.database.insert_expire(f"block-difficulty:{block_hash}", difficulty, DpowServer.DIFFICULTY_EXPIRY)

                # Base difficulty if not provided
                difficulty = difficulty or nanolib.work.WORK_DIFFICULTY

                # Ask for work on demand
                await self.mqtt.send(f"work/ondemand", f"{block_hash},{difficulty}", qos=QOS_0)

                timeout = data.get('timeout', 5)
                try:
                    timeout = int(timeout)
                    if timeout < 1 or timeout > 30:
                        raise
                except:
                    raise InvalidRequest("Timeout must be an integer between 1 and 30")

                try:
                    work = await asyncio.wait_for(self.work_futures[block_hash], timeout=timeout)
                except asyncio.TimeoutError:
                    logger.warn(f"Timeout of {timeout} reached for {block_hash}")
                    raise RequestTimeout()
                finally:
                    try:
                        future = self.work_futures.pop(block_hash)
                        future.cancel()
                    except Exception:
                        pass
                # logger.info(f"Work received: {work}")
            else:
                # logger.info(f"Work in cache: {work}")
                pass

            # Increase the work type counter for this service
            asyncio.ensure_future(self.database.hash_increment(f"service:{service}", work_type))

            response = {'work': work}
            if 'id' in data:
                response['id'] = data['id']

        return response

    @asyncio.coroutine
    async def service_ws_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = ujson.loads(msg.data)
                        if type(data) != dict:
                            raise InvalidRequest("Bad request (not json)")
                        response = await self.service_handler(data)
                    except InvalidRequest as e:
                        response = dict(error=e.reason)
                    except RequestTimeout:
                        response = dict(error="Timeout reached without work", timeout=True)
                    except Exception as e:
                        response = dict(error=f"Unknown error, please report the following timestamp to the maintainers: {datetime.datetime.now()}")
                        logger.critical(traceback.format_exc())
                    finally:
                        await ws.send_json(response)
                elif msg.type == WSMsgType.ERROR:
                    # logger.error(f"ws connection closed with exception {ws.exception()}")
                    pass
        except Exception:
            pass

        # logger.info('websocket connection closed')
        return ws

    @asyncio.coroutine
    async def service_post_handler(self, request):
        try:
            data = await request.json(loads=ujson.loads)
            if type(data) != dict:
                raise InvalidRequest("Bad request (not json)")
            response = await self.service_handler(data)
        except InvalidRequest as e:
            response = dict(error=e.reason)
        except RequestTimeout:
            response = dict(error="Timeout reached without work", timeout=True)
        except Exception as e:
            response = dict(error=f"Unknown error, please report the following timestamp to the maintainers: {datetime.datetime.now()}")
            logger.critical(traceback.format_exc())
        finally:
            return web.json_response(response, dumps=ujson.dumps)


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
            await server.close()
            sys.exit(1)

    async def cleanup(app):
        logger.info("Server shutting down")
        await server.close()

    # use websockets or callback from the node
    app_blocks = None
    if not config.use_websocket:
        app_blocks = web.Application()
        app_blocks.router.add_post('/block/', server.block_arrival_cb_handler)
        handler_blocks = app_blocks.make_handler()
        coroutine_blocks = loop.create_server(handler_blocks, "0.0.0.0", 5040)
        server_blocks = loop.run_until_complete(coroutine_blocks)

    # endpoint for a permanent connection to services via websockets
    app_ws = web.Application()
    app_ws.router.add_get('/service_ws/', server.service_ws_handler)
    handler_ws = app_ws.make_handler()
    coroutine_ws = loop.create_server(handler_ws, "0.0.0.0", 5035)
    server_ws = loop.run_until_complete(coroutine_ws)

    # endpoint for checking if server is up
    app_upcheck = web.Application()
    upcheck_handler = lambda request: web.Response(text="up")
    app_upcheck.router.add_get('/upcheck/', upcheck_handler)
    handler_upcheck = app_upcheck.make_handler()
    coroutine_upcheck = loop.create_server(handler_upcheck, "0.0.0.0", 5031)
    server_upcheck = loop.run_until_complete(coroutine_upcheck)


    # endpoint for service requests
    app_services = web.Application()
    app_services.on_startup.append(startup)
    app_services.on_cleanup.append(cleanup)
    app_services.router.add_post('/service/', server.service_post_handler)
    try:
        if config.web_path:
            web.run_app(app_services, host="0.0.0.0", port=5030, path=config.web_path)
        else:
            web.run_app(app_services, host="0.0.0.0", port=5030)
    except KeyboardInterrupt:
        loop.stop()
    finally:
        if not loop.is_closed():
            if app_blocks:
                server_blocks.close()
                loop.run_until_complete(handler_blocks.shutdown(5.0))
            server_ws.close()
            loop.run_until_complete(handler_ws.shutdown(5.0))
            server_upcheck.close()
            loop.run_until_complete(handler_upcheck.shutdown(5.0))
            remaining_tasks = asyncio.Task.all_tasks()
            loop.run_until_complete(asyncio.wait_for(asyncio.gather(*remaining_tasks), timeout=10))
            loop.close()

if __name__ == "__main__":
    main()
