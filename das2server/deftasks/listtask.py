"""Update the list of Data sources"""

import das2server.util.task as T
import das2server.util.error as E


##############################################################################

class Task(T.TaskHandler):
	
	def __init__(self, dConf, broker, sQueue, iJobIdx, sTask):
		T.Task.__init__(self, dConf, broker, sQueue, iJobIdx, sTask)
	
	def shutdown(self, signum):
		pass
	
	def run(self, fLog):
		raise E.TodoError("Updating a cached list of dataset files is not yet implemented")

