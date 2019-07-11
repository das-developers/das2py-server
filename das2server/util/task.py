"""General Work Task creater and Handler"""

import sys
import time

try:
	import redis
	g_bHaveRedis = True
except ImportError, e:
	g_bHaveRedis = False


from errors import *

##############################################################################
class QueueBroker(object):
	"""Wrapper for redis so that different brokers can be used and so execption
	types are standardized.
	"""
	
	# REDIS default connection class will not handle sigterm properly (doesn't
	# break out of the read), so override it
	
	def __init__(self, **kwargs):
		self.broker = redis.StrictRedis(**kwargs)
	
	def disconnect(self):
		self.broker.connection_pool.disconnect()
	
	def keys(self, sPtrn):
		try:
			ret = self.broker.keys(sPtrn)
		except redis.exceptions.ConnectionError, e:
			raise ServerError(str(e))
		return ret
		
	def lrange(self, sKey, iBeg, iEnd):
		try:
			ret = self.broker.lrange(sKey, iBeg, iEnd)
		except redis.exceptions.ConnectionError, e:
			raise ServerError(str(e))
		return ret
	
	def lpush(self, sKey, sVal):
		try:
			ret = self.broker.lpush(sKey, sVal)
		except redis.exceptions.ConnectionError, e:
			raise ServerError(str(e))
		return ret
	
	def brpoplpush(self, sPopQueue, sPushQueue):
		try:
			ret = self.broker.brpoplpush(sPopQueue, sPushQueue)
		except redis.exceptions.ConnectionError, e:
			raise ServerError(str(e))
		return ret
			
	def lpop(self, sQueue):
		try:
			ret = self.broker.lpop(sQueue)
		except redis.exceptions.ConnectionError, e:
			raise ServerError(str(e))
		return ret
		
	def delete(self, sKey):
		try:
			ret = self.broker.delete(sKey)
		except redis.exceptions.ConnectionError, e:
			raise ServerError(str(e))
		return ret
		
	def lset(self, sKey, iPos, sVal):
		try:
			ret = self.broker.lset(sKey, iPos, sVal)
		except redis.exceptions.ConnectionError, e:
			raise ServerError(str(e))
		return ret
		

##############################################################################
def getBroker(fLog, dConf):
	"""Get the work queue broker specified in the config file.
	
	The returned object will have the following methods:
	
	
	Nominally this will be a redis broker, but others could be implemented
	"""
	global g_bHaveRedis
	
	if not g_bHaveRedis:
		fLog.write("   Redis key-server module not installed on sys.path: %s"%sys.path)
		return None
	
	sBroker = 'redis'
	if dConf.has_key('WORK_QUEUE_BROKER'):
		if dConf['WORK_QUEUE_BROKER'].lower() != 'redis':
			fLog.write("Configuration Error, currently only redis is supported"+\
			           " as a work queue broker.\n  WORK_QUEUE_BROKER = "+\
						  "%s\nExiting...\n"%dConf['WORK_QUEUE_BROKER'])
			return None
			
	
	lConn = ["localhost", 6379, 0]
	if dConf.has_key("WORK_QUEUE_CONN"):
		lConn = dConf["WORK_QUEUE_CONN"].split(":")
		if len(lConn) > 1:
			lConn[1] = int(lConn[1])
		if len(lConn) > 2:
			lConn[2] = int(lConn[2])
	
	# Since re-dis libs do lasy connection, get a list of das2 keys to kick
	# some communication, before handing back the broker object	
	try:
		broker = QueueBroker(host=lConn[0], port=lConn[1], db=lConn[2],
		                     socket_connect_timeout=300)
		sKey = broker.keys('das2_*')
	except ServerError, e:
		fLog.write("   ERROR: Job broker not available at %s:%d, db=%d.\n"%(
		     lConn[0], lConn[1], lConn[2]))
		return None
		
	return broker


##############################################################################
# Static ENUM Class to help keep the field numbers straight

class JOB_FIELDS(object):
	REQ_TIME = 0
	REQUESTER = 1
	REQUESTER_EX = 2
	RMTREQ = 3
	RMTREQ_EX = 4
	USER = 5
	CATEGORY = 6


##############################################################################
def curTime():
	rTime = time.time()
	nMilli = int( (rTime - int(rTime))*1000 )
	t = time.gmtime(rTime)
	sTm ='%s.%03d'%('%04d-%02d-%02dT%02d:%02d:%02d'%tuple(t[:6]),nMilli)
	return sTm


##############################################################################
#def makeJobEntry(sReq, sReqEx, sRmtReq, sRmtReqEx, sUser, sCat, lJobArgs):
#	"""Make generic job enteries
#	"""


##############################################################################

class TaskHandler(object):
	"""Handle communicating updates to a work queue so that job handling 
	code dosen't have to know about which broker is in use.
	
	SubClasses should implement a run(fLog) method.
	"""
	
	def __init__(self, dConf, broker, sQueue, iJobIdx, sTask, fLog):
		"""Initialize a task, requires the following objects
		
		dConf - The dictionary of configuration file key = value pairs
		
		broker - Designed around redis.StrictRedis objects, but can take anything
		         that has an lset(sQueue, iIndex, sValue) mothod
		
		sQueue - The work queue on which this task lives.  Only used when
		         callling broker.lset() 
		
		iJobIdx - The index of the entry in the work queue, Only used when
		          calling broker.lset()
		
		sTask - A pipe, '|', delimited string as defined in Appendix B of 
		        the PyServer User's reference.  If this string doesn't follow
		        the rules for a work item, then a ValueError exception is
		        thrown.
				  
		fLog - A das logger for writing info messages, is not stored but instead
		       is only used for the duration of the function.
		"""
		self.dConf = dConf
		
		self.broker = broker
		self.sQueue = sQueue
		self.iJobIdx = iJobIdx
		self.sTask = sTask
		
		self.lTask = sTask.split('|')
		if len(self.lTask) < 7:
			raise QueryError("Task field list has less than the required 7 "+\
			                 "members: %s"%self.lTask)
								  		
		self.bStartCalled = False
		self.bEndCalled = False
		self.sStartTime = None
		self.sEndTime = None
		self.sStatus = None
		self.nRetCode = None
	
	
	def shutdown(self, signum):
		"""Call this to halt the task, includes sending a SIGINT to any child
		processes.  
		
		Derived Classes must override this
		"""
		pass
	
	def run(self, fLog):
		"""Call this to run the task, may trigger calls to update the progress
		for this work item in the broker.
		
		Derived Classes must override this
		"""
		pass
		
	
	def fields(self):
		return len(self.lTask)
	
	
	def get(self, iIdx):
		if iIdx < 0 or iIdx >= len(self.lTask):
			raise IndexError("Index %d is out of range for task type %s"%(
			                 iIdx, self.lTask[6]))
								  
		return self.lTask[iIdx]
		
		
	def category(self):
		"""Return the job category"""
		return self.lTask[JOB_FIELDS.CATEGORY].lower()
		
		
	def incIdx(self):
		self.iJobIdx += iJobIdx
		
	
	def decIdx(self):
		if self.iJobIdx - 1 < 0:
			raise ValueError("List index %d is impossible"%iJobIdx)
		self.iJobIdx -= iJobIdx
				
		
	def begin(self, sStatus=''):
		assert( not self.bStartCalled)
		self.bStartCalled = True
		
		self.lTask.append(curTime())
		self.lTask.append(sStatus)
		self.lTask.append('0/100')
		
		sTask = '|'.join(self.lTask)
		self.broker.lset(self.sQueue, self.iJobIdx, sTask)
		
		
	def setProgress(self, rProgress, sStatus=''):
		"""Tracks progress as a fraction from 0 to 1.0"""
		
		self.lTask[-2] = sStatus
		self.lTask[-1] = '%.2f'%rProgress
		
		sTask = '|'.join(self.lTask)
		self.broker.lset(self.sQueue, self.iJobIdx, sTask)
		
	
	def end(self, nRetCode=None, sStatus=None):
		assert(self.bStartCalled)
		assert( not self.bEndCalled)
		self.bEndCalled = True
		
		if sStatus != None:
			self.sStatus = sStatus
		
		if self.sStatus != None:
			self.lTask[-2] = self.sStatus
		else:
			self.lTask[-2] = ''
		
		self.sEndTime = curTime()
		self.lTask[-1] = self.sEndTime
		
		if nRetCode != None:
			self.nRetCode = nRetCode
			
		self.lTask.append("%d"%self.nRetCode)
				
		sTask = '|'.join(self.lTask)
		self.broker.lset(self.sQueue, self.iJobIdx, sTask)
		
	def endTime(self):
		return self.sEndTime
	
	def retCode(self):
		return self.nRetCode


