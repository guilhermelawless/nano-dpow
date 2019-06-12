import argparse

class DpowConfig(object):

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--web_host', type=str, default='127.0.0.1', help="Web server host")
        parser.add_argument('--web_path', type=str, default='', help='Web server path')
        parser.add_argument('--requests_port', type=int, default=5030, help="Web server port for incoming service requests")
        parser.add_argument('--blocks_port', type=int, default=5040, help="Web server port for incoming blocks via the node callback")
        parser.add_argument('--use_websocket', action='store_true', help="If enabled, will get blocks via websocket and not callback")
        parser.add_argument('--websocket_uri', type=str, default='ws://[::1]:7078', help="The Node (v19+) websocket server URI")
        parser.add_argument('--redis_uri', type=str, default='redis://localhost', help="Redis server URI")
        parser.add_argument('--mqtt_uri', type=str, default='mqtt://localhost:1883', help="MQTT broker URI")
        parser.add_argument('--debug', action='store_true', help="Enable debugging mode (all blocks are precached")

        args = parser.parse_args()

        self.web_host = args.web_host
        self.web_path = args.web_path
        self.requests_port = args.requests_port
        self.blocks_port = args.blocks_port
        self.use_websocket = args.use_websocket
        self.websocket_uri = args.websocket_uri
        self.redis_uri = args.redis_uri
        self.mqtt_uri = args.mqtt_uri
        self.debug = args.debug
