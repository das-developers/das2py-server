"""Utilities to assist with caching h-api requests"""

import os
import sys
from os.path import join as pjoin

if not sys.platform.lower().startswith('win'):
	import pwd

import das2server.util.task as T

# Task Strings for hapi server stuff

g_sInfoCache = "HAPI_INFO_CACHE"


##############################################################################
# just for testing
def perr(sOut):
	sys.stderr.write(sOut)
	sys.stderr.write('\r\n')


##############################################################################

def infoCacheFileName(fLog, dConf, sId, sHParams):
	# Convert IDs to paths as follows:
	#
	# ('VGR1/PWS/Spectra', None)  -> $CACHE_ROOT/hapi/VGR1/PWS/Spectra.json
	# 
	# ('VGR1/PWS/Spectra', 'peaks,avg') 
	#  -> 
	#    $CACHE_ROOT/hapi/VGR1/PWS/Spectra_avg_peaks.json (HParams in sort order)
	#
	# ('Juno/WAV/Spectra,LFRL', None) 
	#  -> 
	#    $CACHE_ROOT/hapi/Juno/WAV/Spectra_LFRL.json
	#
	# Notice selecting a sub-source is the same thing as selecting just
	# a single parameter.  This is because Das2 does not allow two 
	# datasets to participate in a join unless they have the same name.
	# (Das2 has too many implicit structure assumptions)
	#
	# The DSDF is compensating here by introducing sub-sources, but really
	# all items in the stream should have an ID by which you can reference
	# them regardless of thier join status.  Adding a new item "id" would
	# be a nice way to do this:
	#
	#   now:  <yscan name="join_key" ... />
	#
	#   future:  <yscan join="survey_e" id="lfrl" ... />
	#
	# would be a nice way to do this.

	if 'CACHE_ROOT' not in dConf:
		return None
	
	sPath = pjoin(dConf['CACHE_ROOT'], 'hapi')
	
	lId = sId.split('/')	
	if len(lId) > 1:
		sIdSubDir = os.sep.join( lId[:-1] )
		#fLog.write("   INFO: lId = %s, sPath = %s, sIdSubDir = %s"%(lId, sPath, sIdSubDir))
		sPath = pjoin(sPath, sIdSubDir)
	
	sDataSet = lId[-1]
	
	# Now see if a sub-source is present
	lSubSet = []
	if sDataSet.find(',') != -1:
		lDataSet = [s.strip() for s in sDataSet.split(',')]
		lSubSet = lDataSet[1:]
		sDataSet = lDataSet[0]
	
	# Now see if params are present
	if (not (sHParams is None)) and (len(sHParams) > 0) :
		lHParams = [s.strip() for s in sHParams.split(',')]
		lSubSet += lHParams
	
	if len(lSubSet) > 0:
		lSubSet.sort()
		sSubSet = '_'.join(lSubSet)
		sDataSet = "%s-%s"%(sDataSet, sSubSet)
	
	sPath = pjoin(sPath, "%s.json"%sDataSet)
	
	fLog.write("   INFO: Cache file for id='%s:%s' is %s"%(sId, sHParams, sPath))
	return sPath	


##############################################################################
# Little Enum to help keep hapi-info-cache job field numbers straight
#
# Now we have to cache the particular parameters that they asked about
# Uggh.  This required feature of hapi is a real pain.  I think the point
# of hapi is to put all the work on the server creators.  Good luck with
# that Goddard, you're going to need it.  They should do this stuff on
# the client and only require of the server what which is absolutly needed,
# such as reducing the network load.
#

class HINFO_CACHE(T.JOB_FIELDS):
	ID = 7
	HPARAMS = 8
	

##############################################################################

# From user 'tgambin' at StackOverflow --Thanks!
def find_nth(haystack, needle, n):
    start = haystack.find(needle)
    while start >= 0 and n > 1:
        start = haystack.find(needle, start+len(needle))
        n -= 1
    return start
	 
def reqInfoCacheBuild(fLog, dConf, sId, sHParams):
	"""
	Request that an hapi datasource have it's info cached for a particular
	arrangement of parameters.  If lParams is null then this is the same
	as asking for the cache for no params.
	"""

	# Try to get the broker, if you can't just ignore the request
	broker = T.getBroker(fLog, dConf)
	if broker == None:
		fLog.write("   WARNING: Work queue unreachable, dropping cache request")
		return
		
	# See what jobs are aready on the build list, only need to compare against
	# the Job-Type, and ID and params fields
	lTmp = broker.lrange('das2_todo', 0, 1)
	lWaiting = []
	for sTmp in lTmp:
		if sTmp.find(g_sInfoCache) > -1:
			i = find_nth(sTmp, '|', HINFO_CACHE.ID)
			if i > -1:
				lWaiting.append( sTmp[i+1:] )  # Already has the pipe embedded
	
	# make sure the params string is in sort order
	lHParams = [s.strip() for s in sHParams.split(',')]
	lHParams.sort()
	sHParams = ','.join(lHParams)
	
	sJobId = '%s|%s'%(sId, sHParams)
	
	if sJobId in lWaiting:
		fLog.write('   Info cache miss: Job %s already in queue, dropping cache request')
		return None
		
	lTask = ['']*(HINFO_CACHE.HPARAMS+1)
	
	if os.environ.has_key('SERVER_NAME'):
		lTask[HINFO_CACHE.REQUESTER] = lTask[HINFO_CACHE.REQUESTER] + os.environ['SERVER_NAME']

	if os.environ.has_key('SCRIPT_NAME'):
		lTask[HINFO_CACHE.REQUESTER] = "%s%s"%(lTask[HINFO_CACHE.REQUESTER], os.environ['SCRIPT_NAME'])

	if os.environ.has_key('REMOTE_ADDR'):
		lTask[HINFO_CACHE.RMTREQ] = lTask[HINFO_CACHE.RMTREQ] + os.environ['REMOTE_ADDR']
		
	if sys.platform.lower().startswith('win'):
		lTask[HINFO_CACHE.USER] = os.environ['USERNAME']
	else:
		lTask[HINFO_CACHE.USER] = pwd.getpwuid( os.getuid() )[0]
			
	lTask[HINFO_CACHE.CATEGORY] = g_sInfoCache
	lTask[HINFO_CACHE.ID] = sId
	if sHParams != None:
		lTask[HINFO_CACHE.HPARAMS] = sHParams
	else:
		lTask[HINFO_CACHE.HPARAMS] = ""

	lTask[0] = T.curTime()
	sTask = '|'.join(lTask)

	try:
		broker.lpush('das2_todo', sTask)
	except E.ServerError, e:
		fLog.write('ERROR: %s'%str(e))
	
	return None






























