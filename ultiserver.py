import asyncio
from aiohttp import web
import aiomqtt
import time
import aioredis
import fourletterphat

#mqtt_client = aiomqtt.Client(client_id="nanotest", clean_session=True, userdata=None,transport="tcp")
#host = "dangilsystem.zapto.org"
host = "localhost"


@asyncio.coroutine
async def send_mqtt(topic, message):
    mqttc = aiomqtt.Client(asyncio.get_event_loop(), "nanotest")
    await mqttc.connect(host, port=1883, keepalive=10)

    mqttc.publish(topic, message)
        
    mqttc.disconnect()

async def redis_insert(key, value):
    loop = asyncio.get_event_loop()
    redis = await aioredis.create_redis('redis://localhost', loop=loop)
    await redis.set(key, value )
    redis.close()
    await redis.wait_closed()

async def redis_delete(key):
    loop = asyncio.get_event_loop()
    redis = await aioredis.create_redis('redis://localhost', loop=loop)
    outcome = await redis.delete(str(key))
    redis.close()
    await redis.wait_closed()
    print("Delete: {} {}".format(outcome, key))

async def redis_getkey(key):
    loop = asyncio.get_event_loop()
    redis = await aioredis.create_redis('redis://localhost', loop=loop)
    val = await redis.get(key)
    redis.close()
    await redis.wait_closed()
    return val.decode("utf-8") 

async def redis_exists(key):
    loop = asyncio.get_event_loop()
    redis = await aioredis.create_redis('redis://localhost', loop=loop)
    exists = await redis.exists(key)
    redis.close()
    await redis.wait_closed()
    return exists

async def handle(request):
    data = await request.json()
    account_exists = await redis_exists(data['account'])
    if account_exists == 1:
        fourletterphat.set_decimal(1,True)

        print("Old account: {}".format(data['account']))
        account_hash = await redis_getkey(data['account'])
        print("Account Hash: {} {}".format(account_hash, data['hash']))
        if account_hash != data['hash']:
            print("New Hash, updating")
            await redis_insert(data['account'], data['hash'] )

            await redis_delete(account_hash)
            print("Deleted")
            await redis_insert(data['hash'] , "0")
            print("New Entry Inserted")
            await send_mqtt("work/precache", data['hash'])
        else:
            print("Duplicate")

        fourletterphat.set_decimal(0,False)

    else:
        fourletterphat.set_decimal(0,True)

        print("New account: {}".format(data['account']))
        await redis_insert(data['account'], data['hash'] )
        await redis_insert(data['hash'], "0")
        print("Inserted")
        await send_mqtt("work/precache", data['hash'])

        fourletterphat.set_decimal(0,False)

    return web.Response(text="test")

def on_connect(client, userdata, flags, rc):
    print("Connected to Rx")
    client.subscribe("work/precache")

fourletterphat.print_str('dPoW')
fourletterphat.show()
app = web.Application()
app.router.add_post('/', handle)

web.run_app(app, port=5030)
