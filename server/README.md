# BoomPow Server

## Setup

### Requirements

1. Python 3.6.7 or higher.
2. A redis server running on `redis://localhost` by default.
3. An MQTT broker (tested with Mosquitto) with listeners on port `1883` and `8883`.
4. Authentication configured on the MQTT broker
5. Callbacks from a BANANO node to `127.0.0.1:5030` by default.

### Installation

```bash
pip3 install -r requirements.txt
```

## Running

```bash
python3 bpow_server.py
```
