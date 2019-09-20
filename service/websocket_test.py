#!/usr/bin/env python3

import asyncio
import websockets
import json
from time import time
from sys import argv
from random_hash_request import get_random_request

async def main():
    async with websockets.connect(f"wss://bpow.banano.cc/service_ws/") as websocket:

        for i in range(int(argv[3])):
            request = get_random_request()
            print(request)
            start_time = time()
            await websocket.send(json.dumps(request))
            rec = await websocket.recv()
            complete_time = time()
            print(rec + "\nTook: " + str(complete_time - start_time))

try:
    if len(argv) < 4:
        print(f"Usage: {argv[0]} user api_key number_of_requests")
    else:
        asyncio.get_event_loop().run_until_complete(main())
except KeyboardInterrupt:
    pass
except ConnectionRefusedError:
    print("Error connecting to server")
