import argparse
from os import environ


class DpowConfig(object):

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--web_path', type=str, default='', help='Web server path')
        parser.add_argument('--use_websocket', action='store_true', help="If enabled, will get blocks via websocket and not callback")
        parser.add_argument('--websocket_uri', type=str, default='ws://[::1]:7078', help="The Node (v19+) websocket server URI")
        parser.add_argument('--mqtt_uri', type=str, default='mqtt://localhost:1883', help="MQTT broker URI")
        parser.add_argument('--debug', action='store_true', help="Enable debugging mode (all blocks are precached")

        args = parser.parse_args()

        self.web_path = args.web_path
        self.use_websocket = args.use_websocket
        self.websocket_uri = args.websocket_uri
        self.mqtt_uri = environ.get('MQTT_SECRET_URI', args.mqtt_uri)
        self.debug = args.debug
