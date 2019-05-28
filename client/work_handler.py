import requests
import aiohttp
import aiohttp_requests
import json


class WorkHandler(object):
    def __init__(self, worker_uri, mqtt_client, callback, error_callback):
        self.mqtt_client = mqtt_client
        self.callback = callback
        self.error_callback = error_callback
        self.worker_uri = f"http://{worker_uri}"
        self.work_queue = set()
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession(json_serialize=json.dumps, conn_timeout=1)
        try:
            requests.post(self.worker_uri, json={"action": "invalid"}, timeout=2).json()['error']
        except requests.exceptions.RequestException:
            raise Exception("Worker not available at {}".format(self.worker_uri))

    async def stop(self):
        await self.session.close()

    def is_queued(self, block_hash: str):
        return block_hash in self.work_queue

    async def queue_cancel(self, block_hash: str):
        # Remove before cancelling as this means someone has completed this work already
        self.work_queue.remove(block_hash)
        await self.session.post(self.worker_uri, json={
            "action": "work_cancel",
            "hash": block_hash
        })

    async def queue_work(self, block_hash: str, difficulty: str):
        try:
            self.work_queue.add(block_hash)
            res = await self.session.post(self.worker_uri, json={
                "action": "work_generate",
                "hash": block_hash,
                "difficulty": difficulty
            })
            # Unless it was cancelled in the meantime
            if block_hash in self.work_queue:
                self.work_queue.remove(block_hash)
                res_js = await res.json()
                if 'work' in res_js:
                    await self.callback(self.mqtt_client, block_hash, res_js['work'])
                else:
                    print(res_js['error'])
        except Exception as e:
            print(f"Work handler error: {e}")
            if block_hash in self.work_queue:
                self.work_queue.remove(block_hash)
            await self.error_callback()
