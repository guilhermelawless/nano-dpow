import sys
import logging
from logging.handlers import WatchedFileHandler, TimedRotatingFileHandler

def get_logger():
    logger = logging.getLogger("dpow")
    log_format = "%(asctime)s - %(levelname)s: "
    formatter = logging.Formatter(log_format, "%Y-%m-%d %H:%M:%S %z")
    log_file = "logs/dpow.txt"
    logging.basicConfig(level=logging.INFO, format=log_format + "%(message)s")
    handler = WatchedFileHandler(log_file)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addHandler(TimedRotatingFileHandler(log_file, when="d", interval=1, backupCount=30))
    return logger
