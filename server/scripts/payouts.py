#!/usr/bin/env python3

import requests
import json
import re
import argparse
import nanolib
from sys import exit


def nano_public_address(string):
    p = re.compile('^(nano|xrb)_[13]{1}[13456789abcdefghijkmnopqrstuwxyz]{59}$')
    if not p.match(string):
        msg = "%r is not a valid Nano address" % string
        raise argparse.ArgumentTypeError(msg)
    return string


parser = argparse.ArgumentParser()
parser.add_argument('--node', type=str, default='http://[::1]:7076')
parser.add_argument('--wallet', type=str, required=True, help="Nano node wallet.")
parser.add_argument('--account', type=nano_public_address, required=True, help='Account from which to send funds.')
parser.add_argument('--distribution', type=float, required=True, help='How much of the account balance to distribute')
parser.add_argument('--dry_run', action='store_true', help='Perform everything except sending funds, for debugging.')
parser.add_argument('payouts_file', type=str, help='The JSON encoded file with payout information.')
args = parser.parse_args()


def node(json_request):
    try:
        r = requests.post(args.node, json=json_request).json()
    except:
        raise Exception("Could not reach the node")
    if 'error' in r:
        raise Exception("Error in call: {} -> {}".format(json_request, r['error']))
    return r

with open(args.payouts_file, 'r') as f:
    payouts = json.load(f)

print("\nChecking for invalid clients...")

# Remove invalid clients
for client in list(payouts.keys()):
    try:
        nano_public_address(client)
    except argparse.ArgumentTypeError:
        print("Skipping client '{}' as it is an invalid Nano account".format(client))
        payouts.pop(client)

print("\n========= DPOW PAYOUTS =========")
total_works = sum(map(lambda x: x[1]['precache'] + x[1]['ondemand'], payouts.items()))
print("Number of proofs:", total_works)

balance_raw = int(node({"action": "account_balance", "account": args.account})['balance'])
print("Balance available: {} raw = {} Mnano".format(balance_raw, nanolib.convert(balance_raw, nanolib.NanoDenomination.RAW, nanolib.NanoDenomination.MEGANANO)))
total_payout = int(args.distribution*balance_raw)
print("Total payout given {} distribution will be {} Mnano".format(args.distribution, nanolib.convert(total_payout, nanolib.NanoDenomination.RAW, nanolib.NanoDenomination.MEGANANO)))
print("================================\n")

# Compute the amounts
payouts_ready = dict()
payout_ids = dict()
for client, details in payouts.items():
    p_id = details.get('id', None)
    if not p_id:
        print("\n\n!!ABORT unique id not found in payout file")
        exit(1)
    payout_ids[client] = p_id
    precache = details.get('precache', 0)
    ondemand = details.get('ondemand', 0)
    print("\nClient {} did {} precache and {} ondemand".format(client, precache, ondemand))
    client_total = precache + ondemand
    factor = float(client_total) / total_works
    payout_raw = int(factor*total_payout)
    print("They get {:.3f} % of the payout -> {} Mnano".format(factor*100., nanolib.convert(payout_raw, nanolib.NanoDenomination.RAW, nanolib.NanoDenomination.MEGANANO)))
    if payout_raw > 0:
        payouts_ready[client] = payout_raw

if args.dry_run:
    print("\n--dry_run was given, no payouts done!\n")
    exit(0)

cont = input("\nContinue with payouts? Must answer exactly: OFCOURSE ... ")
if cont != "OFCOURSE":
    print("No payouts were done")
    exit(1)

# Actually payout
payout_info = dict()
for client, amount_raw in payouts_ready.items():
    print("Sending {} to {}...".format(amount_raw, client), end=' -> ')
    send_id = payout_ids[client]
    try:
        response = node({"action": "send", "id": send_id, "wallet": args.wallet, "source": args.account, "destination": client, "amount": amount_raw})
        block = response['block']
        print(block, "\n")
        payout_info[client] = dict(block=response['block'], amount=amount_raw)
    except Exception as e:
        print(e)
        input("Continue after error? (Ctrl-C to cancel)")

with open('payout_finished_info.json', 'w') as f:
    json.dump(payout_info, f, indent=4)
