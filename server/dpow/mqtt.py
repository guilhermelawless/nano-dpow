#!/usr/bin/env python3

import asyncio
import logging
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2


class DpowMQTT(object):

    def __init__(self, broker: str, loop, message_handle_cb, logger=logging):

        self.ok = True
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
            ("result/#", QOS_0)
        ])

    async def close(self):
        try:
            self.ok = False
            await self.connection.disconnect()
        except:
            pass

    async def send(self, topic: str, message: str, qos=QOS_0):
        try:
            await self.connection.publish(topic, str.encode(message), qos=qos)
            if not self.ok:
                self.logger.info("MQTT client is connected again")
                self.ok = True
        except Exception as e:
            self.logger.critical(f"Error while publishing to MQTT: {e}")
            self.ok = False

    @asyncio.coroutine
    async def message_receive_loop(self):
        while 1:
            try:
                message = await self.connection.deliver_message()
                if not self.ok:
                    self.logger.info("MQTT client is connected again")
                    self.ok = True
                topic, content = message.topic, message.data.decode("utf-8")
                await self.callback(topic, content)
            except KeyboardInterrupt:
                return
            except ClientException as e:
                self.ok = False
                self.logger.critical(f"Client exception: {e}")
            except Exception as e:
                self.ok = False
                if not e.args:
                    self.logger.debug("Empty exception, returned silently")
                    return
                self.logger.critical(f"Unknown exception: {e}")

    @asyncio.coroutine
    async def heartbeat_loop(self):
        while 1:
            try:
                if self.ok:
                    await self.send("heartbeat", "", qos=QOS_0)
            except Exception as e:
                self.ok = False
                if not e.args:
                    self.logger.debug("Empty exception, returned silently")
                    return
                self.logger.error(f"Heartbeat failure: {e}")
            finally:
                await asyncio.sleep(1)
