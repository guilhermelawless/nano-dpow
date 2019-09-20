#!/usr/bin/env python3

import requests
import time
import uuid
from sys import argv, exit

def get_random_request():
    try:
        user = str(argv[1])
        key= str(argv[2])
    except IndexError:
        print("Usage: {} user api_key".format(argv[0]))
        exit(1)
    else:
        hash = (uuid.uuid4().hex + uuid.uuid4().hex).upper()
        # for precache testing uncomment the following line
        # hash = "0000000000000000000000000000000000000000000000000000000000000000"
        request = {"hash" : hash, "user": user, "api_key" : key, "timeout" : 30, "test": 1}
        return request

if __name__ == "__main__":
    json_request = get_random_request()
    print(json_request)
    start_time = time.time()
    r = requests.post('https://bpow.banano.cc/service/', json = json_request)
    complete_time = time.time()
    print(r.text + "\nTook: " + str(complete_time - start_time))
