import requests
import aiohttp
import aiohttp_requests
import json


class WorkHandler(object):
    def __init__(self, worker_uri, mqtt_client, callback):
        self.mqtt_client = mqtt_client
        self.callback = callback
        self.worker_uri = f"http://{worker_uri}"
        try:
            requests.post(self.worker_uri, json={"action": "invalid"}).json()['error']
        except requests.exceptions.RequestException:
            raise Exception("Worker not available at {}".format(self.worker_uri))

    async def queue_work(self, block_hash: str, difficulty: str):
        async with aiohttp.ClientSession(json_serialize=json.dumps) as session:
            res = await session.post(self.worker_uri, json={
                "action": "work_generate",
                "hash": block_hash,
                "difficulty": difficulty
            })
            res_js = await res.json()
            if 'work' in res_js:
                await self.callback(self.mqtt_client, block_hash, res_js['work'])