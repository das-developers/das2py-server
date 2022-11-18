"""Utilities for handling data coverage meta-dataset generation"""

import dasflex.util.task as T
import dasflex.util.error as E

##############################################################################
# Little Enum to help keep coverage dataset update job field numbers straight

class COVERAGE_FIELDS(T.JOB_FIELDS):
	DATASET = 7
	BEGIN = 8
	END = 9
	REQ_BEGIN = 11
	STATUS = 12
	PROGRESS = 13

	@staticmethod
	def length():
		return 14


##############################################################################

class Task(T.TaskHandler):
	
	def __init__(self, dConf, broker, sQueue, iJobIdx, sTask):
		T.Task.__init__(self, dConf, broker, sQueue, iJobIdx, sTask)
	
	def shutdown(self, signum):
		pass
	
	def run(self, fLog):
		raise E.TodoError("Updating Coverage Plots is not yet implemented")
	
