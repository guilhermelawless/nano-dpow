import sys
import logging
from logging.handlers import WatchedFileHandler, TimedRotatingFileHandler

def get_logger():
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s@%(funcName)s:%(lineno)s - %(message)s", "%Y-%m-%d %H:%M:%S %z")
    logger = logging.getLogger("dpow")
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.WARN)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    log_file = "/tmp/dpow.txt"
    filehandler = WatchedFileHandler(log_file)
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(formatter)
    logger.addHandler(filehandler)
    logger.addHandler(TimedRotatingFileHandler(log_file, when="d", interval=1, backupCount=100))
    return logger
