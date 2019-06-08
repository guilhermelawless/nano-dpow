#!/usr/bin/env python3

import asyncio
import websockets
import json


def subscription(topic: str, ack: bool=False, options: dict=None):
    d = {"action": "subscribe", "topic": topic, "ack": ack}
    if options is not None:
        d["options"] = options
    return d


class WebsocketClient(object):

    def __init__(self, uri, callback):
        self.uri = uri
        self.arrival_cb = callback

    async def loop(self):
        try:
            async with websockets.connect(self.uri) as websocket:
                await websocket.send(json.dumps(subscription("confirmation", ack=True)))
                await websocket.recv()  # ack
                while 1:
                    rec = json.loads(await websocket.recv())
                    topic = rec.get("topic", None)
                    if topic and topic == "confirmation":
                        await self.arrival_cb(rec["message"])
        except KeyboardInterrupt:
            pass
        except ConnectionRefusedError:
            print("Error connecting to websocket server. Make sure you have enabled it in ~/Nano/config.json and check "
                  "./sample_client.py --help")





