#!/usr/bin/env python

import re
import argparse
import redis
import requests
import logging
from logging.handlers import TimedRotatingFileHandler, WatchedFileHandler
from collections import defaultdict
from datetime import datetime
from bpow import Validations

r = redis.StrictRedis(host="localhost", port=6379, decode_responses=True)

parser = argparse.ArgumentParser()
parser.add_argument('--node', type=str, default='http://[::1]:7072')
parser.add_argument('--wallet', type=str, help="BANANO node wallet.", default='522B56D9021982C1D99AF5AC155F148C66C717BC29A34662D6BDB07A0B0812C2')
parser.add_argument('--account', type=str, help='Account from which to send funds.', default='ban_1boompow14irck1yauquqypt7afqrh8b6bbu5r93pc6hgbqs7z6o99frcuym')
parser.add_argument('--set-payout-factor', type=float, help='Change payment factor', default=None)
parser.add_argument('--dry_run', action='store_true', help='Perform everything except sending funds, for debugging.')
args = parser.parse_args()

if args.set_payout_factor:
    print(f"Setting payout factor to {args.set_payout_factor}")
    r.set("bpow:paymentfactor", str(args.set_payout_factor))
    exit(0)
elif not Validations.validate_address(args.account):
    print("Invalid payout address specified")
    exit(1)

MAX_PAYOUT_FACTOR = 0.1

payout_factor = r.get("bpow:paymentfactor")
# There's a MAX_PAYOUT_FACTOR to avoid someone from fat fingering the change
payout_factor = min(float(payout_factor), MAX_PAYOUT_FACTOR) if payout_factor is not None else 0
print(f"Paying {payout_factor} BANANO per PoW")

clients = r.smembers("clients")
clients = {c for c in clients}

final_payout_sum = 0

# Setup logging
LOG_FILE = '/tmp/bpow_payments.log'
logger = logging.getLogger()
def setup_logger():
    logging.basicConfig(level=logging.INFO)
    handler = WatchedFileHandler(LOG_FILE)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s@%(funcName)s:%(lineno)s", "%Y-%m-%d %H:%M:%S %z")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(TimedRotatingFileHandler(LOG_FILE, when="d", interval=1, backupCount=100))

setup_logger()

def communicate_wallet(wallet_command) -> dict:
    try:
        r = requests.post(args.node, json=wallet_command, timeout=300)
        return r.json()
    except requests.exceptions.RequestException:
        return None

def send(destination : str, amount_ban : float) -> str:
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
    resp = communicate_wallet(action)
    if resp is not None and 'block' in resp:
        return resp['block']
    return None

for client in clients:
    if not Validations.validate_address(client):
        logger.info(f"!Skipping client '{client}' as it is an invalid BANANO account!\n\n")
        continue
    client_info = r.hgetall(f"client:{client}")
    if not client_info:
        continue
    logger.info(f"Processing payments for {client}")

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
        logger.error(f"Skipping client, bad state: client has total_works < total_credited {client}")
        continue
    elif should_be_credited == 0:
        continue

    payment_amount = should_be_credited * payout_factor

    logger.info(f"Paying {payment_amount} to {client} for {should_be_credited} PoWs")

    if args.dry_run:
        logger.info("Dry run, not processing payment")
        continue

    send_resp = send(client, payment_amount)
    if send_resp is not None:
        r.hset(f"client:{client}", 'total_credited', str(total_works))
        r.hset(f"client:{client}", 'total_paid', str(payment_amount + total_paid))
        final_payout_sum += payment_amount
    else:
        logger.error("PAYMENT FAILED, RPC SEND RETURNED NULL")

total_paid_db = r.get('bpow:totalrewards')
total_paid_db = float(total_paid_db) if total_paid_db is not None else 0.0

total_paid_db += final_payout_sum

r.set('bpow:totalrewards', str(total_paid_db))

logger.info(f"Total paid today {final_payout_sum}, total paid all time {total_paid_db}")
