import argparse

class DpowConfig(object):

	def __init__(self):
		parser = argparse.ArgumentParser()
		parser.add_argument('--web_host', type=str, default="127.0.0.1", help="Web server host")
		parser.add_argument('--web_port', type=int, default=5030, help="Web server port")
		parser.add_argument('--redis_uri', type=str, default="redis://localhost", help="Redis server URI")
		parser.add_argument('--mqtt_uri', type=str, default="mqtt://localhost:1883", help="MQTT broker URI")
		parser.add_argument('--debug', action="store_true", help="Enable debugging mode (all blocks are precached")

		args = parser.parse_args()

		self.web_host = args.web_host
		self.web_port = args.web_port
		self.redis_uri = args.redis_uri
		self.mqtt_uri = args.mqtt_uri
		self.debug = args.debug
