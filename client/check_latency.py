import paho.mqtt.client as mqtt
import json
from time import perf_counter

works = dict()

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, rc):
    print("Connected with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("$SYS/#")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    contents = msg.payload.decode("utf-8")
    if 'work' in msg.topic:
        block_hash = msg.payload.decode("utf-8")
        print('Hash seen: {}'.format(block_hash))
        works[block_hash] = perf_counter()
    elif 'result' in msg.topic:
        block_hash = msg.topic.split('result/')[1]
        if block_hash in works:
            work = msg.payload.decode("utf-8")
            print('Work seen for hash {} after {}ms'.format(block_hash, int(1000*(perf_counter() - works[block_hash]))))
        else:
            print('Result for {} received before seen'.format(block_hash))


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

host = "dangilsystem.zapto.org"

client.connect(host, 1883)

client.subscribe("work/precache")
client.subscribe("result/#")
print("Subscribed")
# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
