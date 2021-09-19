"""Default request handler for running Das2 readers"""

import sys
import platform
import os
import json

from os.path import basename as bname
from os.path import join as pjoin

# Module moved in python3
try:
	from urllib import quote_plus as urlEnc
except ImportError:
	from urllib.parse import quote_plus as urlEnc


##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
##############################################################################
def normalizeFlagParam(form):
	"""In general one GET form key goes with one data source query parameter
	but FLAG_SET parameters are an exception.
	
	Since more than one flag can be set, two syntax types are supported in
	order to make the interface easier for web-browser clients both the
	standard syntax:
	
	   key=f1,f2,f3...
	
	and the alternate syntax...
	
	   key~f1=on&key~f2=on&key.f3=off
	
	are supported.
	"""
	
	# Build a new parameter set that turns any flag parameters into the connonical
	# set
	dForm = {}
	for sKey in form:
		iTilda = sKey.find('~')
		
		if iTilda == -1:
			dForm[sKey] = form.getfirst(sKey)
		else:
			sShortKey = sKey[:Tilda]
			sState = form.getfirst(sKey)
			if sState.lower() not in ('on','true','1'):
				continue
			
			sFlag = sKey[Tilda + 1:].strip()
			if len(sFlag) == 0:
				continue
			
			if sShortKey in dForm:
				dForm[sShortKey] = "%s,%s"%(dForm[sShortKey], sFlag)
			else:
				dForm[sShortKey] = sFlag
	
	return dForm

##############################################################################
def _addRequired(U, fLog, dParams, lReq, sPrefix=None):
	"""Walk the parameters tree finding out if required parameters are missing
	some parameters are containers (famous example is time.min) non-container
	parameters have a TYPE entry.
	"""
		
	for sParam in dParams:
		sTmp = sParam
		if sPrefix:
			sTmp = "%s.%s"%(sPrefix, sParam)

		#fLog.write("DEBUG: Checking parameter %s"%sTmp)
		
		if 'TYPE' in dParams[sParam]:
			if 'REQUIRED' not in dParams[sParam]:
				sTmp = sParam
				if sPrefix:
					sTmp = "%s.%s"%(sPrefix, sParam)
				U.webio.serverError(fLog, "Error in data source definition, "+\
				                 "keyword 'REQUIRED' missing for parameter %s"%sTmp)
				return None
				
			if dParams[sParam]['REQUIRED']:
				if sPrefix:
					lReq.append("%s.%s"%(sPrefix,sParam))
				else:
					lReq.append(sParam)
		else:
			#U.webio.serverError(fLog, u"DEBUG: sub params are %s"%dParams[sParam].keys())
			#return None
			_addRequired(U, fLog, dParams[sParam], lReq, sParam)
			
	return
	
##############################################################################
# Parameter translation.  
g_dSep = {'NONE':'','SPACE':' ','COMMA':',', 'COLON':':', 'MINUS':'-'}

def _xlateArgPtrn(U, fLog, sPattern, sFormVal):
	"""Use the subtitution patterns to convert the form value to a command 
	line argument.  Patterns supported now are %{VALUE} and %{FLAG,septype}
	"""
	if sPattern.find("%{VALUE}") != -1:
		return sPattern.replace("%{VALUE}",sFormVal)
	
	i = sPattern.find("%{FLAG,")
	if sPattern.find("%{FLAG,") != -1:
		j = sPattern.find("}")
		if (j == -1) or (j < i) or (i + 7 == j):
			U.webio.serverError("Error in datasource FLAG_SET translation pattern %s"%sPattern)
			return None
		sSep = sPattern[i+7:j].strip().upper()
		if sSep not in g_dSep:
			U.webio.serverError("Error in datasource FLAG_SET translation pattern, unknown separator %s"%sSep)
			return None
		lFormVal = sFormVal.split(',')
		sFormVal = g_dSep[sSep].join(lFormVal)
		
		return "%s%s%s"%(sPattern[:i], sFormVal, sPattern[j+1:])
	
	U.webio.serverError("Error in datasource argument translation %s, pattern not recognized"%sPattern)
	return None

##############################################################################


	
def _normParams(U, fLog, dSrc, sType, lOmitt, dForm):
	"""Given a data source definition dictionary and a web form object determine
	the normalized parameter set for a reader.  Args are:
	
	U - the utility module, used for exceptions
	fLog - The logger, used for debug messages
	
	dSrc - The datasource definition
	
	sType - The type of parameters to get, typically 'READER_ARG'
	
	lOmitt - Parameters to ignore.  These are usually parameters that are used
	         to set the cache block and aren't part of the cache line definition
	
	form - The http form
	"""
		
	# The parameter set is determined by everything marked READER_ARG that
	# is not associated with the cacheBase .* parameters
	dParams = U.dsdf.sourceGetParamDict(dSrc['QUERY_PARAMS'])
			
	# Search the new form for any reader parameters that are not in the omitt list
	sToNorm = ''
	for sKey in dForm:
		bSkip = False
		for sOmitt in lOmitt:
			if sKey.startswith(sOmitt):
				bSkip = True
				break
		
		if bSkip or (sKey not in dParams):
			continue
		
		dParam = dParams[sKey]
			
		# Parameter should always have a '_translate' and '_what' keys
		# even if nothing else is present
		if '_translate' not in dParam:
			U.webio.serverError("Internal error, key _translate not present for"+\
			                 " parameter " + sKey)
		if '_what' not in dParam['_translate']:
			U.webio.serverError("Internal error, definiton _what not present for"+\
			                 " parameter " + sKey)
		
		if dParam['_translate']['_what'] != sType:
			continue
			
		# Translations can be one of: pattern, map, or direct.
		if '_pattern' in dParam['_translate']:
			sToNorm += " "
			sXlate = _xlateArgPtrn(U, fLog, dParam['_translate']['_pattern'], dForm[sKey])
			if not sXlate:
				return None
			
			sToNorm += " %s"%sXlate
			
		elif '_map' in dParam['_translate']:
			dMap = dParam['_translate']['_map']
			if dForm[sKey] not in dMap:
				U.webio.queryError("Form value %s for key %s not in data source argument map"%(
				                dForm[sKey], sKey))
				return None
			
			sToNorm += " %s"%dMap[dForm[sKey]]
			
		else:
			sToNorm += " %s"%dForm[sKey]
	
	# Now call the dsdf normalizeParams to make sure we get the same mapping
	# as the Das 2.2 system did.  Don't want to have to re-write the cache
	# just because they install new server software
	return U.dsdf.normalizeParams(sToNorm)
	

##############################################################################

def getCacheReadCmd(U, fLog, sLocalId, dSrc, dForm):
	"""Try to get a command line for a cache read that will satisfy the request
	if not return None.
	
	Submit any cache build requests for any cache misses
	"""
	
	if '_cache' not in dSrc['COORDINATES']:
		return None
				
	sNormParams = _normParams(U, fLog, dSrc, 'READER_ARG', ['time.'], dForm)
	
	fLog.write("   Cache check: Need resolution '%s' or better with paramset '%s'"%(
	           rRes, sNormParams))
		
	dCache = dSrc['COORDINATES']['_cache']
		
	# Get all the parameter values over which data are grouped in coord space
	# these have to be ranges so require a min and max.  Default res to 0 if 
	# if not provided
	dRegion = {}
	for sParam in dCache['_block_by']:
		for sKey in form:
			sPre = sParam + '.'
			if sKey.startswith(sPre):
				dRegion[sKey] = dForm[sKey]
		if sParam + '.res' not in dRegion:
			dRegion[sParam + '.res'] = 0.0
	
	# The above method is general, but our current cache reader was built only
	# to understand time blocks.  Until we update it we'll have to collapse 
	# down to only understanding time
	bNonTimeCache = False
	for sKey in dRegion:
		if not sKey.startswith('time.'):
			bNonTimeCache = True
			fLog.write("   TODO: Request for non-time cache blocks can't "+\
			           "be satisfied by the current cache reader, assuming cache miss")
			return None
		
	lMissing = U.cache.missList23(fLog,dConf,dCache,sLocalId,dRegion,sNormParams)
		
	if lMissing != None and len(lMissing) > 0:
		for t in lMissing:
			fLog.write("Missing: %s"%str(t))
				
		fLog.write("   Cache miss: Submitting build task for %d "%len(lMissing)+\
		           "cacheLevel_%02d blocks."%lMissing[0][2])
		U.cache.reqCacheBuild(fLog, dConf, sLocalId, lMissing)
	else:
		bCacheMiss = False
		sCacheDir =  pjoin(dConf['CACHE_ROOT'], 'data', sLocalId)
		fLog.write("   Cache hit: Reading data from %s"%sCacheDir)
		
		# Cache readers are expected to take the following arguments:
		# 0. The program name (of course)
		# 1. The DSDF file path --> need to update to pure json
		# 2. The dataset cache root (= Cache_ROOT + dsdf_rel_path)
		# 3. The normalized parameter string
		# 4. The begin index point
		# 5. The end index point (exclusive upper bound)
		# 6. The requested resolution		
		uCmd = u"%s %s %s %s '%s' '%s' %.5e"%(
		         dSrc['_cache_reader'], dsdf.sPath, sCacheDir, sNormParams,
					sBeg, sEnd, rRes
		       )
	 
	return uCmd
	

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface
	"""
	
	sLocalId = form.getfirst('dataset', '')
	if sLocalId == '':
		sLocalId = os.getenv("PATH_INFO")  # Knock off leading '/data/'
		if sLocalId.startswith('/data/'):
			sLocalId = sLocalId[len('/data/'):]
	
	if sLocalId.find('_dirinfo_') != -1:
		U.webio.queryError(fLog, u"Invalid das2.3 query")
		return 17
	
	fLog.write("\nDas 2.3 Data Query Handler")
	
	if sys.platform.startswith('win'):
		U.webio.todoError(fLog, u"Not yet compatible with windows:\n"+\
		      u"Change the shell pipelines to use the python subprocess "+\
				u"module before running on windows.")
		return 7	
	
	if 'DSDF_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	# Get the datasource object
	dsdf = U.dsdf.Dsdf(sLocalId, dConf, form, fLog)
	
	# Get the interface definition
	sRootUrl = "%s/data"%U.webio.getScriptUrl() 
	dDef = dsdf.getInterfaceDef(dConf, fLog, dConf['SITE_PATH_URI'], sRootUrl, True)
	
	# See if this is just a redirection, it will look like a catalog node
	if 'URL' in dDef:
		return U.dsdf.handleRedirect(fLog, sLocalId, dsdf)
					
	# Get the interface definition and make sure that all required parameters
	# are specified
	if 'SOURCE' not in dDef:
		U.webio.serverError(fLog, "'SOURCE' key missing in source definition")
		return 17
	else:
		dSrc = dDef['SOURCE']
	
	if 'QUERY_PARAMS' not in dSrc:
		U.webio.serverError(fLog, "'QUERY_PARAMS' missing in source definition")
		return 17
	else:
		dParams = dSrc['QUERY_PARAMS']
		
	# normalize any flag_set parameters
	dForm = normalizeFlagParam(form)
	
	# make sure we have all required parameters	
	lReq = []
	for sBlock in dParams:
		lMore = _addRequired(U, fLog, dParams[sBlock], lReq)
			
	for sReq in lReq:
		if sReq not in dForm:
			U.webio.queryError(fLog, u"Invalid query, required GET key %s is missing"%sReq)
			return 17
			
	# Loop through all parameter values looking for wierd stuff such as shell
	# injection attacks (U.dsdf.checkParam, U.dsdf.normalizeParams(sRdrCmd))
	for sKey in dForm:
		if not dForm[sVal] or len(dForm[sVal]) == 0:
			U.webio.queryError(fLog, u"Invalid query, GET key %s contains no value", sKey)
			return 17
			
		if not U.dsdf.checkParam(fLog, sKey, sVal):
			return 17
			
	# Handle authorization if needed
	if '_authorization' in dSrc:
		sAuth = dSrc['_authorization']['_dsdf_compat']
		nRet = U.auth.authorize(dConf, fLog, form, sLocalId, sAuth)

		if nRet == U.auth.AUTH_SVR_ERR:
			sys.stdout.write("Status: 501 Internal Server Error\r\n\r\n")
			# Don't give away alot of information when a failed authentication
			# occurs, the log has that info if needed
			return 0
			
		elif nRet == U.auth.AUTH_FAIL:
			sys.stdout.write("Status: 401 Authorization Required\r\n")
			sys.stdout.write('WWW-Authenticate: Basic realm="%s"\r\n\r\n'%dsdf['_realm'])
			return 0

		# Only other status out of auth is AUTH_SUCCESS, which means we proceed
	
	# Try for a cache read if you can get it
	uCmd = _getCacheReadCmd(U, fLog, sLocalId, dSrc, dForm)
	
	# Well, we have a cache miss, produce reduced data the old fashioned way...
	if uCmd == None:
	
		# The command building functions always return a string, unless there is an
		# error in which case they return None
		uRdrCmd = _buildReaderCmd(U, fLog, sLocalId, dSrc, dForm)
		if uRdrCmd == None or len(uRdrCmd) == 0:
			return 17
		uCmd = uRdrCmd
	
		uReduceCmd = _buildReducerCmd(U, fLog, sLocalId, dSrc, dForm)
		if uReduceCmd == None:
			return 17
	
		if len(uReduceCmd) > 0:
			uCmd += "| %s"%uReduceCmd
				
	# Output transformation...
	uTransCmd = _buildTransCmd(U, fLog, sLocalId, dSrc, dForm)
	if uTransCmd == None:
		return 17
		
	if len(uTransCmd) > 0:
		uCmd += "| %s"%uTransCmd
		
	# Content disposition
	sMime = _getOutputMime(dSrc, dForm)
	sOutFile = _getOutputFile(sLocalId, dForm, sMime)
	
	fLog.write(u"   Exec Host: %s"%platform.node())
	fLog.write(u"   Exec Cmd: %s"%uCmd)
	fLog.write(u"   Filename: %s"%sOutFile) 
	
	# Run it
	(nRet, sStdErr, bHdrSent) = U.command.sendCmdOutput(
		fLog, uCmd, sMimeType, sContentDis, sOutFile)

	if nRet != 0:
		U.webio.serverError(
			fLog, 
			u"exec: %s\n%s\nNon-zero exit value, %d from pipeline"%(uCmd, sStdErr, nRet ), 
			bHdrSent
		)
	
	return nRet
		
