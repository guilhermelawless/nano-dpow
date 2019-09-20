#!/usr/bin/env python

import re
import argparse
import redis
import requests
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
clients = {c for c in clients}

final_payout_sum = 0

def communicate_wallet(self, wallet_command) -> dict:
    try:
        r = requests.post(args.node, json=wallet_command, timeout=300)
        return r.json()
    except requests.exceptions.RequestException:
        return None

def send(self, destination : str, amount_ban : float, uid : str) -> str:
    """Send amount to destination, return hash. None if failed"""
    expanded = float(amount_ban) * 100
    amount_raw = str(int(expanded) * (10 ** 27))
    action = {
        "action": "send",
        "wallet": args.wallet,
        "source": args.account,
        "destination": destination,
        "amount": amount_raw
    }
    resp = self.communicate_wallet(action)
    if resp is not None and 'block' in resp:
        return resp['block']
    return None

for client in clients:
    if not Validations.validate_address(client):
        print("!Skipping client '{}' as it is an invalid BANANO account!\n\n".format(client))
        continue
    client_info = r.hgetall(f"client:{client}")
    if not client_info:
        continue
    print(f"Processing payments for {client}")

    # Sum total work contributions
    total_works = 0
    total_works += int(client_info['precache']) if 'precache' in client_info else 0
    total_works += int(client_info['ondemand']) if 'ondemand' in client_info else 0

    # Get how many pows this client has already been paid for
    total_credited = int(client_info['total_credited']) if 'total_credited' in client_info else 0
    total_paid = int(client_info['total_paid']) if 'total_paid' in client_info else 0

    # Get how many this client should be paid for
    should_be_credited = total_works - total_credited

    if should_be_credited < 0:
        raise Exception(f'bad state, client has total_works < total_credited {client}')
    elif should_be_credited == 0:
        continue

    payment_amount = should_be_credited * payout_factor

    print(f"Paying {payment_amount} to {client} for {should_be_credited} PoWs")

    if args.dry_run:
        print("Dry run, not processing payment")
        continue

    send_resp = send(client, payment_amount)
    if send_resp is not None:
        r.hset(f"client:{client}", 'total_credited', str(total_works))
        r.hset(f"client:{client}", 'total_paid', str(payment_amount + total_paid))
        final_payout_sum += payment_amount
    else:
        print("PAYMENT FAILED, RPC SEND RETURNED NULL")

    print("\n")

total_paid_db = r.get('dpow:totalrewards')
total_paid_db = float(total_paid_db) if total_paid_db is not None else 0.0

total_paid_db += final_payout_sum

r.set('dpow:totalrewards', str(total_paid_db))

print(f"Total paid today {final_payout_sum}, total paid all time {total_paid_db}")