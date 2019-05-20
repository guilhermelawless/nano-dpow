import requests
import aiohttp
import aiohttp_requests
import json


class WorkHandler(object):
    def __init__(self, worker_uri, mqtt_client, callback):
        self.mqtt_client = mqtt_client
        self.callback = callback
        self.worker_uri = f"http://{worker_uri}"
        self.work_queue = set()
        try:
            requests.post(self.worker_uri, json={"action": "invalid"}).json()['error']
        except requests.exceptions.RequestException:
            raise Exception("Worker not available at {}".format(self.worker_uri))

    def is_queued(self, block_hash: str):
        return block_hash in self.work_queue

    async def queue_cancel(self, block_hash: str):
        async with aiohttp.ClientSession(json_serialize=json.dumps) as session:
            # Remove before cancelling as this means someone has completed this work already
            self.work_queue.remove(block_hash)
            await session.post(self.worker_uri, json={
                "action": "work_cancel",
                "hash": block_hash
            })

    async def queue_work(self, block_hash: str, difficulty: str):
        async with aiohttp.ClientSession(json_serialize=json.dumps) as session:
            self.work_queue.add(block_hash)
            res = await session.post(self.worker_uri, json={
                "action": "work_generate",
                "hash": block_hash,
                "difficulty": difficulty
            })
            # Unless it was cancelled in the meantime
            if block_hash in self.work_queue:
                res_js = await res.json()
                if 'work' in res_js:
                    await self.callback(self.mqtt_client, block_hash, res_js['work'])