"""Default request handler for running Das2.2 readers"""

import sys
import platform
import subprocess
import select
import fcntl
import os

from os.path import basename as bname
from os.path import join as pjoin

from urllib import quote_plus as urlEnc

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
	
##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See dasflex.handlers.intro.py for a decription of this function
	interface
	"""
	
	sDsdf = form.getfirst('dataset', '')
	if sDsdf == '':
		sDsdf = os.getenv("PATH_INFO")[1:]  # Knock off leading '/'
	
	if sDsdf.find('_dirinfo_') != -1:
		U.webio.queryError(fLog, u"Invalid das2.2 query")
		return 17
	
	fLog.write("\nDas 2.2 Coverage Dataset Handler")
	
	if sys.platform.startswith('win'):
		U.webio.todoError(fLog, u"Not yet compatible with windows:\n"+\
		      u"Change the shell pipelines to use the python subprocess "+\
				u"module before running on windows.")
		return 7	
	
	if 'DATASRC_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DATASRC_ROOT not set in %s"%dConf['__file__'])
		return 17
					
	# All das2.2 queries require a start and end time
	sBeg = form.getfirst('start_time','')
	sEnd = form.getfirst('end_time','')
	
	sRes = form.getfirst('resolution', '')
	if sRes == '':
		rRes = 0.0
	else:
		try:
			rRes = float(sRes)
		except ValueError as e:
			U.webio.queryError(fLog, u"Invalid das2.2 query, resolution '%s'"%sRes+\
			                "is not convertable to a floating point number")
			return 17
		
	sInterval = form.getfirst('interval', '')
	sParams = form.getfirst('params','')
	sNormParams = U.misc.normalizeOpts(sParams)
	
	lTmpKey = ['start_time','end_time','resolution','interval','params']
	lTmpVal = [sBeg, sEnd, sRes, sInterval, sParams];
	for i in range(0, len(lTmpVal)):
		if not U.dsdf.checkParam(fLog, lTmpKey[i], lTmpVal[i]):
			return 17
	
	if sBeg == '':
		U.webio.queryError(fLog, u"Invalid das2.2 query, start_time was not specified")
		return 17
	if sEnd == '':
		U.webio.queryError(fLog, u"Invalid das2.2 query, end_time was not specified")
		return 17
		
	# Okay this looks like a decent query, load the dsdf, and fill in defaults
	# If the dsdf wants the data to come from a different location, then 
	# just send a redirect now.
	try:
		dsdf = U.dsdf.Dsdf(sDsdf, dConf, form, fLog)
		
		if u'rename' in dsdf:
			return U.dsdf.handleRedirect(fLog, sDsdf, dsdf)
		
		if u'server' in dsdf and dsdf[u'server'] != U.webio.getScriptUrl() \
		   and not U.misc.isTrue('IGNORE_REDIRECT', dConf):
			return U.dsdf.handleRedirect(fLog, sDsdf, dsdf)
		
		dsdf.fillDefaults(dConf)
	
	except U.errors.DasError as e:
		U.webio.dasErr2HttpMsg(fLog, e)
		return 17
	
	# And finnaly, drop the parameters if the DSDF requests it
	# do NOT drop the normalized params.  Those don't go to the
	# reader but ARE used to keep cached versions straight.
	if dsdf.isTrue(u'dropParams'):
		sParams = ''

	# Handle authorization
	if 'readAccess' in dsdf:
		nRet = U.auth.authorize(dConf, fLog, form, sDsdf, dsdf['readAccess'])

		if nRet == U.auth.AUTH_SVR_ERR:
			sys.stdout.write("Status: 501 Internal Server Error\r\n\r\n")
			# Don't give away alot of information when a failed authentication
			# occurrs, the log has that info if needed
			return 0
			
		elif nRet == U.auth.AUTH_FAIL:
			sys.stdout.write("Status: 401 Authorization Required\r\n")
			sys.stdout.write('WWW-Authenticate: Basic realm="%s"\r\n\r\n'%dsdf['securityRealm'])
			return 0

		# Only other status out of auth is AUTH_SUCCESS, which means we proceed
		
		

	if dsdf[u'das2Stream']:
		sOutFmt = 'd2s'
	else:
		sOutFmt = 'qds'
	
	# Try for a coverage cache read if you can get it
	bCacheMiss = True
	if U.cache.isCacheable(dsdf, sNormParams, rRes):
		
		fLog.write("   Cache check: Need resolution '%s' or better with paramset '%s'"%(
		           rRes, sNormParams))
					  
		lMissing = U.cache.missList(fLog,dConf,dsdf,sNormParams,rRes,sBeg,sEnd)
		
		if lMissing != None and len(lMissing) > 0:
			for t in lMissing:
				fLog.write("Missing: %s"%str(t))
				
			fLog.write("   Cache miss: Submitting build task for %d "%len(lMissing)+\
			           "cacheLevel_%02d blocks."%lMissing[0][2])
			U.cache.reqCacheBuild(fLog, dConf, sDsdf, lMissing)
		else:
			bCacheMiss = False
			sCacheDir =  pjoin(dConf['CACHE_ROOT'], sDsdf)
			fLog.write("   Cache hit: Reading data from %s"%sCacheDir)
			
			# Cache readers are expected to take the following arguments:
			# 0. The program name (of course)
			# 1. The DSDF file path
			# 2. The dataset cache root (= Cache_ROOT + dsdf_rel_path)
			# 3. The normalized parameter string
			# 4. The begin index point
			# 5. The end index point (exclusive upper bound)
			# 6. The requested resolution		
			uCmd = u"%s %s %s %s '%s' '%s' %.5e"%(
			         dsdf[u'cacheReader'], dsdf.sPath, sCacheDir, sNormParams,
						sBeg, sEnd, rRes
			       )
		
	# Well, we have a cache miss, produce reducted data the old fashioned way...
	if bCacheMiss:
		# The Reader...
		if sInterval != '':
			uCmd = u"%s '%s' '%s' '%s' %s"%(dsdf[u'reader'], sInterval, sBeg, sEnd, sParams)
		else:
			uCmd = u"%s '%s' '%s' %s"%(dsdf[u'reader'], sBeg, sEnd, sParams)
		
		# The Reducer...
		if sRes != '':		
			if dsdf[u'reducer'] not in [u'not_reducible', u'not_reducable', u'pre_reduced']:	
				uCmd += u"| %s '%s'"%(dsdf[u'reducer'], sRes)				
	
		if sInterval == '':
			# The reader requires an interval setting but none was provided
			if dsdf[u'requiresInterval']:
				U.webio.queryError(fLog, u"Invalid das2.2 query, parameter 'interval' was not specified")
				return 17
		
		
		
	# Converting to ascii
	sAscii = form.getfirst('ascii', '')
	if U.misc.isTrue(sAscii):
		sOutCat = 'text'
			
		if dsdf[ u'qstream'] and 'QDS_TO_UTF8' in dConf:
			uCmd += u'| %s '%(dConf['QDS_TO_UTF8'])
				
		elif dsdf[u'das2Stream'] and 'D2S_TO_UTF8' in dConf:
			uCmd += u'| %s '%(dConf['D2S_TO_UTF8'])
	else:
		sOutCat = 'bin'
		
	
	fLog.write(u"   Exec Host: %s"%platform.node())
	fLog.write(u"   Exec Cmd: %s"%uCmd)
		
	(sMimeType, sContentDis, sFileExt) = U.webio.getOutputMime(sOutCat, sOutFmt)
		
	# Generate a filename
	sFnBeg = sBeg.replace(":","-").replace(".000Z", "").replace("T00-00-00","")
	sFnEnd = sEnd.replace(":","-").replace(".000Z", "").replace("T00-00-00","")
	sOutFile = "%s_%s_%s.%s"%(bname(sDsdf).replace('.dsdf',''), 
	                          #sBeg.replace(':','_'), sEnd.replace(':','_'),
									  sFnBeg, sFnEnd, sFileExt)
	fLog.write(u"   Filename: %s"%sOutFile)
		
	return U.dsdf.sendCmdOutput(fLog, uCmd, sMimeType, sContentDis, sOutFile)
	
