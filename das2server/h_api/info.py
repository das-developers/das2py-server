"""Default handler for Heliophysics API info responses, since HAPI requires
a listing of all parameters in a dataset the DSDF must be run over an 
example range if hapi stuff is not pre-generated
"""

import sys
import time
import json
import platform
import os.path
from os.path import join as pjoin

from . import error
from . import cache

##############################################################################
# Fallback HAPI info command line

# For now this is hardcoded, can open it up in the future...

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	fLog.write("\nDas 2.2 HAPI Info handler")
	
	pout("Content-Type: application/json; charset=utf-8")
	
	# HAPI is very strict.  Check the parameters list to make sure that only
	# the allowed parameters are present
	if not error.paramCheck(fLog, 'info', ('id','parameters'), form):
		return 8
		
	if not error.reqCheck(fLog, 'data', ('id',), form):
		return 9
	
	sId = form.getfirst('id', '')
	U.dsdf.checkParam(fLog, 'id', sId)   # Check for shell injection attack stuff
	lId = sId.split(',')
	
	sDsdf = lId[0]
	if len(lId) > 1:
		sSubKey = lId[1]
	else:
		sSubKey = None
	
	sHapiParam = form.getfirst('parameters','')
	U.dsdf.checkParam(fLog, 'parameters', sHapiParam)
	
	sScript = U.webio.getScriptUrl()
	
	if 'DSDF_ROOT' not in dConf:
		error.sendUnkId(fLog, "Server misconfigured, DSDF_ROOT not specified")
		return 10
	
	# See if we can just skip all this stuff and read the cached info response
	# Top level cache directory is hapi, followed by the full dataset id
	# as a path
	sInfoFile = cache.infoCacheFileName(fLog, dConf, sId, sHapiParam)
	if os.path.isfile(sInfoFile):
			
		fLog.write("   Sending Cached HAPI 1.1 Info Message from %s"%sInfoFile)
		pout("Expires: now")
		pout("Status: 200 OK\r\n")
		try:
			fTmp = open(sInfoFile, 'r')
			sJson = fTmp.read()
			sys.stdout.write(sJson)
		except IOError as e:
			fLog.write("   ERROR: %s, falling back to direct reader run", str(e))
			
		# Even if we have a ready file if the cache file is older than the
		# associated DSDF ask for an update anyway	
		sDsdfFile = pjoin(dConf['DSDF_ROOT'], sDsdf) + ".dsdf"
		if os.path.getmtime(sDsdfFile) > os.path.getmtime(sInfoFile):
			fLog.write("   HAPI Info older than DSDF, summiting build task for %s"%sId)
			cache.reqInfoCacheBuild(fLog, dConf, sId, sHapiParam)
		
		return 0
		
	else:
		# Enter info cache request and continue on
		fLog.write("   HAPI Info cache miss, summiting build task for %s"%sId)
		cache.reqInfoCacheBuild(fLog, dConf, sId, sHapiParam)
			
	try:
		dsdf = U.dsdf.Dsdf(sDsdf, dConf, form, fLog)
		dsdf.fillDefaults(dConf)
	except U.errors.DasError as e:
		error.sendDasError(fLog, U, e)
		return 11
		
	# Determine parameters to send to the reader, and the normalized version
	# in case the cache reader is run instead.  The SubSource keys are:
	#  SUB_ID | Comment | Resolution/Interval | Reader Parameters
	sDescription = None
	if u'description' in dsdf:
		sDescription = dsdf[u'description']
		
	if sSubKey:
		lSubSrc = dsdf.subSource(sSubKey)
		if lSubSrc == None:
			error.sendUnkId(fLog, ",".join(lId))
		
		sDescription = lSubSrc[0]
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
		
	sNormParams = U.dsdf.normalizeParams(sRdrParams)
	
	# Check to see if this datasource is compatable with the HAPI protocol
	if bReqInterval and rInterval == 0.0:
		error.sendIncompatable(fLog, "interval readers must define a sub-source "+\
		                       "since they have no intrinsic resolution")
		return 12
	
	if 'rename' in dsdf:
		error.sendIncompatable(fLog, "rename redirect")
		return 12
	
	if 'IGNORE_REDIRECT' not in dConf:
		if (u'server' in dsdf) and (dsdf[u'server'] != sScript):
			error.sendIncompatable(fLog, "cross-server redirect")
			return 13
			
	if not dsdf.isTrue(u'hapi'):
		error.sendUnkId(fLog, ",".join(lId))  # Not an error, just shouldn't be
		                                      # and end point
		return 14
	
	if 'validRange' not in dsdf:
		error.sendIncompatable(fLog, "no valid range provided")
		return 15
			
	lExamples = dsdf.getExamples(fLog)
	if len(lExamples) == 0:
		error.sendIncompatable(fLog, "no example time range provided")
	dEx = lExamples[-1]
	
	(sExBeg, sExEnd) = (dEx['http_params']['start_time'], dEx['http_params']['end_time'])
	fLog.write("   Using range %s to %s for stream information"%(sExBeg, sExEnd))
	
	if (u'qstream' in dsdf) and dsdf.isTrue(u'qstream'):
		error.sendTodo(fLog, "QStream to HAPI Stream conversion not yet implemented")
		return 17
	
	# Looks good, try to get the info...
	
	fLog.write("   Sending HAPI 1.1 Info Message for data source %s"%(",".join(lId)))
		
	# To get the parameters we have to run a reader (at least for a little bit)
	# and pipe the output to the HAPI converter.  See if we can just hit a cache
	# that has exactly the resolution requested and not have to run a reader
	uRdrCmd = None
	if not bReqInterval and U.cache.isExactlyCacheable(dsdf, sNormParams, rResolution):
		
		lMissing = U.cache.missList(fLog,dConf,dsdf,sNormParams,rResolution,sExBeg,sExEnd)
		if (lMissing == None) or len(lMissing) == 0:
			sCacheDir =  pjoin(dConf['CACHE_ROOT'], "data", sDsdf)
			fLog.write("   Cache hit: Reading data from %s"%sCacheDir)
			
			# Cache readers are expected to take the following arguments:
			# 0. The program name (of course)
			# 1. The DSDF file path
			# 2. The dataset cache root (= Cache_ROOT + dsdf_rel_path)
			# 3. The normalized parameter string
			# 4. The begin index point
			# 5. The end index point (exclusive upper bound)
			# 6. The requested resolution		
			uRdrCmd = u"%s %s %s %s '%s' '%s' %.5e"%(
			         dsdf[u'cacheReader'], dsdf.sPath, sCacheDir, sNormParams,
						sExBeg, sExEnd, rResolution
			       )
		else:
			# Cache miss, ask the worker to fix this problem
			fLog.write("   Cache miss: Submitting build task for %d "%len(lMissing)+\
			           "cacheLevel_%02d blocks."%lMissing[0][2])
			U.cache.reqCacheBuild(fLog, dConf, sDsdf, lMissing)
					 
	if uRdrCmd == None:
		# Must of not been cachable or we had a cache miss
		if bReqInterval:
			uRdrCmd = u"%s '%e' '%s' '%s' %s"%(dsdf[u'reader'], rInterval, sExBeg, sExEnd, sRdrParams)
		else:
			uRdrCmd = u"%s '%s' '%s' %s"%(dsdf[u'reader'], sExBeg, sExEnd, sRdrParams)
		
	
	# Here the command options are:
	# 1. Make a header (-i)
	# 2. Don't output data (-n)
	# 3. Use DSDF file for extra information (-d %s)
	# 4. Use parameter select list (%s)
	uHapiCmd = u"das2_hapi -i -n -d %s %s"%(dsdf.sPath, sHapiParam)
	
	uCmd = u"%s | %s"%(uRdrCmd, uHapiCmd)
	
	fLog.write(u"   Exec Host: %s"%platform.node())
	fLog.write(u"   Exec Cmd: %s"%uCmd)
	
	(nRet, sOut, sErr) = U.command.getCmdOutput(fLog, uCmd) # Blocking call
	
	# The hapi converter always triggers an error return because it kills the
	# pipe as soon as it has what in needs.  Don't trigger off of an error
	# return.
	#if nRet != 0:
	#	pout('Status: 500 Internal Server Error\r\n')
	#
	#	dStatus = {'code':1500, 'message': 'Internal Server Error'}
	#	dOut = {"HAPI": "1.1", 'status':dStatus}
	#	dStatus['x_reason'] = sErr.replace('\\', '\\\\').replace('"','\"') 
	#	
	#	sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
	#	sys.stdout.write(sOut)
	#	sys.stdout.write('\r\n')
	#	return 0
		
	
	# If couldn't parse the converter's output ...
	try:
		dOut = json.loads(sOut, encoding="utf-8")
	except ValueError:
		pout('Status: 500 Internal Server Error\r\n')
		dStatus = {'code':1500, 'message': 'Internal Server Error'}
		dOut = {"HAPI": "1.1", 'status':dStatus}
		dStatus['x_reason'] = "Couldn't decode JSON data from sub-command"
		sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
		sys.stdout.write(sOut)
		sys.stdout.write('\r\n')
		return 13
		
		
	# Okay, looks like it worked
	sTmp = ''
	if sHapiParam and (len(sHapiParam) > 0):
		sTmp = "&parameters=%s"%sHapiParam
		
	# Provide a Das2 link in case the client is able to use these
	dOut['x_links'] = [ {
		"tag":"das2Stream",
		"description":"Access to the upstream Das2 data source for this HAPI endpoint",
		"mime-type": "application/vnd.das2.das2stream",
		"url":"%s?server=dataset?dataset=%s&start_time=%s&end_time=%s"%(
               sScript, sId, sExBeg, sExEnd)
	}]
		
	# Change the description to match the sub source if needed
	if sDescription:
		fLog.write("   Setting description to: \"%s\""%sDescription)
		dOut['description'] = sDescription
		
	pout("Expires: now")
	pout("Status: 200 OK\r\n")
		
	sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
	return 0
