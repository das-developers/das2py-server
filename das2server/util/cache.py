"""Utilities to support Server-Side caching"""

# make py2 code safer by preventing relative imports
from __future__ import absolute_import

import sys
import time

import os.path
from os.path import join as pjoin

if not sys.platform.lower().startswith('win'):
	import pwd

import das2

from . import task as T
from . import misc as M
from . import errors as E


##############################################################################

def isCacheable(dsdf, sNormParam, rReqRes):
	"""Inspect the cacheLevel parameter in the dsdf object and see if it
	is possible for a dataset to exist that meets the given parameter set
	and resolution level.
	
	dsdf - A dsdf object with default filled in, has dictionary like properties
	sNormParam - A normalized parameter string for the reader
	rRes - The requested resolution
	"""
	
	if len(dsdf['cacheLevel']) == 0:
		return False
	
	for nLevel in dsdf['cacheLevel']:
		(rRes, sUnit, sPeriod, sParams) = dsdf['cacheLevel'][nLevel]
		if sUnit == 'ms':
			rRes /= 1000.0
		
		if rReqRes < rRes:
			continue
		
		if M.normalizeOpts(sParams) != sNormParam:
			continue
	
		return True
	
	return False
	
	
def isExactlyCacheable(dsdf, sNormParam, rReqRes):
	"""Inspect the cacheLevel parameter in the dsdf object and see if it
	is possible for a dataset to exist that has exactly the given resolution
	
	dsdf - A dsdf object with default filled in, has dictionary like properties
	sNormParam - A normalized parameter string for the reader
	rRes - The requested resolution
	"""
	
	if len(dsdf['cacheLevel']) == 0:
		return False
	
	for nLevel in dsdf['cacheLevel']:
		(rRes, sUnit, sPeriod, sParams) = dsdf['cacheLevel'][nLevel]
		if sUnit == 'ms':
			rRes /= 1000.0
		
		# If the params don't match ignore the request
		if M.normalizeOpts(sParams) != sNormParam:
			continue 
		
		# If we have non-zero values see if they are close enough
		if (rRes != 0.0) and (rReqRes != 0.0):
			if (abs(rRes - rReqRes) / rRes) > 0.0001:
				continue	
		
		# One of them is zero, look for exact match
		if rRes != rReqRes:
			continue
		
		# All checks pass		
		return True
	
	return False

	
	
##############################################################################
# Little Enum to help keep caching job field numbers straight

class CACHE_FIELDS(T.JOB_FIELDS):
	DATASET = 7
	BEGIN = 8
	END = 9
	LEVEL = 10
	
	# This is for a possible future version of the cache builder that runs the
	# same as this one but produces something other than just averages over 
	# time bins.
	#TRANSFORM = 11
	
	REQ_BEGIN = 11
	STATUS = 12
	PROGRESS = 13

	LEN_INITAL = 11
	LEN_IN_PROC = 14
	
	
##############################################################################

def snapToTimeBlks(fLog, dsdf, sBeg, sEnd, nLevel, bCoverage=False):
	"""Given a dsdf object which has fully initialize defaults and a 
	cache level, stap begin and end times for cache generation to 
	cache block boundaries.
	
	Returns a three tuple of (dtBeg, tAdj, dtEnd)
	
	dtBeg - A DasTime object for the begining of the cache period
	
	tAdj  - A tuple of time adjustments needed to step from one file start
	        time to the next.  This has the format 
			(nYear, nMonth, nDay, nHour, nMinute, nSec)
			  
	dtEnd - A DasTime object for the ending of the cache period
	"""
	
	(nRes, sUnits, sPeriod, sParams) = dsdf['cacheLevel'][nLevel]
	
	sUnit = None
	if nRes != 0: 
		if sUnits.lower() in ('sec', 's','second','seconds'):
			sUnit = 's'
		elif sUnits.lower() in ('ms', 'millisec', 'millisecond', 'milliseconds'):
			sUnit = 'ms'
		else:
			raise E.TodoError("Handling resolution in units other than seconds"+\
		                " or milliseconds is not yet implemented")
	
	sBeg = sBeg
	sEnd = sEnd
			
	dtB = das2.DasTime(sBeg)
	dtE = das2.DasTime(sEnd)

	if sPeriod == 'persecond':
		fFrac = dtE.sec() - int(dtE.sec())
		if fFrac > 0.0:
			dtE.adjust(0, 0, 0, 0, 0, 1)

		return (
			das2.DasTime(dtB.year(), dtB.month(), dtB.dom(), dtB.hour(),
			             dtB.minute(), dtB.sec()),
			(0, 0, 0, 0, 0, 1),
			das2.DasTime(dtE.year(), dtE.month(), dtE.dom(), dtE.hour(),
			            dtE.minute(), dtE.sec())
		)
	
	elif sPeriod == 'perminute':
		if dtE.sec() > 0.0:
			dtE.adjust(0, 0, 0, 0, 1)

		return (
			das2.DasTime(dtB.year(), dtB.month(), dtB.dom(), dtB.hour(), dtB.minute()),
			(0, 0, 0, 0, 1, 0),
			das2.DasTime(dtE.year(), dtE.month(), dtE.dom(), dtE.hour(), dtE.minute())
		)

	elif sPeriod == 'hourly':
		if dtE.minute() > 0 or dtE.sec() > 0.0:
			dtE.adjust(0, 0, 0, 1)
					
		return (
			das2.DasTime(dtB.year(), dtB.month(), dtB.dom(), dtB.hour()),
			(0, 0, 0, 1, 0, 0),
			das2.DasTime(dtE.year(), dtE.month(), dtE.dom(), dtE.hour())
		)
				
	elif sPeriod == 'daily':
		if dtE.hour() > 0 or dtE.minute() > 0 or dtE.sec() > 0.0:
			dtE.adjust(0, 0, 1, 0)
		
		return (
			das2.DasTime(dtB.year(), dtB.month(), dtB.dom()),
			(0, 0, 1, 0, 0, 0),
			das2.DasTime(dtE.year(), dtE.month(), dtE.dom())
		)

	elif sPeriod == 'monthly':	
		if dtE.dom() > 1 or dtE.hour() > 0 or dtE.minute() > 0 or dtE.sec() > 0.0:
			dtE.adjust(0, 1, 0, 0)

		return (
			das2.DasTime(dtB.year(), dtB.month(), 1),
			(0, 1, 0, 0, 0, 0),
			das2.DasTime(dtE.year(), dtE.month(), 1)
		)

	else:
		raise E.ServerError("Unknown storage period %s, in DSDF %s"%(
		                    sPeriod, sDsdf))

##############################################################################
def getBlockPath(dConf, dsdf, sNormParam, nLevel, dtBeg, bCoverage=False):
	
	sDsdf = dsdf.sName
	
	sCacheRoot = pjoin(dConf['CACHE_ROOT'], "data")
	
	(nRes, sUnits, sPeriod, sParams) = dsdf['cacheLevel'][nLevel]
	
	# Get the resolution stub
	if nRes > 0:
		if sUnits != None and len(sUnits) > 0:
			sRes = "bin-%d%s"%(nRes, sUnits)
		else:
			sRes = "bin-%d"%nRes
	else:
		sRes = 'intrinsic'

	sExt = 'd2s'
	if dsdf[u'qstream']:
		sExt = 'qds'
				
	# Get the output directory and file name based of the storage scheme
	# and time period.
	
	if sPeriod == 'persecond':
		sDir = pjoin(sCacheRoot, sDsdf, sNormParam, sRes,
			     "%04d"%dtBeg.year(),"%02d"%dtBeg.month(),
			     "%02d"%dtBeg.dom(),"%02d"%dtBeg.hour(),  
			     "%02d"%dtBeg.minute())

		sFile = "%04d-%02d-%02dT%02d-%02d-%02.0f_%s.%s"%(dtBeg.year(),
			dtBeg.month(), dtBeg.dom(), dtBeg.hour(),
			dtBeg.minute(), dtBeg.sec(), sRes, sExt)
			

	elif sPeriod == 'perminute':
		sDir = pjoin(sCacheRoot, sDsdf, sNormParam, sRes,
			     "%04d"%dtBeg.year(),"%02d"%dtBeg.month(),
			     "%02d"%dtBeg.dom(),"%02d"%dtBeg.hour())

		sFile = "%04d-%02d-%02dT%02d-%02d_%s.%s"%(dtBeg.year(),
			dtBeg.month(), dtBeg.dom(), dtBeg.hour(),
			dtBeg.minute(), sRes, sExt)

	elif sPeriod == 'hourly':
		sDir = pjoin(sCacheRoot, sDsdf, sNormParam, sRes, 
		             "%04d"%dtBeg.year(),"%02d"%dtBeg.month(),
		             "%02d"%dtBeg.dom())
		
		sFile = "%04d-%02d-%02dT%02d_%s.%s"%(dtBeg.year(),
		        dtBeg.month(), dtBeg.dom(), dtBeg.hour(),
				  sRes, sExt)
									  				
	elif sPeriod == 'daily':
		sDir = pjoin(sCacheRoot, sDsdf, sNormParam, sRes, 
		             "%04d"%dtBeg.year(),"%02d"%dtBeg.month())
		
		sFile = "%04d-%02d-%02d_%s.%s"%(dtBeg.year(),
		        dtBeg.month(), dtBeg.dom(), sRes, sExt)
				
	elif sPeriod == 'monthly':
		sDir = pjoin(sCacheRoot, sDsdf, sNormParam, sRes, 
		             "%04d"%dtBeg.year())
		
		sFile = "%04d-%02d_%s.%s"%(dtBeg.year(), dtBeg.month(),
		                           sRes, sExt)
	else:
		assert(False)

	return (sDir, sFile)

##############################################################################

def missList(fLog, dConf, dsdf, sNormParam, rRes, sBeg, sEnd, bCoverage=True):
	"""Get a list of all block periods that are not present in the disk
	cache for a particular dataset.  Arguments are:

	  rRes - The resolution in seconds (may be fractional seconds)
	
	Return value is a list of the following tuples:
	
	     (sBegIdx, sEndIdx, nCacheLevel)
		  
	Here sBegIdx and sEndIdx are times, but when we move to Das 2.3 they
	will need to be a general index.
	"""
		
	# Rank levels that match our normalized parameter string in order from
	# highest resolution to lowest (lowest rRes to highest rRes) .
	dRes = {}
	for nLevel in dsdf['cacheLevel']:
		(nRes, sUnits, sMethod, sParams) = dsdf['cacheLevel'][nLevel]
		if sNormParam == M.normalizeOpts(sParams):
			fRes = float(nRes)
			if sUnits == 'ms':
				fRes /= 1000.0
			dRes[fRes] = nLevel
	
	if len(dRes) == 0:
		raise E.ServerError("missList called for data that are not cacheable")
	
	lRes = list(dRes.keys())
	lRes.sort()
	
	iRes = 0
	for iKey in range(0, len(lRes) - 1):
		if lRes[iKey + 1] > rRes:
			break
		iRes += 1
	
#	fLog.write("dRes: %s"%dRes)
	
	nUseLevel = dRes[lRes[iRes]]
	
	(dtBeg, tAdj, dtEnd) = snapToTimeBlks(fLog, dsdf, sBeg, sEnd, nUseLevel)
	
	lMissing = []
	while dtBeg < dtEnd:
		#fLog.write(" tAdj = %s\n"%str(tAdj))
		#fLog.write(  "   Checking for: %s %s %s"%(dsdf.sName, sNormParam, dtBeg))
		(sDir, sFile) = getBlockPath(dConf, dsdf, sNormParam, nUseLevel, dtBeg)
		#fLog.write(" Need cache block %s/%s"%(sDir, sFile))
		dtEndBlk = dtBeg.copy()
		dtEndBlk.adjust(tAdj[0],tAdj[1],tAdj[2],tAdj[3],tAdj[4],tAdj[5])
		#fLog.write(" dtEndBlk = %s"%str(dtEndBlk))
		
		if not os.path.isfile(pjoin(sDir, sFile)):
			# Trim  the time strings based on the period
			nSz = 10
			if dsdf['cacheLevel'][nUseLevel][2] == 'hourly':
				nSz = 16
			elif dsdf['cacheLevel'][nUseLevel][2] == 'perminute':
				nSz = 16
			elif dsdf['cacheLevel'][nUseLevel][2] == 'persecond':
				nSz = 19
			lMissing.append( (str(dtBeg)[:nSz], str(dtEndBlk)[:nSz], nUseLevel) )
		
		dtBeg = dtEndBlk
			
	return lMissing

##############################################################################

# 
# From user 'tgambin' at StackOverflow --Thanks!
def find_nth(haystack, needle, n):
    start = haystack.find(needle)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start+len(needle))
        n -= 1
    return start


def reqCacheBuild(fLog, dConf, sDsdf, lToBuild, bCoverage=False):
	"""
	Request that one or more cache areas be built (or rebuilt)
	
	lToBuild is a list of three tuples, each of which contains the
	following:
	
	   (sBeg, sEnd, nCacheLevel)
		
	For each tuple if the job is already listed in das2_todo, it's not
	re-added.  This isn't a complete solution since jobs are likely 
	in the process of being worked on, but it least this means we won't
	sumbit more duplicate jobs than there are worker processes
	"""
	# Try to get the broker, if you can't just ignore the request
	broker = T.getBroker(fLog, dConf)
	if broker == None:
		fLog.write("   WARNING: Work queue unreachable, dropping cache request")
		return
		
	# See what jobs are aready on the build list, only need to compare against
	# the Job-Type, DSDF, Start, Stop and Level keys.
	lTmp = broker.lrange('das2_todo', 0, 1)
	lWaiting = []
	for sTmp in lTmp:
		if sTmp.find('TASK_CACHE') > -1:
			i = find_nth(sTmp, '|', CACHE_FIELDS.DATASET)
			if i > -1:
				lWaiting.append( sTmp[i+1:] ) 
		
	for (sBeg, sEnd, nLevel) in lToBuild:
	
		lTask = ['']*CACHE_FIELDS.LEN_INITAL
		
		if 'SERVER_NAME' in os.environ:
			lTask[1] = lTask[1] + os.environ['SERVER_NAME']
		if 'SCRIPT_NAME' in os.environ:
			lTask[1] = "%s%s"%(lTask[1], os.environ['SCRIPT_NAME'])
		if 'REMOTE_ADDR' in os.environ:
			lTask[3] = lTask[3] + os.environ['REMOTE_ADDR']
		
		if sys.platform.lower().startswith('win'):
			lTask[5] = os.environ['USERNAME']
		else:
			lTask[5] = pwd.getpwuid( os.getuid() )[0]
			
		lTask[6] = 'TASK_CACHE'
		lTask[CACHE_FIELDS.DATASET] = sDsdf
		lTask[CACHE_FIELDS.BEGIN] = sBeg
		lTask[CACHE_FIELDS.END] = sEnd
		lTask[CACHE_FIELDS.LEVEL] = "%d"%nLevel
		
		sJobId = '|'.join(lTask[CACHE_FIELDS.DATASET:])
		if sJobId in lWaiting:
			fLog.write('   Cache miss: Job %s already in queue, dropping cache request'%sJobId)
			return 			
		
		lTask[0] = T.curTime()
		sTask = '|'.join(lTask)
		
		try:
			broker.lpush('das2_todo', sTask)
		except E.ServerError as e:
			fLog.write('ERROR: %s'%str(e))
	
	return None

# ########################################################################## #
# Cache Solver #

def cacheCmdSolver(fLog, dConf, dDefault, dSrc, dParams):
	"""
	"""

	pass

