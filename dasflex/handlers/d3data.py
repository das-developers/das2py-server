"""Default request handler for running Das2 readers"""

import sys
import platform
import os
import json

from os.path import basename as bname
from os.path import join as pjoin
from urllib.parse import quote_plus as urlEnc
from urllib.parse import unquote_plus as urlDec
from urllib.parse import parse_qsl as queryDec

U = None # Namespace placeholder for the webutil module

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')


# ########################################################################## #
def _localId(fLog, sPathInfo):

	if sPathInfo.startswith('/source/'):   # Knock off leading '/source'
		sLocalId = sPathInfo[len('/source/'):]
	else:
		U.webio.queryError(fLog, 
			"Invalid data request, path did not begin with '/source/'"
		)
		return None

	# Pop off the last item and use it as the form handling convertion (aka the
	# actual source type)
	if sLocalId.endswith('/'): sLocalId = sLocalId[-1]

	lLocalId = sLocalId.split('/')
	if len(lLocalId) < 2:
		U.webio.notFoundError(fLog, "Incomplete data source path.")
		return None

	sLocalId = '/'.join( lLocalId[:-1] )

	return sLocalId

# ########################################################################## #

def _getInternal(fLog, dConf, sPathInfo):
	"""load the json object describing internal operations for this data 
	source.

	Returns (dInternal, sConvention)
	"""
	
	if sPathInfo.startswith('/source/'):   # Knock off leading '/source'
		sLocalId = sPathInfo[len('/source/'):]
	else:
		U.webio.queryError(fLog, 
			"Invalid data request, path did not begin with '/source/'"
		)
		return (None, None)

	# Pop off the last item and use it as the form handling convertion (aka the
	# actual source type)
	if sLocalId.endswith('/'): sLocalId = sLocalId[-1]

	lLocalId = sLocalId.split('/')
	if len(lLocalId) < 2:
		U.webio.notFoundError(fLog, "Incomplete data source path.")
		return (None, None)

	sConv = lLocalId[-1].strip()
	sLocalId = '/'.join( lLocalId[:-1] )

	sInternal = "%s/root/%s/internal.json"%(dConf['DATASRC_ROOT'], sLocalId.lower())

	if not os.path.isfile(sInternal):
		U.webio.notFoundError(fLog, "There is no data source at '%s'"%sInternal)
		return (None, None)

	try:
		with open(sInternal, 'r') as fIn:
			fLog.write("   INFO: Loading %s"%sInternal)
			dIntern = json.load(fIn)
	except Exception as e:
		fLog.write("   ERROR: %s"%str(e))
		sContact = ''
		if 'CONTACT_URL' in dConf:
			sContact = ' at <a href="%s">%s</a'%(dConf['CONTACT_URL'],dConf['CONTACT_URL'])
		elif 'CONTACT_EMAIL' in dConf:
			sContact = ' at <a href="mailto: %s">%s</a>'%(dConf['CONTACT_EMAIL'],dConf['CONTACT_EMAIL'])
		U.webio.serverError(fLog, 
			"There is an internal problem with this data source, please contact "+\
			"the server administrator%s"%sContact
		)
		return (None, None)

	return (dIntern, sConv)

# ########################################################################## #

def _defaultName(fLog, dConf, dParams, sLocalId, dTargOut):
	"""No filename creation rules in source document so wing-it
	"""

	return "fixme_default_name.bin"

# ########################################################################## #

def _mkMsgBody(form, nCmdRet, bHdrSent):
	"""The command did not output a message body, do something so apache doesn't 
	freak out"""

	bOutHtml = False
	if not bHdrSent:
		if nCmdRet == 0:
			U.webio.pout('Status: 400 Bad Request\r\n')
		else:
			U.webio.pout('Status: 500 Internal Server Error\r\n')

		if U.webio.isBrowser():
			U.webio.pout("Content-Type: text/html\r\n\r\n")
			bOutHtml = True
		else:
			U.webio.pout("Content-Type: text/plain\r\n\r\n")

	sReferer = "the previous page"
	if 'HTTP_REFERER' in os.environ:
		sRef = os.environ['HTTP_REFERER']
	
	if bOutHtml:

		lParams = ['<li>URL = %s</li>'%(U.webio.getUrl()) ]
		for sKey in form.keys():
			if form[sKey].file: continue
			lParams.append("<li>%s = %s </li>"%(sKey, form.getfirst(sKey, None)))

		if nCmdRet == 0:
			U.webio.pout('''
<!DOCTYPE html>
<html><head><title>No Output</title></head>
<body>
<h3>Successfully Did Nothing</h3>
<p>The program servicing your request ran sucessfully, but produced no output.
Typically this happens when requesting a non-das format and there isn't any
data available that would satisfy the following request parameters:</p>
<ul>
%s
</ul>
<p>You could try returning to %s and selecting a different parameter range, 
or sending a message to the technical contact for this data source.</p>
</body>
</html>
'''%('\n'.join(lParams), sReferer))

		else:
			U.webio.pout('''
<!DOCTYPE html>
<html><head><title>No Output</title></head>
<body>
<h3>Query Processing Error</h3>
<p>The program servicing your request finished with an error code and produced
no output.  Typically this happens when requesting a non-das data format and
the server is misconfigured.<p>
<p>That's a bummer, but lets get this fixed.  Please contact the server
administrator and provide them with the following information:
<ul>
%s
</ul>
<p>Thanks for your help.</p>
</body>
</html>
'''%('\n'.join(lParams)) )

	else:
		lParams = [ 'URL = %s'%(U.webio.getUrl()) ]
		for sKey in form.keys():
			if form[sKey].file: continue
			lParams.append("%s = %s"%(sKey, form.getfirst(sKey, None)))

		if nCmdRet == 0:
			U.webio.pout('''
# Successfully Did Nothing
The program servicing your request ran sucessfully, but produced no output.
Typically this happens when requesting a non-das format and there isn't any
data available that would satisfy the following request parameters:

```
%s
```
You could try returning to %s and selecting a different parameter range, 
or sending a message to the technical contact for this data source.
'''%('\n'.join(lParams), sReferer))

		else:
			U.webio.pout('''
# Query Processing Error
The program servicing your request finished with an error code and produced
no output.  Typically this happens when requesting a non-das data format and
the server is misconfigured.

That's a bummer, but lets get this fixed.  Please contact the server
administrator and provide them with the following information:

```
%s
```

Thanks for your help.
'''%('\n'.join(lParams)))


# ########################################################################## #
def handleReq(modUtil, sReqType, dConf, fLog, form, sPathInfo):
	"""Run a command pipeline and stream the result as an http message body.
	
	Args:
		See dasflex.handlers.intro.py for a decription of this function
		interface
	"""

	global U
	U = modUtil

	fLog.write("\ndas flex data request handler")

	if 'DATASRC_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DATASRC_ROOT not set in %s"%dConf['__file__'])
		return 17

	if sys.platform.startswith('win'):
		U.webio.todoError(fLog, "Not yet compatible with windows:\n"+\
	     	"Change the shell pipelines to use the python subprocess module "+\
			"before running on windows."
		)
		return 7

	(dSrc, sConv) = _getInternal(fLog, dConf, sPathInfo)
	fLog.write("   INFO: Query convention is %s"%sConv)
	if not dSrc:
		return 7

	# Get all the query keys as a dictionary, and preform translations.
	# Ignore:
	#   Form keys that upload files
	#   Form keys that are empty

	dParams = {}
	if ('parameters' in dSrc) and ('defaults' in dSrc['parameters']) \
	   and (sConv in dSrc['parameters']['defaults']):  # Insert convention keys
		dInsert = dSrc['parameters']['defaults'][sConv]
		for sParam in dInsert:
			dParams[sParam] = dInsert[sParam]

	dTranslate = {}
	if ('parameters' in dSrc) and ('translate' in dSrc['parameters']) \
	   and (sConv in dSrc['parameters']['translate']):
		dTranslate = dSrc['parameters']['translate'][sConv]

	for sKey in form.keys():
		if form[sKey].file: continue
		sVal = form.getfirst(sKey, None)
		if sVal:
			if sKey in dTranslate:
				if dTranslate[ sKey ]: # Some items map away to nothing
					dParams[ dTranslate[ sKey ] ] = urlDec(sVal)
			else:
				dParams[sKey] = urlDec(sVal)

	# Get the triggered commands of each type
	lTmp = [ "%s=%s"%(sKey, dParams[sKey]) for sKey in dParams]
	fLog.write("   INFO: Solving command-line for params: %s"%(" ".join(lTmp)))
	try:
		lCmds = U.command.triggered(fLog, dSrc, dParams)
		sCmd = U.command.pipeline(fLog, lCmds, dParams)
	except U.errors.DasError as exc:
		U.webio.dasErr2HttpMsg(fLog, exc)
		return 17
	except Exception as exAll:
		U.webio.serverError(fLog, str(exAll))
		return 18

	if 'output' not in lCmds[-1]:
		sLocalId = _localId(fLog, sPathInfo)
		U.webio.serverError(fLog, "Output definition missing for command in %s"%sLocalId)
		return 19
	
	dTargOut = lCmds[-1]['output'] # output of last command is our type


	if ('files' in dSrc) and ('baseName' in dSrc['files']):
		(sMimeType, sContentDis, sOutFile) = U.command.filename(
			fLog, dConf, dParams, dSrc['files']['baseName'], dTargOut
		)
	else:
		sLocalId = _localId(fLog, sPathInfo)
		(sMimeType, sContentDis, sOutFile) = _defaultName(
			fLog, dConf, dParams, sLocalId, dTargOut
		)

	fLog.write("   Exec Host: %s"%platform.node())
	fLog.write("   Exec Cmd: %s"%sCmd)
		
	(nRet, sStdErr, bHdrSent, bMsgBody) = U.command.sendCmdOutput(
		fLog, sCmd, sMimeType, sContentDis, sOutFile
	)

	# If no headers have been sent, default to html
	if not bMsgBody:
		_mkMsgBody(form, nRet, bHdrSent)

	U.webio.flushOut()

	# Make sure the standard error output of the command shows up in the log
	for sLine in sStdErr.split('\n'):
		fLog.write(sLine.strip())

	# Code below ASSUMES that errors can be sent in either das2 or das3 format.
	# Don't make than assumption!  If the format is a das stream send data in
	# band, otherwise, don't send a message body

	if nRet != 0:
		sVer = ""
		if 'format.version' in dParams: sVer = dParams['format.version']

		U.webio.serverError(
			fLog, 
			"exec: %s\n%s\nNon-zero exit value, %d from pipeline"%(sCmd, sStdErr, nRet ), 
			bHdrSent,
			sVer
		)
	
	return nRet
