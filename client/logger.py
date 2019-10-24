import sys
import logging
from logging.handlers import WatchedFileHandler, TimedRotatingFileHandler

class WatchedTimedRotatingFileHandler(TimedRotatingFileHandler, WatchedFileHandler):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        self.dev, self.ino = -1, -1
        self._statstream()

    def emit(self, record):
        self.reopenIfNeeded()
        super().emit(record)

def get_logger(directory):
    log_file = directory + "/dpow.txt"
    logger = logging.getLogger("dpow")
    logger.setLevel(logging.DEBUG)
    stream = logging.StreamHandler(stream=sys.stdout)
    stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s", "%H:%M:%S"))
    stream.setLevel(logging.INFO)
    logger.addHandler(stream)
    file = WatchedTimedRotatingFileHandler(log_file, when="d", interval=1, backupCount=30)
    file.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s@%(funcName)s:%(lineno)s\n%(message)s", "%Y-%m-%d %H:%M:%S %z"))
    file.setLevel(logging.DEBUG)
    logger.addHandler(file)
    return logger
