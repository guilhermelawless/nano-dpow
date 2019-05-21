import subprocess
import requests
import time

addr = "127.0.0.1:7000"
# args = ("nano-work-server", "--cpu-threads", "10", "--listen-address", addr)
args = ("nano-work-server", "--gpu", "0:0", "--listen-address", addr)
gpu = "--gpu" in args
worker = None

def create():
    worker = subprocess.Popen(args, stdout=subprocess.PIPE)
    if gpu:
        worker.stdout.readline()
    time.sleep(0.5)

def destroy():
    worker.terminate()
    worker.wait()
    worker = None

def reload():
    try:
        destroy()
    except:
        pass
    create()

def exists():
    return worker != None