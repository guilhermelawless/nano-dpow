# Nano DPoW Client

These steps will guide you on how to setup a new work client. The nano-work-server provided is based on [nanocurrency/nano-work-server](https://github.com/nanocurrency/nano-work-server). Only this work server is fully supported.

## Setup

### Requirements

1. [Python](https://www.python.org/) 3.6.7 or higher.

### Installation

```bash
git clone https://github.com/guilhermelawless/nano-dpow.git
cd nano-dpow/client
pip3 install --user -r requirements.txt
```

## Running

You need to find out what your GPU vendor/device numbers are if you're going to be using a GPU. Usually it will be either `0:0`, `0:1`, or `1:0`, depending on how many you have (including integrated graphics).

### Linux

1. Install required library
   ```bash
   sudo apt install ocl-icd-libopencl1
   ```
2. Check `./bin/linux/nano-work-server --help` for information on how to select your GPU (or CPU).
3. Run the work server:
  ```bash
  ./bin/linux/nano-work-server --gpu 0:0 -l 127.0.0.1:7000
  ```
4. Check the client configuration options with `python3 dpow_client.py --help`
5. Run the client:
  ```bash
  python3 dpow_client.py --payout YOUR_NANO_ADDRESS --work {ondemand,precache,any}
  ```

### Windows

1. Edit the file `run_windows.bat` with your desired configuration (including the work-server GPU config).
2. Double-click the same file, which should eventually open two terminals. You must leave them running in the foreground. You can minimize but not close them (sorry!).
