import paho.mqtt.client as mqtt
import json
from time import perf_counter

host = "bpow.banano.cc"
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
        block_hash, difficulty = contents.split(',')
        print('WORK: {}'.format(block_hash))
        works[block_hash] = perf_counter()
    elif 'result' in msg.topic:
        block_hash, work, account = contents.split(',')
        if block_hash in works:
            print('RESULT: {} work {}... after {}ms'.format(block_hash[0:10]+"...", work, int(1000*(perf_counter() - works[block_hash]))))
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
    elif 'statistics' in msg.topic:
        print("Statistics update:\n\n{}".format(contents))


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.username_pw_set('client', password='client')
client.connect(host, 8883)

client.subscribe("work/#")
client.subscribe("result/#")
client.subscribe("cancel/#")
client.subscribe("statistics")
#client.subscribe("heartbeat")
print("Subscribed")
client.loop_forever()
