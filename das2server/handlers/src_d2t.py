"""Default handler for sending data source information as a das2 packet"""

from io import StringIO     # handles unicode strings
from os.path import dirname
import sys
import os

##############################################################################

tDrop = (
	'reader', 'reducer', 'compressor', 'readAccess', 'groupAccess',
	'hapi', 'subSource', 'hapi', 'readerCmd', 'reducerCmd', 'exampleQuery',
	'readerTrans'
	
	# Autoplot developers built a hard limit buffer into their das2 info
	# parser.  Try to route around the problem by dropping extra stuff
	,'paramValInfo'
) 

def _das22Iface(U, dSrc):
	"""Write a utf-8 string that contains the stream"""

	(sBeg, sEnd, sRes, sInt, Opts) = U.source.stdFormKeys('v3')

	if ('protocol' not in dSrc) or ('http_params' not in dSrc['protocol']):
		raise U.errors.ServerError("'http_params' missing from source definition")

	dParams = dSrc['protocol']['http_params']
	
	# Have to have at least a begin time and end time to support a das2.2 query
	if (sBeg not in dParams) or (sEnd not in dParams):
		raise U.errors.notFoundError("Data source does not support the das2/v2.2 query interface.")

	dDsdf = {}
	if 'title' in dSrc:  dDsdf['description'] = dSrc['title']
	#if 'contacts' in dSrc:
	#	for dContact in dSrc['contacts']:
	#		if dContact['type'] == 'scientific':
							


	fOut = StringIO()
	
	fOut.write(u"<stream version=\"2.2\">\r\n")
	fOut.write(u"  <properties\r\n")

	lKeys = list(dsdf.keys())
	lKeys.sort()
	sLastPre = ''
	for sKey in lKeys:
	
		bCont = False
		for sTmp in tDrop:
			if sKey.startswith(sTmp):
				bCont = True
				break
		
		if bCont:
			continue

		# Replace special characters
		lValue = list( dsdf[sKey])
		dReplace = {u'&':u'&amp;', u'"':u'&quot;', u"'":u'&apos;', u"<":u"&lt;",
		            u'>':u'&gt;', u'(':'', u')':''}
		lRepKeys = dReplace.keys()
		
		lNewValue = [None]*len(lValue)
		for i in range(0, len(lValue)):
			if lValue[i] in lRepKeys:
				lNewValue[i] = dReplace[ lValue[i] ]
			else:
				lNewValue[i] = lValue[i]
				
		uValue = u"".join(lNewValue)
		
		# See if we want to space this out
		lKey = sKey.split('_')
		if (len(sLastPre) > 0) and (not sKey.startswith(sLastPre)):
			fOut.write( u'\r\n    %s="%s"\r\n'%(sKey, uValue.strip("'")))
		else:
			fOut.write( u'    %s="%s"\r\n'%(sKey, uValue.strip("'")))
		sLastPre = lKey[0]
	
	fOut.write(u" />\r\n")
	fOut.write(u"</stream>")
	
	return fOut.getvalue()


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
