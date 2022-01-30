"""General Utilities for Recording DataSet usage statistics"""

import das2server.util.task as T
import das2server.util.error as E

##############################################################################
# Little Enum to help keep data access job field numbers straight

class USAGE_FIELDS(T.JOBS_FIELDS):
	DATASET = 7
	BEGIN = 8
	END = 9
	PARAMS = 10
	RESOLUTION = 11
	INTERVAL = 12
	REQ_BEGIN = 13
	STATUS = 14
	PROGRESS = 15

	@staticmethod
	def length():
		return 16

##############################################################################

class Task(T.TaskHandler):
	
	def __init__(self, dConf, broker, sQueue, iJobIdx, sTask):
		T.Task.__init__(self, dConf, broker, sQueue, iJobIdx, sTask)
	
	def shutdown(self, signum):
		pass
	
	def run(self, fLog):
		raise E.TodoError("Updating usage statistics is not yet implemented")
	
