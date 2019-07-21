"""Default handler for sending data source information as JSON description"""

from io import StringIO     # handles unicode strings

import sys
import os
import json
import urllib

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')


##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface
	"""
	sDsdf = os.getenv("PATH_INFO")  # Knock off leading '/source'
	if sDsdf.startswith('/source/'):
		sDsdf = sDsdf[len('/source/'):]
	else:
		U.webio.serverError(fLog, u"PATH_INFO did not start with /source/")
		
	sDsdf = sDsdf.replace(".json", '')
	
	fLog.write("\nDas 2.3 Source definition Handler")
	
	if 'DSDF_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	# Hidden debug switch
	bInternal = False
	if form.getfirst('internal', '') != '':
		bInternal = True
	
	dsdf = U.dsdf.Dsdf(sDsdf, dConf, form, fLog)
	sRootUrl = "%s/data"%U.webio.getScriptUrl() 
	dDef = dsdf.getInterfaceDef(dConf, fLog, dConf['SITE_PATHURI'], sRootUrl, bInternal)
	
	# Add in our own options.
	if dsdf.isTrue('qstream'):
		sNewMime = 'text/vnd.das2.qstream; charset=utf-8'
	else:
		sNewMime = 'text/vnd.das2.das2stream; charset=utf-8'
	dOutOpts = {}
	dDef['SOURCE']['QUERY_PARAMS']['OUTPUT'] = dOutOpts
	dOutOpts['text'] = {'TITLE':'Convert Binary Values to Text', 'TYPE':'boolean',
						  'DEFAULT':False, 'REQIRED':False, 'MIME':sNewMime}
	if not dsdf.isTrue('qstream'):
		dDef['SOURCE']['FORMATS']['AVAILABLE'] = [{'MIME':sNewMime, 'VERSION':'2.2'} ]
	else:
		dDef['SOURCE']['FORMATS']['AVAILABLE'] = [{'MIME':sNewMime} ]
		
	
	pout("Content-Type: application/json; charset=utf-8\r\n")
	
	#sScript = U.webio.getScriptUrl()
	#sUrl = _exampleUrl(U, dConf, sScript, sDsdf, dOut, bMkPathUrl)
	#if sUrl:
	#	dOut['example'] = sUrl
	
	sOut = json.dumps(dDef, ensure_ascii=False, sort_keys=True, indent=3)
	sys.stdout.write(sOut.encode('utf-8'))
	return 0



