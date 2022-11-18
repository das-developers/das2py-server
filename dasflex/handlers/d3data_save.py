"""Default request handler for running Das2 readers"""

import sys
import platform
import os
import json

from os.path import basename as bname
from os.path import join as pjoin
from urllib.parse import quote_plus as urlEnc
from urllib.parse import unquote_plus as urlDec

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

# ########################################################################## #

def _getInternal(U, fLog, dConf, sPathInfo):
	"""Returns (dInternal, sConvention)
	"""
	
	if sPathInfo.startswith('/source/'):   # Knock off leading '/source'
		sLocalId = sPathInfo[len('/source/'):]
	else:
		U.webio.queryError(fLog, 
			"Invalid data request, path did not begin with '/source/'"
		)
		return (None,None)

	# Pop off the last item and use it as the form handling convertion (aka the
	# actual source type)
	if sLocalId.endswith('/'): sLocalId = sLocalId[-1]

	lLocalId = sLocalId.split('/')
	if len(lLocalId) < 2:
		U.webio.notFoundError(fLog, "Incomplete data source path.")
		return (None, None)

	sConv = lLocalId[-1].strip()
	sLocalId = '/'.join( lLocalId[:-1] )

	sInternal = "%s/root/%s/internal.json"%(dConf['DATASRC_ROOT'], sLocalId.lower())

	if not os.path.isfile(sInternal):
		U.webio.notFoundError(fLog, "There is no data source at '%s'"%sPathInfo)
		return (None, None)

	try:
		with open(sInternal, 'r') as fIn:
			dIntern = json.load(fIn)
	except Exception as e:
		fLog.write("   ERROR: %s"%str(e))
		sContact = ''
		if 'CONTACT_URL' in dConf:
			sContact = 'at <a href="%s">%s</a'%(dConf['CONTACT_URL'],dConf['CONTACT_URL'])
		elif 'CONTACT_EMAIL' in dConf:
			sContact = 'at <a href="mailto: %s>%s</a>'%(dConf['CONTACT_EMAIL'],dConf['CONTACT_EMAIL'])
		U.webio.serverError(fLog, 
			"There is an internal problem with this data source, please contact "+\
			"the server administrator%s"%sContact
		)
		return (None, None)

	return (dIntern, sConv)


# ########################################################################## #
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""Run a command pipeline and stream the result as an http message body.
	
	Args:
		See dasflex.handlers.intro.py for a decription of this function
		interface
	"""

	fLog.write("\ndas3 data request handler")

	if 'DATASRC_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DATASRC_ROOT not set in %s"%dConf['__file__'])
		return 17

	if sys.platform.startswith('win'):
		U.webio.todoError(fLog, "Not yet compatible with windows:\n"+\
	     	"Change the shell pipelines to use the python subprocess module "+\
			"before running on windows."
		)
		return 7

	(dSrc, sConv) = _getInternal(U, fLog, dConf, sPathInfo)
	if not dSrc:
		return 7

	# Get all the query keys as a dictionary, and preform translations.
	# Ignore:
	#   Form keys that upload files
	#   Form keys that are empty

	dParams = {}
	if ('insert' in dSrc) and (sConv in dSrc['insert']):  # Insert convention keys
		dInsert = dSrc['insert'][sConv]
		for sParam in dInsert:
			dParams[sParam] = dInsert[sParam]

	dTranslate = {}
	if ('translate' in dSrc) and (sConv in dSrc['translate']):
		dTranslate = dSrc['translate'][sConv]

	for sKey in form.keys():
		if form[sKey].file: continue
		sVal = form.getfirst(sKey, None)
		if sVal:
			if sKey in dTranslate:
				if dTranslate[ sKey ]: # Some items map away to nothing
					dParams[ dTranslate[ sKey ] ] = sVal
			else:
				dParams[sKey] = sVal

	pout("Status: 200 OK")
	pout("Content-Type: text/plain")
	pout("")
	for sParam in dParams:
		pout("%s = %s"%(sParam, dParams[sParam]))

	pout("")
	pout(str(dTranslate))
	return 0

	# Handle HTTP basic authorization, the only kind we understand right now

	if 'authorization' in dSrc['internal']:
		nRet = U.auth.authorize(dConf, fLog, dSrc, dParams)

		if nRet == U.auth.AUTH_SVR_ERR:
			sys.stdout.write("Status: 501 Internal Server Error\r\n\r\n")
			# Don't give away alot of information when a failed authentication
			# occurs, the log has that info if needed
			return 0
			
		elif nRet == U.auth.AUTH_FAIL:
			sys.stdout.write("Status: 401 Authorization Required\r\n")
			sys.stdout.write('WWW-Authenticate: Basic realm="%s"\r\n\r\n'%dsdf['securityRealm'])
			return 0

		# Only other status out of auth is AUTH_SUCCESS, which means we proceed
		# Though globus integration may add more options...
		
	# The cache decision:
	#
	# Can a cache read command even be constructed from this parameter set?
	#  |
	#  +-yes->  Are there sufficent cache blocks to handle the command?
	#  |         |
	#  |         +-yes->  Run the cache cmd
	#  |         |
	#	|         +--no->  Submit cache job & run a normal cmd
	#  |
	#  +--no->  Run a normal command

	try:
		sCmd = U.cache.solveCacheCmd(fLog, dConf, dSrc, dParams)
	
		if sCmd != None:
			lMissing = U.cache.missList(fLog, dConf, dSrc, dParams)

			if lMissing != None and len(lMissing) > 0:
				for t in lMissing:
					fLog.write("Missing: %s"%str(t))
					
				fLog.write("   Cache miss: Submitting build task for %d "%len(lMissing)+\
			           	"cacheLevel_%02d blocks."%lMissing[0][2])
				U.cache.reqCacheBuild(fLog, dConf, sDsdf, lMissing)
			else:
				bCacheMiss = False
				sCacheDir =  pjoin(dConf['CACHE_ROOT'], 'data', sDsdf)
				fLog.write("   Cache hit: Reading data from %s"%sCacheDir)
		else:
			sCmd = U.command.solveUpstreamCmd(dConf, dSrc, dParams)
	except U.errors.DasError as e:
		U.webio.dasErr2HttpMsg(fLog, e)
		return 17

	
	if dsdf[u'das2Stream']:
		sOutFmt = 'd2s'
	else:
		sOutFmt = 'qds'
		
	# Converting to ascii
	sAscii = getVal(form, 'ascii', '')
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
	
	(nRet, sStdErr, bHdrSent) = U.command.sendCmdOutput(
		fLog, sCmd, sMimeType, sContentDis, sOutFile
	)

	if nRet != 0:
		U.webio.serverError(
			fLog, 
			u"exec: %s\n%s\nNon-zero exit value, %d from pipeline"%(uCmd, sStdErr, nRet ), 
			bHdrSent
		)
	
	return nRet
