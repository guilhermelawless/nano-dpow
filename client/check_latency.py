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
        block_hash = contents
        print('WORK: {}'.format(block_hash[0:10]+"..."))
        works[block_hash] = perf_counter()
    elif 'result' in msg.topic:
        block_hash, work, account = contents.split(',')
        if block_hash in works:
            print('RESULT: {} after {}ms'.format(block_hash[0:10]+"...", int(1000*(perf_counter() - works[block_hash]))))
        else:
            print('WARN: RESULT: {} received before seen'.format(block_hash[0:10]+"..."))
    elif 'cancel' in msg.topic:
        block_hash = contents
        if block_hash in works:
            print('CANCEL: {} after {}ms'.format(block_hash[0:10]+"...", int(1000*(perf_counter() - works[block_hash]))))
        else:
            print('WARN: CANCEL: {} received before seen'.format(block_hash[0:10]+"..."))
    elif 'heartbeat' in msg.topic:
        print("HEARTBEAT")


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

host = "dangilsystem.zapto.org"

client.connect(host, 1883)

client.subscribe("work/#")
client.subscribe("result/#")
client.subscribe("cancel/#")
client.subscribe("heartbeat")
print("Subscribed")
# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
