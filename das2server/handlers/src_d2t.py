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

def _dsdfToStreamHdr(dsdf):
	"""Write a utf-8 string that contains the stream"""
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
	interface
	"""

	sDsdf = form.getfirst('dataset', '')
	if sDsdf == '':
		if os.getenv("PATH_INFO"):
			sDsdf = os.getenv("PATH_INFO")
			sDsdf = sDsdf.replace('/source/', '')  # Knock off leading '/source/'
			sDsdf = sDsdf.replace('/dsdf.d2t', '') # knock off trailing filename
		else:
			U.webio.queryError(
				fLog, u"No dataset specified, use the 'dataset=' query parameter "+\
				"or the /source/ path"
			)
			return 17
	
	fLog.write("\nDas 2.2 Description Handler")
	
	if 'DSDF_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	try:
		dsdf = U.dsdf.Dsdf(sDsdf, dConf, form, fLog)
	except U.errors.QueryError as e:
		U.webio.notFoundError(fLog, str(e))
		return 17

	if u'rename' in dsdf:
		return U.dsdf.handleRedirect(fLog, sDsdf, dsdf)

	# Add in our own stuff
	sScriptURL = U.webio.getScriptUrl()
	dsdf.d['action'] = 'das2.2 | %s?server=dataset&dataset=%s'%(sScriptURL, sDsdf)
	#dsdf.d['action_01'] = 'das2.3 | %s/%s/data'%(sScriptURL, sDsdf.lower())
	#dsdf.d['interface_00'] = 'das2.3  | %s/%s/das2.json'%(sScriptURL, sDsdf.lower())
	#dsdf.d['interface_01'] = 'vods1.1 | %s/%s/voresource.xml'%(sScriptURL, sDsdf.lower())
	
	sOut = _dsdfToStreamHdr(dsdf)
	
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
