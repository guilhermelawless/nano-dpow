import sys
import logging
from logging.handlers import WatchedFileHandler, TimedRotatingFileHandler

def get_logger():
    logger = logging.getLogger("dpow")
    logging.basicConfig(level=logging.INFO)
    log_file = "/tmp/dpow.txt"
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s@%(funcName)s:%(lineno)s", "%Y-%m-%d %H:%M:%S %z")
    handler = WatchedFileHandler(log_file)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(TimedRotatingFileHandler(log_file, when="d", interval=1, backupCount=100))
    return logger
