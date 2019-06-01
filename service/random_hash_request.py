import requests
import time
import uuid
from sys import argv

hash = (uuid.uuid4().hex + uuid.uuid4().hex).upper()
user = str(argv[1])
key= str(argv[2])

start_time = time.time()
json_request = {"hash" : hash, "account": "nano_1dpowservicetest", "user": user, "api_key" : key}
print(json_request)
r = requests.post('http://127.0.0.1:5030/service/', json = json_request)
complete_time = time.time()
print(r.text + " took: " + str(complete_time - start_time))