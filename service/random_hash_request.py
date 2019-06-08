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
    json_request = {"hash" : hash, "account": "nano_1dpowservicetest", "user": user, "api_key" : key}
    print(json_request)
    r = requests.post('http://127.0.0.1:5030/service/', json = json_request)
    complete_time = time.time()
    print(r.text + "\nTook: " + str(complete_time - start_time))
