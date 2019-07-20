"""Default handler for sending data source information as a das2 packet"""

import StringIO
import sys
import os

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

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
	fOut = StringIO.StringIO()
	
	fOut.write(u"<stream>\r\n")
	fOut.write(u"  <properties")
	
	for uKey in dsdf.keys():
	
		bCont = False
		for sTmp in tDrop:
			if uKey.startswith(sTmp):
				bCont = True
				break
		
		if bCont:
			continue
		
		# Replace special characters
		lValue = list( dsdf[uKey])
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
		
		fOut.write( u' %s="%s"'%(uKey, uValue.strip("'")))
	
	fOut.write(u" />\r\n")
	fOut.write(u"</stream>")
	
	return fOut.getvalue()


##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface
	"""
	sDsdf = form.getfirst('dataset', '')
	if sDsdf == '':
		sDsdf = os.getenv("PATH_INFO")[1:]  # Knock off leading '/'
	
	fLog.write("\nDas 2.2 Description Handler")
	
	if 'DSDF_ROOT' not in dConf:
		U.io.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
		
	dsdf = U.dsdf.Dsdf(sDsdf, dConf, form, fLog)
	
	if u'rename' in dsdf:
		return U.dsdf.handleRedirect(fLog, sDsdf, dsdf)
	
	sOut = _dsdfToStreamHdr(dsdf)
	
	# Set a mime-type that allows this to be visible in a browser
	if U.io.isBrowser():
		pout('Content-Type: text/plain; charset=utf-8\r\n')
	else:
		pout("Content-Type: text/vnd.das2.das2stream\r\n")
		
	nLen = len( sOut.encode('utf-8') )
	
	sAllOut = u"[00]%06d%s"%(nLen, sOut)
	sys.stdout.write(sAllOut.encode('utf-8'))
	return 0
