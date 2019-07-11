"""Handler for hapi_info_cache jobs"""

import os
import os.path
import subprocess
import json

from os.path import join as pjoin
from os.path import dirname as dname

import das2server.util.dsdf as D
import das2server.util.task as T
import das2server.util.errors as E
import das2server.util.command as C

import cache  # This is the hapi subsystem cache file, not the Das2 one


##############################################################################

class Task(T.TaskHandler):
	"""Handle info caching for hapi
	
	1. See if we have a valid task (data source must be HAPI compatable)
	2. Regenerate the info file assuming all parameters are selected
	
	
	"""
	
	###########################################################################
	def __init__(self, dConf, broker, sQueue, iJobIdx, sTask, fLog):
	
		# Call parent, it defines a slew of variables including the broken down
		# task description list
		T.TaskHandler.__init__(self, dConf, broker, sQueue, iJobIdx, sTask, fLog)
		
		self.proc    = None    # The current sub-shell process
		self.uCmd    = None    # The command we are going to run, or are currently running
		self.sOutPath = None   # The file we are going to write
		
		if len(self.lTask) < cache.HINFO_CACHE.HPARAMS + 1:
			raise E.QueryError(
				"Expected %d fields for HAPI Info request cache tasks, entry has %d"%(
				cache.HINFO_CACHE.HPARAMS + 1, len(self.lTask))
			)
		
		# Check that the cache root directory exists
		if not os.path.isdir( self.dConf['CACHE_ROOT'] ):
			raise E.ServerError("Cache Root directory missing: %s"%self.dConf['CACHE_ROOT'])
			         
		sCacheRoot = pjoin(dConf['CACHE_ROOT'], 'hapi')
		
		sId = self.lTask[cache.HINFO_CACHE.ID]
		sHParams = self.lTask[cache.HINFO_CACHE.HPARAMS]
		
				
		# Check for shell injection attack stuff
		sMsg = "field looks like a shell-injection attack"
		if not D.checkParam(fLog, 'id', sId): 
			raise E.QueryError("Task ID %s: '%s'"%(sMsg, sId))
		
		if not D.checkParam(fLog, 'parameters', sHParams):
			raise E.QueryError("Task PARAMETERS %s: '%s'"%(sMsg, sId))
		
		# Get and check the DSDF
		lId = sId.split(',')
		sDsdf = lId[0]
		if len(lId) > 1:
			sSubKey = lId[1]
		else:
			sSubKey = None
		
		dsdf = D.Dsdf(sDsdf, self.dConf, None, fLog)
		self.sDescription = None
		if u'description' in dsdf:
			self.sDescription = dsdf[u'description']
				
		dsdf.fillDefaults(self.dConf)
		
		# Determine parameters to send to the reader, and the normalized version
		# in case the cache reader is run instead.  The SubSource keys are:
		#  SUB_ID | Comment | Resolution/Interval | Reader Parameters
		if sSubKey:
			lSubSrc = dsdf.subSource(sSubKey)
			if lSubSrc == None:
				raise E.QueryError("HAPI ID %s does not refer to valid subsource for DSDF %s"%(
				             sId, sDsdf))
			
			self.sDescription = lSubSrc[0]
			rTmp = lSubSrc[1]
			sRdrParams = lSubSrc[2]
		else:
			sRdrParams = ''
			rTmp = 0.0
	
		bReqInterval = dsdf.isTrue('requiresInterval')
		
		if bReqInterval:
			rInterval = rTmp        #  Very different uses...
		else:
			rResolution = rTmp      #  for this variable
		
		sNormParams = D.normalizeParams(sRdrParams)
		
		
		# Check to see if this datasource is compatable with the HAPI protocol
		if bReqInterval and rInterval == 0.0:
			raise E.QueryError("%s is not HAPI 1.1 compatible, interval readers "%sId+\
			                   "must define a sub-source since they have no "+\
									 "intrinsic resolution")
	
		if 'rename' in dsdf:
			raise E.QueryError("% is not HAPI 1.1 compatible, rename redirect encountered"%sId)
	
		if 'IGNORE_REDIRECT' not in dConf:
			if (u'server' in dsdf) and (dsdf[u'server'] != sScript):
				raise E.QueryError("%s is not HAPI 1.1 compatible cross-server redirect"%sId)
			
		if (u'hapi' in dsdf) and (not dsdf.isTrue(u'hapi')):
			# Not an error, just shouldn't be an end point
			raise E.QueryError("HAPI support not enabled for %s"%sId)  
	
		if 'validRange' not in dsdf:
			raise E.QueryError("%s is not HAPI 1.1 compatible, no valid range provided"%sId)
			
		lExamples = dsdf.getExamples(fLog)
		if len(lExamples) == 0:
			raise E.ServerError("no example time range provided")
		dEx = lExamples[-1]
		(sExBeg, sExEnd) = (dEx['params']['time.min'], dEx['params']['time.max'])
		fLog.write("   Using range %s to %s for stream information"%(sExBeg, sExEnd))
	
		if (u'qstream' in dsdf) and dsdf.isTrue(u'qstream'):
			raise E.TodoError("QStream to HAPI Stream conversion not yet implemented")
		
		
		# Don't use the cache for this, we're not in real-time mode
		if bReqInterval:
			uRdrCmd = u"%s '%e' '%s' '%s' %s"%(dsdf[u'reader'], rInterval, sExBeg, sExEnd, sRdrParams)
		else:
			uRdrCmd = u"%s '%s' '%s' %s"%(dsdf[u'reader'], sExBeg, sExEnd, sRdrParams)
		
		# Here the command options are:
		# 1. Make a header (-i)
		# 2. Don't output data (-n)
		# 3. Use DSDF file for extra information (-d %s)
		# 4. Use parameter select list (%s)
		uHapiCmd = u"das2_hapi -i -n -d %s %s"%(dsdf.sPath, sHParams)
			
		self.uCmd = u"%s | %s"%(uRdrCmd, uHapiCmd)
		
		self.sOutPath = cache.infoCacheFileName(fLog, dConf, sId, sHParams)
		
		# If the dsdf has a server=tag in it, add in a link to the equivalent das2 service
		self.sDas2Url = None
		if (u'server' in dsdf) and (len(dsdf[u'server']) > 10):
			self.sDas2Url = u'%s?server=dataset?dataset=%s&start_time&end_time=%s&params="%s'%(
			                dsdf[u'server'], sExBeg, sExEnd, sRdrParams
			                )
		
	###########################################################################
	def shutdown(self, signum):
		self.bShutdown = True
		if self.proc != None:
			self.proc.send_signal(signum)


	###########################################################################
	def run(self, fLog):
		"""Basically this is the same code as the info.py request handler it
		just is not triggered from apache so none of the CGI stuff is available
		"""	
		# Assume it doesn't work, until we know it does
		self.nRetCode = 13
		
		fLog.write("   Exec: %s"%self.uCmd)
		
		self.proc = subprocess.Popen(
			self.uCmd, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
			stderr=subprocess.PIPE, close_fds=True
		)
				
		(sStdOut, sStdErr) = self.proc.communicate()
		fLog.write(sStdErr)
		
		if self.proc.returncode != 0:
			fLog.write(u"Error detected in command %s"%self.uCmd)
			self.nRetCode = self.proc.returncode
			return
			
			
		sDir = dname(self.sOutPath)
		if not os.path.isdir(sDir):
			os.makedirs(sDir)
			
		# Read the output in as a JSON object (may throw and that's okay)
		dOut = json.loads(sStdOut, encoding="utf-8")
		
		if self.sDas2Url != None:
			dOut['x_links'] = [
				{
				"tag":"das2Stream",
				"description":"Access to the upstream Das2 data source for this HAPI endpoint",
				"mime-type": "application/vnd.das2.das2stream",
				"url":self.sDas2Url
				}
			]
			
		# Override the description to match the sub source if needed
		if self.sDescription:
			dOut['description'] = self.sDescription
		
		
		sJsonOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
				
		fOut = file(self.sOutPath, 'wb')
		fOut.write(sJsonOut)
		fOut.close()
		fLog.write("Cache file %s written"%self.sOutPath)
		self.nRetCode = 0
			
		self.proc = None
	
		
