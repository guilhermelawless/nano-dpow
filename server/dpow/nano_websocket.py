#!/usr/bin/env python3

import asyncio
import websockets
import json
import logging
import traceback


def subscription(topic: str, ack: bool=False, options: dict=None):
    d = {"action": "subscribe", "topic": topic, "ack": ack}
    if options is not None:
        d["options"] = options
    return d


class WebsocketClient(object):

    def __init__(self, uri, callback, logger=logging):
        self.uri = uri
        self.arrival_cb = callback
        self.logger = logger
        self.ws = None
        self.stop = False

    async def setup(self, silent=False):
        try:
            self.ws = await websockets.connect(self.uri)
            await self.ws.send(json.dumps(subscription("confirmation", ack=True)))
            await self.ws.recv()  # ack
        except Exception as e:
            if not silent:
                self.logger.critical("Error connecting to websocket server. Check your settings in ~/Nano/config.json")
                self.logger.error(traceback.format_exc())
            raise

    async def close(self):
        self.stop = True

    async def reconnect_forever(self):
        self.logger.warn("Attempting websocket reconnection every 30 seconds...")
        while not self.stop:
            try:
                await self.setup(silent=True)
                self.logger.warn("Connected to websocket!")
                break
            except:
                self.logger.debug("Websocket reconnection failed")
                await asyncio.sleep(30)

    async def loop(self):
        while not self.stop:
            try:
                rec = json.loads(await self.ws.recv())
                topic = rec.get("topic", None)
                if topic and topic == "confirmation":
                    await self.arrival_cb(rec["message"])
            except KeyboardInterrupt:
                break
            except websockets.exceptions.ConnectionClosed as e:
                self.logger.error(f"Connection closed to websocket. Code: {e.code} , reason: {e.reason}.")
                await self.reconnect_forever()
            except Exception as e:
                self.logger.critical(f"Unknown exception while handling getting a websocket message:\n{traceback.format_exc()}")
                await self.reconnect_forever()
