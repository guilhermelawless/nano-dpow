# Nano DPoW Client

These steps will guide you on how to setup a new work client. The nano-work-server provided is based on [nanocurrency/nano-work-server](https://github.com/nanocurrency/nano-work-server). Only this work server is fully supported.

## Setup

### Requirements

1. Python 3.6.7 or higher.

### Installation

```bash
pip3 install --user -r requirements.txt
```

## Running

### Work Server

#### Linux

```bash
./bin/linux/nano-work-server --gpu 0:0 -l 127.0.0.1:7000
```

Check `./bin/linux/nano-work-server --help` for information on how to select your GPU (or CPU)

#### Windows (experimental)

Edit the properties of the file `run_work_server.lnk` inside `bin\windows` to run `bin\windows\nano-work-server.exe` with the desired options when clicked. Run it, should leave a terminal window running in the foreground.

### DPoW Client

Check the possible options with `--help`, and run as follows (choose one of the work types only):

```bash
python3 dpow_client.py --payout YOUR_NANO_ADDRESS --work {ondemand,precache,any}
```
