#!/usr/bin/env python3

import asyncio
import json
import logging
from bpow.redis_db import BpowRedis
from hbmqtt.client import MQTTClient, ClientException, ConnectException
from hbmqtt.mqtt.constants import QOS_0, QOS_1, QOS_2

class BpowMQTT(object):

    def __init__(self, broker: str, loop, message_handle_cb, database, logger=logging):

        self.ok = True
        self.logger = logger
        self.database = database
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
            ("result/#", QOS_0),
            ("get_priority/#", QOS_0),
            ("disconnect/#", QOS_0)
        ])

    async def close(self):
        try:
            self.ok = False
            await self.connection.disconnect()
        except:
            pass
    
    async def client_check(self):
        while 1:
            try:
                client_list = await self.database.set_members('client_list')
                if len(client_list) > 0:
                    for client in client_list:
                        client_actions = await self.database.get(f"client-lastaction:{client}")
                        if client_actions is None:
                            assigned_queues = await self.database.hash_getall(f"client-connections:{client}")
                            self.logger.info("sending callback")
                            await self.callback(f'disconnect/{client}', json.dumps(assigned_queues))
            except Exception as e:
                self.logger.error(f"Exception in client_check: {e}")
            await asyncio.sleep(60)

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
