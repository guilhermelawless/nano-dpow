#!/usr/bin/env python

import re
import json
import argparse
import redis
from collections import defaultdict
from datetime import datetime
from dpow import Validations

r = redis.StrictRedis(host="localhost", port=6379, decode_responses=True)

parser = argparse.ArgumentParser()
parser.add_argument('--node', type=str, default='http://[::1]:7072')
parser.add_argument('--wallet', type=str, help="BANANO node wallet.", default='0')
parser.add_argument('--account', type=str, help='Account from which to send funds.', default='ban_1boompow14irck1yauquqypt7afqrh8b6bbu5r93pc6hgbqs7z6o99frcuym')
parser.add_argument('--set-payout-factor', type=float, help='Change payment factor', default=None)
parser.add_argument('--dry_run', action='store_true', help='Perform everything except sending funds, for debugging.')
args = parser.parse_args()

if args.set_payout_factor:
    print(f"Setting payout factor to {args.set_payout_factor}")
    r.set("dpow:paymentfactor", str(args.set_payout_factor))
    exit(0)
elif not Validations.validate_address(args.account):
    print("Invalid payout address specified")
    exit(1)

payout_factor = r.get("dpow:paymentfactor")
payout_factor = min(float(payout_factor), 0.05) if payout_factor is not None else 0
print(f"Paying {payout_factor} BANANO per PoW")

clients = r.smembers("clients")

total_paid = 0

for client in clients:
    if not Validations.validate_address(client):
        print("!Skipping client '{}' as it is an invalid BANANO account!\n\n".format(client))
        continue
    client_info = r.hgetall(f"client:{client}")
    if not client_info:
        continue
    print(f"Processing payments for {client}")
    client_info = json.loads(client_info)

    # Sum total work contributions
    total_works = 0
    total_works += int(client_info['precache']) if 'precache' in client_info else 0
    total_works += int(client_info['ondemand']) if 'ondemand' in client_info else 0

    # Get how many pows this client has already been paid for
    total_credited = int(client_info['total_credited']) if 'total_credited'in client_info else 0

    # Get how many this client should be paid for
    should_be_credited = total_works - total_credited

    if should_be_credited < 0:
        raise Exception(f'bad state, client has total_works < total_credited {client}')
    elif should_be_credited == 0:
        continue

    payment_amount = should_be_credited * payout_factor
    total_paid += payment_amount

    print(f"Paying {payment_amount} to {client} for {should_be_credited} PoWs")

    #r.hset(f"client:{client}", 'total_credited', str(total_works))
    #r.hset(f"client:{client}", 'total_paid', str(payment_amount))

    print("\n")