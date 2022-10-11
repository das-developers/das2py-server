"""Default handler for sending data source information as a das2 packet"""

from os.path import dirname
import sys
import os

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.handlers.intro.py for a decription of this function
	interface.

	Check the source interface to see if it can be adapted to the old DSDF
	format.  If so send a reply
	"""

	sSrc = form.getfirst('dataset', '')
	if sSrc == '':
		if os.getenv("PATH_INFO"):
			sSrc = os.getenv("PATH_INFO")
			sSrc = sSrc.replace('/source/', '')  # Knock off leading '/source/'
			sSrc = sSrc.replace('/dsdf.d2t', '') # knock off trailing filename
		else:
			U.webio.queryError(
				fLog, u"No dataset specified, use the 'dataset=' query parameter "+\
				"or the /source/ path"
			)
			return 17
	
	fLog.write("\nDas 2.2 Description Handler")
	
	try:
		dSrc = U.source.external(fLog, dConf, sSrc)
	except U.errors.QueryError as e:
		U.webio.notFoundError(fLog, str(e))
		return 17
	# Add in our own stuff
	sScriptURL = U.webio.getScriptUrl()
	dsdf.d['action'] = 'das2.2 | %s?server=dataset&dataset=%s'%(sScriptURL, sSrc)
	
	try:
		sOut = _das22Iface(dSrc)
	except U.errors.DasError as e:
		U.webio.dasErr2HttpMsg(fLgo, e)
		return 17
	
	U.webio.pout('Access-Control-Allow-Origin: *\r\n')
	U.webio.pout('Access-Control-Allow-Methods: GET\r\n')
	U.webio.pout('Access-Control-Allow-Headers: Content-Type\r\n')

	# Set a mime-type that allows this to be visible in a browser
	if U.webio.isBrowser():
		U.webio.pout('Content-Type: text/plain; charset=utf-8\r\n\r\n')
	else:
		U.webio.pout("Content-Type: text/vnd.das2.das2stream\r\n\r\n")
	
	xOut = sOut.encode('utf-8')
	nLen = len( xOut )
	U.webio.pout("[00]%06d"%nLen)
	U.webio.pout(xOut)
	return 0
