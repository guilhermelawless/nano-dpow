import asyncio
import requests
import aiohttp
import aiohttp_requests
import json
from random import shuffle


class WorkQueue(asyncio.Queue):
    """Specialized subclass of asyncio.Queue that retrieves random entries"""

    def _init(self, maxsize):
        self._queue = dict()

    def remove(self, block_hash):
        try:
            self._queue.pop(block_hash)
            return True
        except ValueError:
            return False

    def _put(self, item):
        block_hash, difficulty, work_type = item
        self._queue[block_hash] = (difficulty, work_type)

    def _get(self):
        # Items will be popped as (block_hash, (difficulty, work_type))
        return self._queue.popitem()

    def __contains__(self, block_hash):
        return block_hash in self._queue


class WorkHandler(object):
    def __init__(self, worker_uri, mqtt_client, callback, error_callback):
        self.mqtt_client = mqtt_client
        self.callback = callback
        self.error_callback = error_callback
        self.worker_uri = f"http://{worker_uri}"
        self.work_queue = WorkQueue()
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession(json_serialize=json.dumps, conn_timeout=1)
        try:
            requests.post(self.worker_uri, json={"action": "invalid"}, timeout=2).json()['error']
        except requests.exceptions.RequestException:
            raise Exception("Worker not available at {}".format(self.worker_uri))

    async def stop(self):
        if self.session:
            await self.session.close()

    def is_queued(self, block_hash: str):
        return block_hash in self.work_queue

    async def queue_cancel(self, block_hash: str):
        if self.work_queue.remove(block_hash):
            try:
                await self.session.post(self.worker_uri, json={
                    "action": "work_cancel",
                    "hash": block_hash
                })
            except Exception as e:
                print(f"Work handler queue_cancel error: {e}")


    async def queue_work(self, work_type: str, block_hash: str, difficulty: str):
        try:
            await self.work_queue.put((block_hash, difficulty, work_type))
        except Exception as e:
            print(f"Work handler queue_work error: {e}")
            self.work_queue.remove(item)
            await self.error_callback()

    @asyncio.coroutine
    async def loop(self):
        while 1:
            try:
                block_hash, (difficulty, work_type) = await self.work_queue.get()
                print(f"Working {block_hash}")
                res = await self.session.post(self.worker_uri, json={
                    "action": "work_generate",
                    "hash": block_hash,
                    "difficulty": difficulty
                })
                res_js = await res.json()
                if 'work' in res_js:
                    await self.callback(self.mqtt_client, work_type, block_hash, res_js['work'])
                else:
                    print(res_js['error'])
            except Exception as e:
                print(f"Work handler loop error: {e}")
                await asyncio.sleep(5)

