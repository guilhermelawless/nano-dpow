class InvalidRequest(ValueError):
	"""The request is invalid."""
	def __init__(self, reason):
		self.reason = reason
	def __str__(self):
		return repr(self.reason)

class RequestTimeout(Exception):
	"""The request timed out."""

class RetryRequest(Exception):
	"""Something went wrong, ask to retry."""
