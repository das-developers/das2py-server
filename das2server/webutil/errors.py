"""Error types for das flex server libraries"""

class DasError(Exception):
	"""Generic class to catch all das errors but ignore built-in errors"""
	pass

class CancelOp(DasError):
	"""Generic class to use from signal handlers to indicate a blocking
	operation should cease"""
	pass

class ServerError(DasError):
	"""Raised when the user tried to preform a valid operation but the
	server is messed up is same way"""
	
	pass


class TodoError(DasError):
	"""Raised when the user tried to preform a valid operation but some
	of the code isn't finished."""
	
	pass


class QueryError(DasError):
	"""Raised the user query to the das2 server has a problem"""
	pass


class ForbidError(DasError):
	"""Raised when the user tried to access something they are not allowed
	to see.  Used exclsively with password proteceted data sources. 
	Misconfigured file permissions are a ServerError"""
	
	pass


class NotFoundError(DasError):
	"""Consider using a QueryError instead, unless you have found half of
	something an the other half is missing."""
	
	pass

class RemoteServer(DasError):
	"""With federated catalogs, server  aren't supposed to advertise other
	servers stuff it's not thier job to worry about it"""

