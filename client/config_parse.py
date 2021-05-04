import argparse
import re

WORK_TYPES = ["ondemand", "precache", "any"]

def nano_public_address(string):
    p = re.compile('^(nano|xrb)_[13]{1}[13456789abcdefghijkmnopqrstuwxyz]{59}$')
    if not p.match(string):
        msg = "%r is not a valid Nano address" % string
        raise argparse.ArgumentTypeError(msg)
    return string

class DpowClientConfig(object):

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--server', type=str, default='wss://client:client@dpow-api.nanos.cc', help="MQTT broker URI")
        parser.add_argument('--worker_uri', type=str, default='127.0.0.1:7000', help='URI of work server listening for RPC calls.')
        parser.add_argument('--payout', type=nano_public_address, required=True, help='Payout address.')
        parser.add_argument('--work', type=str, action='store', choices=WORK_TYPES, default="any", help='Desired work type. Options: any (default), ondemand, precache.')

        args = parser.parse_args()

        self.server = args.server
        self.worker = args.worker_uri
        self.payout = args.payout
        self.work_type = args.work
