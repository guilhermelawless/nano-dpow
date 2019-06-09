# Nano DPoW Client

These steps will guide you on how to setup a new work client. The nano-work-server provided is based on [nanocurrency/nano-work-server](https://github.com/nanocurrency/nano-work-server). Only this work server is fully supported.

## Setup

### Requirements

1. Python 3.6.7 or higher.

### Installation

```bash
git clone https://github.com/guilhermelawless/nano-dpow.git
cd nano-dpow/client
pip3 install --user -r requirements.txt
```

## Running

### Work Server

You need to find out what your GPU vendor/device numbers are if you're going to be using a GPU.

#### Linux

```bash
./bin/linux/nano-work-server --gpu 0:0 -l 127.0.0.1:7000
```

Check `./bin/linux/nano-work-server --help` for information on how to select your GPU (or CPU)

#### Windows (experimental)

Navigate to `bin\windows` on your file explorer and double-click the file `run_work_server.bat`, it should leave a terminal window running in the foreground, which you can minimize but not close (sorry!). Edit the file to change the GPU that will be used.

Alternatively you can run `bin\windows\nano-work-server.exe` with the usual options (see above in the instructions for Linux).

### DPoW Client

Check the possible options with `--help`, and run as follows (choose one of the work types only):

```bash
python3 dpow_client.py --payout YOUR_NANO_ADDRESS --work {ondemand,precache,any}
```
