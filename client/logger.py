import sys
import logging
from logging.handlers import WatchedFileHandler, TimedRotatingFileHandler

def get_logger():
    log_file = "logs/dpow.txt"
    logger = logging.getLogger("dpow")
    logger.setLevel(logging.DEBUG)
    stream = logging.StreamHandler(stream=sys.stdout)
    stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%H:%M:%S"))
    stream.setLevel(logging.INFO)
    logger.addHandler(stream)
    file = WatchedFileHandler(log_file)
    file.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s@%(funcName)s:%(lineno)s", "%Y-%m-%d %H:%M:%S %z"))
    file.setLevel(logging.DEBUG)
    logger.addHandler(file)
    logger.addHandler(TimedRotatingFileHandler(log_file, when="d", interval=1, backupCount=30))
    return logger
