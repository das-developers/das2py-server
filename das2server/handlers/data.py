"""Default request handler for running Das2 readers"""

import sys
import platform
import os

from os.path import basename as bname
from os.path import join as pjoin
from urllib.parse import quote_plus as urlEnc
from urllib.parse import unquote_plus as urlDec

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

# ########################################################################## #
def _getDas22Src(U, fLog, form):
	sDsdf = form.getfirst('dataset','')
	if len(sDsdf) == 0:
		U.webio.queryError(fLog, "dataset parameter is required")
		return None
	if sDsdf.endswith('.dsdf'):
		sDsdf = sDsdf.replace('.dsdf','')
	return sDsdf

def _getDas23Src(U, fLog):
	sSrc = os.getenv("PATH_INFO")  # Knock off leading '/source'
	if sSrc.startswith('/source/'):
		sSrc = sSrc[len('/source/'):]
	else:
		U.webio.serverError(fLog, u"PATH_INFO did not start with /source/")
		return None

	if sSrc.endswith('/data'): sSrc = sSrc.replace('/data','');
	elif sSrc.endswith('/data/'): sSrc = sSrc.replace('/data/','')
	else:
		U.webio.serverError(fLog, u"PATH_INFO did not end with /data")
		return None

	return sSrc

# ########################################################################## #

def _map22ParamTo30(U, dParam):
	(sBeg, sEnd, sRes, sInt, sOpts) = U.source.stdFormKeys("v3.0")
	if 'start_time' in dParam: dParam[sBeg] = dParam.pop('start_time')
	if 'stop_time'  in dParam: dParam[sEnd] = dParam.pop('stop_time')
	if 'resolution' in dParam: dParam[sRes] = dParam.pop('resolution')
	if 'interval'   in dParam: dParam[sInt] = dParam.pop('interval')
	if 'params'     in dParam: dParam[sOpts] = dParam.pop('params')

# ########################################################################## #
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""Run a command pipeline and stream the result as an http message body.
	
	Args:
		See das2server.handlers.intro.py for a decription of this function
		interface
	"""

	fLog.write("\ndas3 data request handler")

	if 'DSDF_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17

	if sys.platform.startswith('win'):
		U.webio.todoError(fLog, "Not yet compatible with windows:\n"+\
	     	"Change the shell pipelines to use the python subprocess module "+\
			"before running on windows."
		)
		return 7

	# Get all the query keys as a dictionary, most of the sub functions
	# are going to want this interface anyway.  Ignore form items that
	# are uploaded files, we don't handle file input in this handler
	dParams = {}
	for sKey in form.keys():
		if form[sKey].file: continue
		dParams[sKey] = form.getfirst(sKey, None)
	
	# Trigger off of "server=dataset" to handle a das2.2 style request
	if ('server' in dParams) and (dParams['server'] == 'dataset'):
		sSrc = _getDas22Src(U, fLog, form)
		if not sSrc: return 17
		if not _map22ParamTo23(dParam): return 17
	else:
		sSrc = _getDas23Src(U, fLog)
		if not sSrc: return 17

	# Get the source definition including the internal protocol stuff.
	try:
		dSrc = U.source.internal(fLog, dConf, sSrc)
	except U.errors.QueryError:
		U.webio.queryError(fLog, "Data source does not exist")
		return 17
	except U.errors.ServerError as e:
		U.webio.serverError(str(e));
		return 17

	# Merge default commands into the source definition.  This will bring
	# the default re-binner, the default PSD, the default CSV converter, etc.
	U.command.mergeDefCmds(fLog, dConf, dSrc)

	# Handle authorization
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
