"""Default logo request handler"""

import glob
import sys
import mimetypes

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription the handler
	interface
	"""
	
	pout = sys.stdout.write
	
	if 'SITE_NAME' in dConf and len(dConf['SITE_NAME'].strip()) > 0:
		pout('Access-Control-Allow-Origin: *\r\n')
		pout('Access-Control-Allow-Methods: GET\r\n')
		pout('Access-Control-Allow-Headers: Content-Type\r\n')
		pout("Content-Type: text/plain; charset=utf-8\r\n\r\n")
		pout("%s\r\n"%dConf['SITE_NAME'])
		return 0

	U.webio.serverError(fLog, u"Bad Server Configuration, SITE_IDENTITY missing")
	return 17
	

	
