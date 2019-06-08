import sys
import logging

def get_logger():
	formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s@%(funcName)s:%(lineno)s - %(message)s')
	logger = logging.getLogger("dpow")
	logger.setLevel(logging.DEBUG)

	handler = logging.StreamHandler(sys.stderr)
	handler.setLevel(logging.WARN)
	handler.setFormatter(formatter)
	logger.addHandler(handler)

	filehandler = logging.FileHandler("log.txt", 'a', 'utf-8')
	filehandler.setLevel(logging.DEBUG)
	filehandler.setFormatter(formatter)
	logger.addHandler(filehandler)

	return logger
