"""Default handler for Heliophysics API info responses, since HAPI requires
a listing of all parameters in a dataset the DSDF must be run over an 
example range if hapi stuff is not pre-generated
"""

import sys
import time
import json
import platform
from os.path import basename as bname
from os.path import join as pjoin

import error

##############################################################################
# Fallback HAPI info command line

# For now this is hardcoded, can open it up in the future...


##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

##############################################################################
def _sendBadFormat(fLog, sReqFmt):
	sys.stdout.write('Status: 400 Bad Request\r\n')
	
	fLog.write("Output type '%s' not supported for this server"%sReqFmt)
	dStatus = {'message': "Bad request - unsupported output format",
	           'code':1409 }
	dOut = {"HAPI": "1.1", 'status':dStatus}
	sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
	pout(sOut)

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	fLog.write("\nDas 2.2 HAPI Info handler")
	
	# HAPI is very strict.  Check the parameters list to make sure that only
	# the allowed parameters are present
	tLegal = ('id','time.min','time.max','parameters','include','format')
	if not error.paramCheck(fLog, 'data', tLegal, form, True):
		return 8
		
	if not error.reqCheck(fLog, 'data', ('id','time.min', 'time.max'), form, True):
		return 9
		
	sTmp = form.getfirst('format', 'csv')
	if sTmp.lower() != 'csv':
		_sendBadFormat(fLog, sReqFmt, True)
	
	sId = form.getfirst('id', '')
	lId = sId.split(',')
	sDsdf = lId[0]
	if len(lId) > 1:
		sSubKey = lId[1]
	else:
		sSubKey = None
		
	sBeg = form.getfirst('time.min','')
	sEnd = form.getfirst('time.max','')
	
	bHeader = False
	if form.getfirst('include', '') == 'header':
		bHeader = True
	
	sHapiParam = form.getfirst('parameters','')
	U.dsdf.checkParam(fLog, 'parameters', sHapiParam)
	
	sScript = U.io.getScriptUrl()
	
	if 'DSDF_ROOT' not in dConf:
		error.sendUnkId(fLog, "Server misconfigured, DSDF_ROOT not specified", True)
		return 10
			
	try:
		dsdf = U.dsdf.Dsdf(sDsdf, dConf, form, fLog)
		dsdf.fillDefaults(dConf)
	except U.errors.DasError as e:
		error.sendDasError(fLog, U, e, True)
		return 11
	
	# Determine parameters to send to the reader, and the normalized version
	# in-case the cache reader is run instead
	#  SUB_ID | Comment | Resolution/Interval | Reader Parameters
	if sSubKey:
		lSubSrc = dsdf.subSource(sSubKey)
		if lSubSrc == None:
			error.sendUnkId(fLog, ",".join(lId))
			
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
	
	# Handle authorization
	if 'readAccess' in dsdf:
		nRet = U.auth.authorize(dConf, fLog, form, sDsdf, dsdf['readAccess'])
		if nRet != U.auth.AUTH_SUCCESS:
			error.sendIncompatable(fLog, "Data source requires authorization")
			return 12
	
	
	# Check to see if this datasource is compatable with the HAPI protocol
	if bReqInterval and rInterval == 0.0:
		error.sendIncompatable(fLog, "interval readers must define a sub-source "+\
		                       "since they have no intrinsic resolution")
		return 12
	
	if 'rename' in dsdf:
		error.sendIncompatable(fLog, "rename redirect", True)
		return 12
	
	if 'IGNORE_REDIRECT' not in dConf:
		if (u'server' in dsdf) and (dsdf[u'server'] != sScript):
			error.sendIncompatable(fLog, "cross-server redirect", True)
			return 13
			
	if not dsdf.isTrue(u'hapi'):
		error.sendUnkId(fLog, ",".join(lId), True)  # Not an error, just shouldn't be
		                                            # an end point
		return 14
	
	# Only matters if headers were requested.
	if bHeader and ('validRange' not in dsdf):
		error.sendIncompatable(fLog, "no valid range provided", True)
		return 15
	
	if (u'qstream' in dsdf) and dsdf.isTrue(u'qstream'):
		error.sendTodo(fLog, 
		               "QStream to HAPI Stream conversion not yet implemented", 
							True)
		return 17
	
	# Looks good, try to get the info...
	
	fLog.write("   Sending HAPI 1.1 Info Message for data source %s"%(",".join(lId)))
	
	# To get the parameters we have to run a reader (at least for a little bit)
	# and pipe the output to the HAPI converter.  See if we can just hit the
	# intrinsic resolution cache and not have to run the reader
	uRdrCmd = None
	if not bReqInterval and U.cache.isExactlyCacheable(dsdf, sNormParams, rResolution):
		lMissing = U.cache.missList(fLog,dConf,dsdf,sNormParams,rResolution,sBeg,sEnd)
		if (lMissing == None) or len(lMissing) == 0:
			sCacheDir =  pjoin(dConf['CACHE_ROOT'], 'data', sDsdf)
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
						sBeg, sEnd, rResolution
			       )
		else:
			# Cache miss, ask the worker to fix this problem
			fLog.write("   Cache miss: Submitting build task for %d "%len(lMissing)+\
			           "cacheLevel_%02d blocks."%lMissing[0][2])
			U.cache.reqCacheBuild(fLog, dConf, sDsdf, lMissing)
					 
	if uRdrCmd == None:
		# Must of not been cachable or we had a cache miss
		if bReqInterval:
			uRdrCmd = u"%s '%e' '%s' '%s' %s"%(dsdf[u'reader'], rInterval, sBeg, sEnd, sRdrParams)
		else:
			uRdrCmd = u"%s '%s' '%s' %s"%(dsdf[u'reader'], sBeg, sEnd, sRdrParams)

	
	# Here the command options are:
	# 1. Maybe make a header (-i)
	# 2. Don't output data (-n)
	# 3. Use DSDF file for extra information (-d %s)
	# 4. Use parameter select list (%s)
	sOpt = ""
	if bHeader:
		sOpt = " -i -d %s"%dsdf.sPath
	
	# HAPI datasources can't be fattened (Grrr)
	#if dsdf[u'flattenHapi']:
	#	sOpt += "-f"

	uHapiCmd = u"das2_hapi %s -b %s -e %s %s"%(
	            sOpt, sBeg, sEnd, sHapiParam)
	
	uCmd = u"%s | %s"%(uRdrCmd, uHapiCmd)
	
	fLog.write(u"   Exec Host: %s"%platform.node())
	fLog.write(u"   Exec Cmd: %s"%uCmd)
	
	# Make a decent file name for this dataset in case they just want
	# to save it to disk
	sName = bname(sDsdf).replace('.dsdf','')
	if sSubKey:
		sName = "%s-%s"%(sName, sSubKey)
		
	sFnBeg = sBeg.replace(":","-").replace(".000Z", "").replace("T00-00-00","")
	sFnEnd = sEnd.replace(":","-").replace(".000Z", "").replace("T00-00-00","")
	sOutFile = "%s_%s_%s.csv"%(sName, sFnBeg, sFnEnd)
	fLog.write(u"   Filename: %s"%sOutFile)
	
	(nRet, sStdErr, bHdrSent) = U.command.sendCmdOutput(
		fLog, uCmd, 'text/csv; charset=utf-8', 'attachment', sOutFile)

	# Handle the no data case
	if nRet == 0:
		if not bHdrSent:
			pout('Content-Type: text/csv; charset=utf-8')
			pout('Status: 200 OK\r\n')
			fLog.write("   Not data in range, empty message body sent")
	else:
		if not bHdrSent:
			# If headers haven't went out the door, I can send a proper error
			# response
			pout('Content-Type: application/json; charset=utf-8')
			pout('Status: 500 Internal Server Error\r\n')
	
			dStatus = {'code':1500, 'message': 'Internal Server Error'}
			dOut = {"HAPI": "1.1", 'status':dStatus}
			dStatus['x_reason'] = sStdErr.replace('\\', '\\\\').replace('"','\"') 
		
			sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
			sys.stdout.write(sOut)
			sys.stdout.write('\r\n')
			
			fLog.write("Non-zero exit value, %d from pipeline BEFORE initial output"%nRet)
		else:
			fLog.write("Non-zero exit value, %d from pipeline AFTER initial output:"%nRet)
			lLines = sStdErr.split('\n')
			for sLine in lLines:
				fLog.write("   %s"%sLine)
						
	return nRet
