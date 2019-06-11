#!/usr/bin/env python3

import asyncio
import logging
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

class DpowMQTT(object):

    def __init__(self, broker: str, loop, message_handle_cb, logger=logging):

        self.logger = logger
        self.connection = MQTTClient(
            loop=loop,
            config={
                "auto_reconnect": True,
                "reconnect_retries": 1000,
                "reconnect_max_interval": 10,
                "default_qos": 0
            }
        )
        self.connect_wait = self.connection.connect(broker, cleansession=False)
        self.callback = message_handle_cb

    async def setup(self):
        await self.connect_wait
        await self.subscribe()

    async def subscribe(self):
        await self.connection.subscribe([
            ("result/#", QOS_1)
        ])

    async def close(self):
        await self.connection.disconnect()

    async def send(self, topic: str, message: str, qos=QOS_0):
        await self.connection.publish(topic, str.encode(message), qos=qos)

    @asyncio.coroutine
    async def message_receive_loop(self):
        error_count = 0
        while 1:
            try:
                message = await self.connection.deliver_message()
                topic, content = message.topic, message.data.decode("utf-8")
                await self.callback(topic, content)
            except KeyboardInterrupt:
                return
            except ClientException as e:
                error_count += 1
                self.logger.critical(f"Client exception: {e}")
                raise
            except Exception as e:
                if not e.args:
                    self.logger.debug("Empty exception, returned silently")
                    return
                error_count += 1
                self.logger.critical(f"Unknown exception: {e}")
                raise
            finally:
                if error_count > 5:
                    return

    @asyncio.coroutine
    async def heartbeat_loop(self):
        while 1:
            try:
                await self.send("heartbeat", "", qos=QOS_1)
            except Exception as e:
                if not e.args:
                    self.logger.debug("Empty exception, returned silently")
                    return
                self.logger.error(f"Hearbeat failure: {e}")
            finally:
                await asyncio.sleep(1)