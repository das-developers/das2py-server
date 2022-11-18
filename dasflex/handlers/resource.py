"""Default Handler for the resource file interface"""

import sys
import os.path
import mimetypes

from os.path import join as pjoin
from os.path import basename as bname

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See dasflex.handlers.intro.py for a decription of this function
	interface
	"""
	
	# Get files from either the static or catalog areas
	if sPathInfo.startswith('/static/'):
		sResource = sPathInfo.replace('/static/', '')
		sFile = pjoin(dConf['RESOURCE_PATH'], sResource)
		
		U.webio.pout("Expires: %s\r\n"%U.webio.httpNextYear()) # long time-out for static

	elif sPathInfo.startswith('/source/'):
		sResource = sPathInfo.replace('/source/', 'root/')
		sFile = pjoin(dConf['DATASRC_ROOT'], sResource)

	if not os.path.isfile(sFile):
		U.webio.serverError(fLog, u"Resource '%s' doesn't exist"%sResource)
		return 17
		
	# Handle our own mime types...
	tRet = U.mime.getMimeByExt(sFile)
	
	if tRet != None:
		#fLog.write("tuple->'%s'"%str(tRet))
		(sType, sContentDis, sFileExt) = tRet
		
		sOutFile = bname(sFile)	
		U.webio.pout('Content-Disposition: %s; filename="%s"\r\n'%(sContentDis, sOutFile))
	else:
		(sType, sEncode) = mimetypes.guess_type(sFile)
		if sType == None:
			U.webio.serverError(fLog, u"Unrecognized mime type for %s"%sFile)
			return 17

	U.webio.pout('Access-Control-Allow-Origin: *\r\n')
	U.webio.pout('Access-Control-Allow-Methods: GET\r\n')
	U.webio.pout('Access-Control-Allow-Headers: Content-Type\r\n')
	U.webio.pout("Content-Type: %s\r\n"%sType)
	U.webio.pout("\r\n")
		
	fIn = open(sFile, 'rb')
	if sys.version_info[0] == 2:
		sys.stdout.write(fIn.read())
	else:
		sys.stdout.buffer.write(fIn.read())
	
	return 0

