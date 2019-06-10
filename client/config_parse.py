import argparse

WORK_TYPES = ["ondemand", "precache", "any"]

class DpowClientConfig(object):

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--server', type=str, default='mqtt://client:client@139.59.134.66:1883', help="MQTT broker URI")
        parser.add_argument('--worker_uri', type=str, default='127.0.0.1:7000', help='URI of work server listening for RPC calls.')
        parser.add_argument('--payout', type=str, required=True, help='Payout address.')
        parser.add_argument('--work', type=str, action='store', choices=WORK_TYPES, default="any", help='Desired work type. Options: any (default), ondemand, precache.')

        args = parser.parse_args()

        self.server = args.server
        self.worker = args.worker_uri
        self.payout = args.payout
        self.work_type = args.work
