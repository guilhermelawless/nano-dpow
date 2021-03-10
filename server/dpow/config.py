import argparse
from os import environ


class DpowConfig(object):

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--web_path', type=str, default='', help='(Optional) Path to a local domain socket if a web server is configured to redirect to it')
        parser.add_argument('--websocket_uri', type=str, default='', help="The Node (v19+) websocket server URI, example ws://[::1]:7078")
        parser.add_argument('--mqtt_uri', type=str, default='', help="MQTT broker URI, alternatively set the MQTT_SECRET_URI environment variable, example mqtt://USER:PASSWORD@localhost:1883")
        parser.add_argument('--debug', action='store_true', help="Enable debugging mode (all blocks are precached)")

        parser.add_argument('--block_expiry', type=int, default=24*60*60, help='How long to keep block hashes in the database. In seconds, default 1 day')
        parser.add_argument('--account_expiry', type=int, default=30*24*60*60, help='How long to keep accounts in the database, reset when the account frontier is updated. In seconds, default 1 month')
        parser.add_argument('--max_multiplier', type=float, default=5.0, help='The maximum multiplier from base difficulty that is accepted. Default 5.0')
        parser.add_argument('--throttle', type=float, default=1.0, help='The number of requests each service can do every second. Minimum 0.1, default 1.0')

        parser.add_argument('--difficulty', type=str, default='', help='Difficulty threshold, example fffffff800000000 . By default, the Nano main network threshold is used')
        args = parser.parse_args()

        self.web_path = args.web_path
        self.websocket_uri = args.websocket_uri
        self.mqtt_uri = environ.get('MQTT_SECRET_URI', args.mqtt_uri)
        self.debug = args.debug

        self.block_expiry = args.block_expiry
        self.account_expiry = args.account_expiry
        self.max_multiplier = args.max_multiplier
        self.throttle = args.throttle

        self.difficulty = args.difficulty
