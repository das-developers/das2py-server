"""Default logo request handler"""

import glob
import sys
import mimetypes

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See dasflex.handlers.intro.py for a decription the handler
	interface
	"""
	
	pout = sys.stdout.write
	
	sPtrn = "%s/logo.*"%dConf['RESOURCE_PATH']
	
	lLogos = glob.glob(sPtrn)
	
	if len(lLogos) == 0:
		U.webio.pout("Status: 404 Not Found\r\n")
		U.webio.pout("Content-Type: text/plain; charset=utf-8\r\n\r\n")
		U.webio.pout("Logo not set for this Das2.2 server\r\n")
		
		fLog.write("\nLogo Handler\n   ERROR: No files matching pattern %s"%sPtrn)
		return 17
	
	(sType, sEncode) = mimetypes.guess_type(lLogos[0])
	if sType == None:
		U.webio.serverError(fLog, u"Unrecognized mime type for %s"%lLogos[0])
		return 17
	
	U.webio.pout("Content-Type: %s\r\n\r\n"%sType)
	
	fLog.write("\nLogo Handler\n   Sending: %s"%lLogos[0])
	fIn = open(lLogos[0], 'rb')
	U.webio.pout(fIn.read())
	
	
	return 0
	
