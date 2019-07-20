"""General Utilities for working with data-set caches"""

import os
import os.path
from os.path import join as pjoin
import subprocess

from das2.dastime import DasTime

import das2server.util.dsdf as D
import das2server.util.task as T
import das2server.util.errors as E
import das2server.util.cache as C	

import sys

##############################################################################

class Task(T.TaskHandler):
	"""Handle Cache Creation Tasks.  The Steps are
	
	1. See if we have a valid task and the task makes sense with the DSDF
	
	2. Adjust the start and stop times so that they hit even blocking periods.
	
	3. Iterate over blocking periods to make the cache at the specified resolution.
	
	"""
	
	###########################################################################
	def __init__(self, dConf, broker, sQueue, iJobIdx, sTask, fLog):
		T.TaskHandler.__init__(self, dConf, broker, sQueue, iJobIdx, sTask, fLog)
		
		# New variables
		self.dsdf   = None    # The DSDF object that goes with the datasource
		self.lLevels = None   # The cache levels to create
		self.proc    = None   # The current sub-shell process
		self.bShutdown = False # A flag to indicate that processing should be
		                       # cut off
		
		self.dBounds = {}     # The list of overall cache boundaries by level
		                      # Each entry in this dict is a 3-tuple of:
									 #   (Begin, End, (increment tuple) )
		
		if len(self.lTask) != C.CACHE_FIELDS.LEN_INITAL:
			raise E.QueryError("Expected %d fields for "%C.CACHE_FIELDS.LEN_INITAL+\
			                   "in-processes caching tasks, entry has %d."% len(self.lTask))
		
		# Check that the cache root directory exists
		if not os.path.isdir( self.dConf['CACHE_ROOT'] ):
			raise E.ServerError("Cache Root directory missing: %s"%self.dConf['CACHE_ROOT'])
		
		# Get and check the DSDF
		sDsdf = self.lTask[C.CACHE_FIELDS.DATASET]
		
		self.dsdf = D.Dsdf(sDsdf, self.dConf, None, fLog)
		self.dsdf.fillDefaults(self.dConf)
		
		sCacheRoot = pjoin(dConf['CACHE_ROOT'], "data")
					
		# Note, DSDFs that specify interval datasources aren't yet cacheable
		if u'requiresInterval' in self.dsdf:
			E.TodoError("Caching for interval based data sources such as "+\
			            sDsdf + " is not yet implemented")
			
		
		if len(self.dsdf['cacheLevel']) == 0:
			raise E.QueryError("Dataset %s does not define any cache levels"%sDsdf)
					
		# Get the cache levels to be created
		sLvlTmp = self.lTask[C.CACHE_FIELDS.LEVEL]
		if sLvlTmp.lower() == 'all':
			self.lLevels = self.dsdf['cacheLevel'].keys()
		else:
			nLevel = int(sLvlTmp, 10)
			if nLevel not in self.dsdf['cacheLevel']:
				raise ValueError("Cache Level %d is not defined for datasource '%s'"%(
				                 nLevel, sDsdf))
			self.lLevels = [ nLevel ]
			
		# Check the cache levels defined in the DSDF, make sure we understand
		# and have good round boundaries in storage.
		for nLevel in self.lLevels:
			sBeg = self.lTask[C.CACHE_FIELDS.BEGIN]
			sEnd = self.lTask[C.CACHE_FIELDS.END]
			
			(nRes, sUnits, sPeriod, sParams) = self.dsdf['cacheLevel'][nLevel]
			
			self.dBounds[nLevel] = C.snapToTimeBlks(fLog, self.dsdf, sBeg, sEnd, 
                                                  nLevel)
			
			# make sure that we have some sort of reducer if this cache level
			# isn't set to intrinsic
			if nRes > 0:
				if not self.dsdf[u'reducer']:
					raise E.ServerError("Cannot make a %d %s "%(nRes, sUnits)+\
					"resolution cache, dataset %s is not reducible"%sDsdf)
			

	
	###########################################################################
	def shutdown(self, signum):
		self.bShutdown = True
		if self.proc != None:
			self.proc.send_signal(signum)


	###########################################################################
	def _totalBlks(self):
		""" Figure out how many blocks I have to create so that progress can
		be monitored
		"""
		nBlks = 0
		
		for nLevel in self.lLevels:
		
			dtBeg = self.dBounds[nLevel][0].copy()
			tAdj = self.dBounds[nLevel][1]
			dtEnd = self.dBounds[nLevel][2]
			
			while dtBeg < dtEnd:
				nBlks += 1
				dtBeg.adjust(tAdj[0], tAdj[1], tAdj[2], tAdj[3], tAdj[4], tAdj[5])
				
		return nBlks		
	
	###########################################################################
	def run(self, fLog):
		"""Loop over all cache levels and all block periods making cache files
		"""
				
		sReader = self.dsdf[u'reader']		
		sReducer = self.dsdf[u'reducer']  # Check in init make sure this is
		                                  # not None for non-intrinsic a cache
		
		nTotalBlks = self._totalBlks()
		nDoneBlks = 0
		nSuccessBlks = 0
		
		# Assume that nothing get's processed, until at least one item succeedes
		self.nRetCode = 13
				
		# Outer loop is cache levels since different levels may have different
		# blocking periods.
		for nLevel in self.lLevels:
		
			(nRes, sUnits, sPeriod, sParams) = self.dsdf['cacheLevel'][nLevel]
			sNormParams = D.normalizeParams(sParams)
			if sParams == None:
				sParams = ''
		
			dtBegBlk = self.dBounds[nLevel][0].copy()
			tAdj = self.dBounds[nLevel][1]
			
			dtEnd = self.dBounds[nLevel][2]
						
			while dtBegBlk < dtEnd:
			
				#sys.stderr.write("Beg Block: %s  End All: %s\n"%(dtBegBlk, dtEnd))
			
				(sDir, sFile) = C.getBlockPath(self.dConf, self.dsdf, sNormParams,
				                               nLevel, dtBegBlk)
														 
				# get the time range
				dtEndBlk = dtBegBlk.copy()
				dtEndBlk.adjust(tAdj[0], tAdj[1], tAdj[2], tAdj[3], tAdj[4], tAdj[5])
								
				# Get the output file name, based of the storage scheme, and 
				# shorten up the times to make the logs easier to read.
				sBeg = str(dtBegBlk)[:10]
				sEnd = str(dtEndBlk)[:10]

				if sPeriod == 'hourly' or sPeriod == 'perminute':
					sBeg = str(dtBegBlk)[:16]
					sEnd = str(dtEndBlk)[:16]

				if sPeriod == 'persecond':
					sBeg = str(dtBegBlk)[:19]
					sEnd = str(dtEndBlk)[:19]
				
				sOutFile = pjoin(sDir, sFile)
				sOutTmp = sOutFile + ".tmp"
				
				if not os.path.isdir(sDir):
					os.makedirs(sDir)
				
				rRes = float(nRes)
				if nRes == 0:
					uCmd = u'%s %s %s %s > %s'%(sReader, sBeg, sEnd, sParams, sOutTmp)
				else:
					if sUnits.lower() in ('ms','millisec','millisecond','milliseconds'):
						rRes /= 1000.0

					uCmd = u'%s %s %s %s | %s -b %s %f > %s'%(sReader, sBeg, sEnd, 
			   		     sParams, sReducer, sBeg, rRes, sOutTmp)
				
				fLog.write("   Exec: %s"%uCmd)
				
				rProg = float(nDoneBlks)/float(nTotalBlks)
				self.setProgress(rProg, "Writing: %s"%sFile)
				
				self.proc = subprocess.Popen(
					uCmd, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
					stderr=subprocess.PIPE, close_fds=True
				)
				
				(sStdOut, sStdErr) = self.proc.communicate()
				fLog.write(sStdErr)
				
				# If we get a non-zero return, nuke the temp file, otherwise
				# move the tmp file to the permanent location
				if self.proc.returncode != 0: 
					if os.path.isfile(sOutTmp):
						fLog.write("Error detected in run, cleaning output: %s"%sOutTmp)
						try:
							os.remove(sOutTmp)
						except IOError as e:
							fLog.write("File '%s' could not be removed!"%sOutTmp)
							pass
				else:
					if os.path.isfile(sOutTmp):
						os.rename(sOutTmp, sOutFile)
					else:
						fLog.write("Error detected, expected output file missing!")
						self.proc.returncode = 5
				
				# If anything succedded return a code of 0, otherwise 13
				if self.proc.returncode == 0:
					self.nRetCode = 0
					nSuccessBlks += 1
				
				self.proc = None
				
				dtBegBlk = dtEndBlk
				nDoneBlks += 1
				
		
		self.sStatus = "Successfully processed %d of %d cache blocks"%(
		               nSuccessBlks, nTotalBlks)
		
		return None
		
	
	
	
		

















