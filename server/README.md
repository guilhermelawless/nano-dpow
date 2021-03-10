# Nano DPoW Server

## Requirements

* Python 3.6.7 or higher.
* A redis server running on `redis://localhost` by default.
* An MQTT broker (tested with Mosquitto) running listening on port `1883` by default.
  * A websocket listener on port `9001` to allow javascript clients for dashboard and web-based workers.
* Authentication configured on the MQTT broker.
* Callbacks from a Nano node to port `5030` by default.
* DNS fully configured and a web server running (example provided is Nginx).

```bash
sudo apt install python3.7 python3-pip redis redis-server nginx git
```

## Installation

The following instructions have been tested on Ubuntu 18.04 LTS.

```bash
# Create a user for dpow
sudo adduser dpow

# Make dpow a sudoer and switch session
sudo usermod -aG sudo dpow && su - dpow

# Download DPoW
git clone https://github.com/guilhermelawless/nano-dpow && cd nano-dpow/server

# Install the Python dependencies
pip3 install --user -r requirements.txt
```

### Setup Mosquitto

```bash
sudo apt install mosquitto mosquitto-auth-plugin

# Copy the Mosquitto configuration file
sudo cp setup/mosquitto/dpow.conf /etc/mosquitto/conf.d/dpow.conf

# Copy the access control file
sudo cp setup/mosquitto/acls /etc/mosquitto/acls

# Create passwords for the MQTT users
# When asked, set password "client". An obvious password is used so that everyone can freely contribute work
sudo mosquitto_passwd -c /etc/mosquitto/passwd client

# Use your own passwords
sudo mosquitto_passwd -b /etc/mosquitto/passwd dpowserver COMPLEX_PASSWORD_1
sudo mosquitto_passwd -b /etc/mosquitto/passwd dpowinterface COMPLEX_PASSWORD_2

# Restart Mosquitto
sudo systemctl restart mosquitto
```

### Setup DPoW as a service

```bash
# Add and configure the service file
sudo cp setup/systemd/dpow.service /etc/systemd/system/dpow.service && sudo vim /etc/systemd/system/dpow.service 

# Enable on startup and start DPoW
sudo systemctl enable dpow && sudo systemctl start dpow
```

View logs with `systemctl status dpow` and `cat /tmp/dpow.txt`.

### Open ports

If you have a firewall (please do), the following ports should be open for inbound TCP traffic:
* `80` and `443` for HTTP and HTTPS, respectively.
* `1883` for MQTT.
* `5040` for Nano block callbacks if the node is not in the same server. Open only to the specific IP.

### Setup Nginx

```bash
# Add and configure the web server, change {DNS_HERE} to your server name
sudo cp setup/nginx/dpow /etc/nginx/sites-available/dpow && sudo vim /etc/nginx/sites-available/dpow

# Enable the server
sudo ln -s /etc/nginx/sites-available/dpow /etc/nginx/sites-enabled/

# Test nginx
sudo nginx -t
```

Highly recommended - secure the server with [CertBot](https://certbot.eff.org/instructions).  Select Nginx on the dropdown and CertBot will make the required changes to the website.

```bash
# Reload nginx to start the server
sudo systemctl restart nginx

# Should return {"error":"Bad request (not json)"} if the setup is correct and DPoW is running
curl -d "test" https://{DNS_HERE}/service/
```

### Cleanup

```bash
# Remove dpow from sudoers
sudo gpasswd -d dpow sudo
```

## Usage

If you followed the previous instructions, the server should be running as a service called `dpow`. The next steps are:

1. Have clients using [dpow_client.py](../client/dpow_client.py) to use argument `--server mqtt://client:client@{DNS_HERE}:1883`
2. Setup some services by using [services.py](scripts/services.py)
  ```bash
  # View instructions
  python3 scripts/services.py --help

  # Add a new service
  python3 scripts/services.py --add test_service
  ```
3. Perform a request either using HTTPS POST or WSS. For HTTPS POST, see the [random_hash_request.py](../service/random_hash_request.py) example and edit the file to point the request to your server. If there are clients connected the request should be fulfilled, otherwise it will return a timeout error after 10 seconds.

## Configuration

See file `nano-dpow/server/dpow/config.py` for some available configuration options

## Payouts

Inside `nano-dpow/server/scripts` run:

- `python3 client_snapshot.py` to create a snapshot of work provided by clients since the last snapshot. This creates `PAYOUTS_FILE` in this directory.
- `python3 payouts.py --help` to learn how to use it

## Web dashboard

A dashboard was created by [mitche50](https://github.com/mitche50). See https://github.com/mitche50/dpow-mqtt for setup instructions. If you followed the dpow server setup above, then the username should be `dpowinterface`.
