#!/usr/bin/env python3

import os
from os.path import basename as bname
from os.path import join as pjoin

import sys

import cgi
import cgitb
cgitb.enable(format='text')

# Stuff that might not work if server is mis-configured
import xml.parsers.expat
from lxml import etree

import das2

# ########################################################################## #

def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

_g_BrowserAgent = ['firefox','explorer','chrome','safari']

def errorExit(sOut):
	"""Cut down error handling for use before the util modules are loaded,
	script must exit afte calling this or multiple HTTP headers will be 
	emitted.
	"""
	
	bClientIsBrowser = False
	if "HTTP_USER_AGENT" in os.environ:
		
		sAgent = os.environ['HTTP_USER_AGENT'].lower()
	
		for sTest in _g_BrowserAgent:
			if sAgent.find(sTest) != -1:
				bClientIsBrowser = True
				break	
	pout("Status: 500 Internal Server Error\r\n")
	
	if bClientIsBrowser:
		pout("Content-Type: text/plain; charset=utf-8\r\n\r\n")
		cgitb.enable(format='text')
		
		pout(sOut)
	else:
		pout("Content-Type: text/plain; charset=utf-8\r\n\r\n")
		pout(sOut)

	sys.exit(5)


# ########################################################################### #
def sendDisabled(fLog, dConf):
	pout('Content-Type: text/html; charset=utf-8\r\n')

	pout('''
<html>
<head></head>
<body>
	<h2>The das2 stream validation service is not enable for this server.</h2>
	<p>Set <tt>ENABLE_VERIFY = true</tt> and possibly update <tt>VERIFY_FROM</tt>
	in your <tt>das2server.conf</tt> file to enable the stream verification service.</p>
</body>
</html>
''')

	return 0

# ########################################################################### #

def _preArticle(U, dConf, fLog, sTitle):
	pout('Content-Type: text/html; charset=utf-8\r\n')
	pout('<!DOCTYPE html>')
	
	dReplace = {"script":U.webio.getScriptUrl()}
				
	sScriptURL = U.webio.getScriptUrl()

	if 'STYLE_SHEET' in dConf:
		sCssLink = "%s/static/%s"%(sScriptURL, dConf['STYLE_SHEET'])
	else:
		sCssLink = "%s/static/das2server.css"%sScriptURL

	if 'SITE_TITLE' in dConf:
		sSiteId = dConf['SITE_TITLE']
	else:
		sSiteId = "Set SITE_TITLE in %s"%dConf['__file__']

	pout('''<html>
<head>
   <title>%s</title>
   <link rel="stylesheet" type="text/css" media="screen" href="%s" />
</head>
'''%(sSiteId, sCssLink))
	
	pout('<body>')

	U.page.header(dConf, fLog, sTitle)
	
	# Add side navigation bar to top level categories, need to put this in a
	# libray call
	pout('<div class="main">')
	
	U.page.sidenav(dConf, fLog)
	
	pout('<div class="article">')


def _postArticle(U, dConf, fLog):
	# END Article Div, and Main DIV ######################################### #
	pout('  </div>\n</div>\n') 
	
	U.page.footer(dConf, fLog)

	pout('''</body>
</html>''')


def printForm(U, dConf, fLog):

	_preArticle(U, dConf, fLog, "<i>das2</i> Validation Service")

	sScriptURL = U.webio.getScriptUrl()

	pout('''
	<p>
	Check the format of a das2/v2.2 or das2/v2.3-basic stream.  This validator
	can parse the following mime types:</br></br>
	<i>das2</i> text stream: <code><b>text/vnd.das2.das2stream; charset=utf-8</b></code> (*.d2t)<br>
   <i>das2</i> binary stream: <code><b>application/vnd.das2.das2stream</b></code> (*.d2s)<br>
   </p>

	<h2>Select a file to Upload</h2>
	<p>
	Upload a stream file for validation.  Only the first megabyte of 
	the uploaded file will be scanned.
	</p>
	<form enctype="multipart/form-data" method="post" action="%s/verify" >

   <div class="flex-container">
   <input type="file" name="file" required>
   <input type="submit" value="Validate">
   </div>
   <input type="checkbox" name="strict" value="yes">
   Treat extensions as errors (strict mode)
   
   <!--
   <input type="checkbox" name="src_node" value="yes">
   Check here if testing a catalog data source node.<br>
   -->
   
   <input hidden="hidden" name="what" value="file">
</form>
	'''%sScriptURL)

	_postArticle(U, dConf, fLog)

	return 0

# ########################################################################### #

def prnErrorContext(curPkt, nLine):
	sHdr = curPkt.content.decode('utf-8')
	lLines = sHdr.split('\n')

	for i in range(len(lLines)):
		# Trim long lines at 80 characters
		if len(lLines[i]) > 80:
			sLine = lLines[i][:76] + " ..."
		else:
			sLine = lLines[i]
			
		# If we have a valid line number only print within 6 lines each 
		# way of the header
		if (nLine > 0) and abs(nLine - (i+1)) > 6: continue
		
		if i + 1 == nLine:
			pout("    %3d---> %s"%(i+1, sLine))
		else:
			pout("    %3d     %s"%(i+1, sLine))


# ########################################################################### #

def validateFile(U, dConf, fLog, form):

	formItem = form['file']
	sFile = formItem.filename
	fIn = formItem.file
	
	bStrict = False
	sSchemaDir = '/space/html/das2/verify'
	sExpect = None
	sSchema = None
	bPrnHdr = False
	
	# Same parsing state info to help with exception output
	curPkt = None
	sCurType = None
	dDataPktCount = {}
	
	try:
		reader = das2.PacketReader(fIn, bStrict)
		
		sStreamContent, sStreamVer, bVarTags = reader.streamType()
		
		if sStreamContent != 'das2':
			pout("This is a %s stream, expected a das2 stream"%sStreamContent)
			return (5, None)
		
		if sExpect and (sExpect != sStreamVer):
			pout("%s: is a %s stream, but %s was expected"%(
				sFile, sStreamVer, sExpect
			))
			return (5, None)
		
		(schema, loc) = das2.loadStreamSchema(sStreamVer, bStrict)
		pout("Loaded XSD: %s"%bname(loc))
		
		for pkt in reader:
			curPkt = pkt
			
			if isinstance(pkt, das2.DataPkt):
				dDataPktCount[pkt.id] += 1
				continue
		
			if bPrnHdr:
				pout(pkt.content)
								
			docTree = pkt.docTree()
			elRoot = docTree.getroot()
			sCurType = elRoot.tag   # wtf is this???
			
			schema.assertValid(docTree)
			
			if isinstance(pkt, das2.DataHdrPkt):
				dDataPktCount[pkt.id] = 0
				pout("|%s| ID %s %s header [OKAY] (data size %d bytes)"%(
					pkt.tag, pkt.id, sCurType, pkt.baseDataLen()
				))
			else:
				pout("|%s| ID %s %s header [OKAY]"%(pkt.tag, pkt.id, sCurType))
				
			curPkt = None
			sCurType = None
	
	except(
		ValueError, etree.XMLSyntaxError, etree.DocumentInvalid, 
		xml.parsers.expat.ExpatError
	) as e:
		if curPkt:
			if sCurType:
				pout("|%s| ID %s %s header [ERROR] (context follows)"%(curPkt.tag, curPkt.id, sCurType))
			else:
				pout("|%s| ID %s data [ERROR]"%(pkt.tag, pkt.id))
			
		# Try to get last line with an error
		nLine = -1
		if isinstance(e, (etree.XMLSyntaxError, etree.DocumentInvalid)):
			#pout(e.error_log)
			nLine = e.error_log[-1].line
		elif isinstance(e, xml.parsers.expat.ExpatError):
			nLine = e.lineno
		
		# Print context if we can get it
		if curPkt and (curPkt.tag not in ('Dx','Qd')):
			try:
				prnErrorContext(curPkt, nLine)
			except:
				# Assumption here
				pout("Header packet %s%d is not valid UTF-8 text"%(
					curPkt.tag, curPkt.id))
		
		# Hack the non-existent 'p' element back out of any das2.2 error messages
		sErr = str(e)
		if sStreamVer == '2.2' and sErr.startswith("Element 'p',"):
			sFind ="Element 'p', attribute 'type': [facet 'enumeration'] The value"
			sRep = "Element 'properties', the attribute qualifier"
			sErr = sErr.replace(sFind, sRep)
		pout(sErr)
		if not curPkt:
			pout("No current packet, this usually means the packet tag length value is incorrect.")
		
		#pout(type(e), "\n   dir:", dir(e.error_log[-1]), '\n   msg:', e.error_log[-1].message)
		#pout("Error in %s:\n%s"%(sFile, str(e)))
		return (5, sStreamVer)
				
	for nId in dDataPktCount:
		pout("|Dx| ID %d %d data packets [OKAY]"%(nId, dDataPktCount[nId]))
	
	if bStrict:
		pout('Stream validates as a strict %s version %s stream without extensions\n'%(
			sStreamContent, sStreamVer))
	else:	
		pout('Stream validates as a %s version %s stream\n'%(
			sStreamContent, sStreamVer))

	return (0, sStreamVer)

# ########################################################################### #

def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):


	# Check authorization to even know about the verify link
	if ('ALLOW_VALIDATE_FROM' not in dConf):
		dConf['ALLOW_VALIDATE_FROM'] = '127.0.0.1/8 ::1'

	if ('REMOTE_ADDR' not in os.environ) or \
		(not U.auth.addrInRange(fLog, os.environ['REMOTE_ADDR'], dConf['ALLOW_VALIDATE_FROM'])):
		notFoundError(fLog, "/verify not found")
		return 0
	
	if not U.misc.isTrue('ENABLE_VALIDATOR', dConf):
		return sendDisabled(fLog, dConf)
		
	if 'file' not in form:
		return printForm(U, dConf, fLog)


	# Main section, processing...

	# Need to include options here to generate a plain report without all the
	# extra browser crud.
	_preArticle(U, dConf, fLog, "<i>das2</i> Validation Service")
	
	formItem = form['file']

	pout("<h2>Validation Report for %s</h2>\n\n"%formItem.filename)
	pout("<pre>")

	(nRet, sStreamVer) = validateFile(U, dConf, fLog, form)

	pout("</pre>")

	sSchema = das2.getSchemaName(sStreamVer)
	if nRet == 0:
		pout('''
		<p>Validation successful!</p>
		<ul>
			<li>All stream headers validate again schema <b>%s</b>.<br><br></li>
			<li>All stream packets are consistent with the given headers</li>
		</li>
		</p>
		'''%sSchema)
	else:
		pout('<p class="error">Validation Errors were detected</p>')
		pout('<ul>')
		if sStreamVer:
			pout('<li>Validation failed against schema <b>%s</b>.</li>'%sSchema)
		else:
			pout('<li>Could not determine the stream type.</li>')
		pout('</ul>')

	_postArticle(U, dConf, fLog)

	return nRet

