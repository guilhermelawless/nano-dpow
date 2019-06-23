#!/usr/bin/env python3

import redis
import json
from collections import defaultdict
from datetime import datetime

r = redis.StrictRedis(host="localhost", port=6379)

clients = r.smembers("clients")
clients = {c.decode("utf-8") for c in clients}

snapshot = defaultdict(lambda: {"precache": 0, "ondemand": 0})
payouts = defaultdict(lambda: {"precache": 0, "ondemand": 0})

for client in clients:
    client_info = r.hgetall(f"client:{client}")
    print(client, client_info)

    for work in ('precache', 'ondemand'):
        work_enc = str.encode(work, "utf-8")
        if work_enc in client_info:
            amount = int(client_info[work_enc])
            snapshot_enc = str.encode("snapshot_"+work, "utf-8")
            snapshot_amount = int(client_info.get(snapshot_enc, 0))
            payout_amount = amount - snapshot_amount
            if payout_amount < 50:
                print(f"Skipping {work}, only did {payout_amount} since last snapshot.")
                continue
            snapshot[client][work] += snapshot_amount
            payouts[client][work] += payout_amount
            r.hset(f"client:{client}", snapshot_enc.decode("utf-8"), amount)
    print("\n")

now = f"{datetime.now():%Y-%m-%d_%H-%M-%S}"

payouts = dict(payouts)
with open(f"payouts_{now}.json", "w") as f:
    json.dump(payouts, f, indent=4)

snapshot = dict(snapshot)
with open(f"snapshot_{now}.json", "w") as f:
    json.dump(snapshot, f, indent=4)

print(f"Updated DB and wrote to files with timestamp {now}")