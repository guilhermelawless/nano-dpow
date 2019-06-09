#!/usr/bin/env python3

import requests
import time
import uuid
from sys import argv

try:
    user = str(argv[1])
    key= str(argv[2])
except IndexError:
    print("Usage: {} user api_key".format(argv[0]))
else:
    hash = (uuid.uuid4().hex + uuid.uuid4().hex).upper()
    start_time = time.time()
    json_request = {"hash" : hash, "account": "xrb_1dpowseruicetest111111111111111111111111111111111111ptmcz6f9", "user": user, "api_key" : key, 'timeout': 1}
    print(json_request)
    r = requests.post('http://139.59.134.66:5030/service/', json = json_request)
    complete_time = time.time()
    print(r.text + "\nTook: " + str(complete_time - start_time))
