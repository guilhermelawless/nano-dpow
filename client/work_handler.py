import asyncio
import requests
import aiohttp
import json
import logging
from random import choice


class WorkQueue(asyncio.Queue):
    """Specialized subclass of asyncio.Queue that retrieves random entries"""

    def pop(self, block_hash) -> (str, str):
        return self._queue.pop(block_hash)

    def try_remove(self, block_hash) -> bool:
        try:
            self.pop(block_hash)
        except KeyError:
            return False
        return True

    def _init(self, maxsize):
        self._queue = dict()

    def _put(self, item):
        block_hash, difficulty, work_type = item
        self._queue[block_hash] = (difficulty, work_type)

    def _get(self):
        # python3 has ordered dicts, simple popitem() would not be random
        block_hash, _ = choice(list(self._queue.items()))
        difficulty, work_type = self._queue.pop(block_hash)
        return block_hash, (difficulty, work_type)

    def __contains__(self, block_hash):
        return block_hash in self._queue


class WorkHandler(object):
    def __init__(self, worker_uri, mqtt_client, callback, error_callback, logger=logging):
        self.mqtt_client = mqtt_client
        self.callback = callback
        self.error_callback = error_callback
        self.worker_uri = f"http://{worker_uri}"
        self.work_queue = WorkQueue()
        self.work_ongoing = set()
        self.session = None
        self.logger = logger

    async def start(self):
        self.session = aiohttp.ClientSession(json_serialize=json.dumps, conn_timeout=1)
        try:
            requests.post(self.worker_uri, json={"action": "invalid"}, timeout=2).json()['error']
        except requests.exceptions.RequestException:
            raise Exception("Worker not available at {}".format(self.worker_uri))

    async def stop(self):
        if self.session:
            await self.session.close()

    async def queue_cancel(self, block_hash: str):
        # If it's queued up work, simply remove it
        try:
            difficulty, work_type = self.work_queue.pop(block_hash)
            self.logger.info(f"REMOVED {work_type}/{block_hash[:10]}")
            return
        except KeyError:
            pass

        # Can also be work that is currently being done
        if block_hash in self.work_ongoing:
            # Remove so that loop() does not send it when complete
            try:
                self.work_ongoing.remove(block_hash)
                await self.session.post(self.worker_uri, json={
                    "action": "work_cancel",
                    "hash": block_hash
                })
            except Exception as e:
                self.logger.error(f"Work handler queue_cancel error: {e}")


    async def queue_work(self, work_type: str, block_hash: str, difficulty: str):
        if block_hash in self.work_queue:
            self.logger.debug(f"IGNORED {work_type}/{block_hash[:10]} (in queue)")
            return
        if block_hash in self.work_ongoing:
            self.logger.debug(f"IGNORED {work_type}/{block_hash[:10]} (ongoing)")
            return
        try:
            await self.work_queue.put((block_hash, difficulty, work_type))
            self.logger.info(f"QUEUED {work_type}/{block_hash[:10]}")
        except Exception as e:
            self.logger.error(f"Work handler queue_work error: {e}")
            self.work_queue.try_remove(item)
            await self.error_callback()

    @asyncio.coroutine
    async def loop(self):
        while 1:
            try:
                block_hash, (difficulty, work_type) = await self.work_queue.get()
                self.logger.info(f"WORK {work_type}/{block_hash[:10]}...")
                self.work_ongoing.add(block_hash)
                res = await self.session.post(self.worker_uri, json={
                    "action": "work_generate",
                    "hash": block_hash,
                    "difficulty": difficulty
                })
                try:
                    self.work_ongoing.remove(block_hash)
                except:
                    # Removed by queue_cancel, no longer needed
                    self.logger.info(f"CANCEL {work_type}/{block_hash[:10]}...")
                    continue
                res_js = await res.json()
                if 'work' in res_js:                    
                    await self.callback(self.mqtt_client, work_type, block_hash, res_js['work'])
                    self.logger.info(f"SENT {work_type}/{block_hash[:10]}")
                else:
                    error = res_js.get('error', None)
                    if error:
                        self.logger.error(f"Unexpected reply from work server: {error}")
            except Exception as e:
                self.logger.error(f"Work handler loop error: {e}")
                await asyncio.sleep(5)
