"""Default request handler for running Das2 readers"""

import sys
import platform
import os
import json

from os.path import basename as bname
from os.path import join as pjoin
from urllib.parse import quote_plus as urlEnc
from urllib.parse import unquote_plus as urlDec

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

# ########################################################################## #

def _getInternal(U, fLog, dConf, sPathInfo):
	"""Returns (dInternal, sConvention)
	"""
	
	if sPathInfo.startswith('/source/'):   # Knock off leading '/source'
		sLocalId = sPathInfo[len('/source/'):]
	else:
		U.webio.queryError(fLog, 
			"Invalid data request, path did not begin with '/source/'"
		)
		return (None,None)

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
		U.webio.notFoundError(fLog, "There is no data source at '%s'"%sPathInfo)
		return (None, None)

	try:
		with open(sInternal, 'r') as fIn:
			dIntern = json.load(fIn)
	except Exception as e:
		fLog.write("   ERROR: %s"%str(e))
		sContact = ''
		if 'CONTACT_URL' in dConf:
			sContact = 'at <a href="%s">%s</a'%(dConf['CONTACT_URL'],dConf['CONTACT_URL'])
		elif 'CONTACT_EMAIL' in dConf:
			sContact = 'at <a href="mailto: %s>%s</a>'%(dConf['CONTACT_EMAIL'],dConf['CONTACT_EMAIL'])
		U.webio.serverError(fLog, 
			"There is an internal problem with this data source, please contact "+\
			"the server administrator%s"%sContact
		)
		return (None, None)

	return (dIntern, sConv)


# ########################################################################## #
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""Run a command pipeline and stream the result as an http message body.
	
	Args:
		See das2server.handlers.intro.py for a decription of this function
		interface
	"""

	fLog.write("\ndas3 data request handler")

	if 'DATASRC_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DATASRC_ROOT not set in %s"%dConf['__file__'])
		return 17

	if sys.platform.startswith('win'):
		U.webio.todoError(fLog, "Not yet compatible with windows:\n"+\
	     	"Change the shell pipelines to use the python subprocess module "+\
			"before running on windows."
		)
		return 7

	(dSrc, sConv) = _getInternal(U, fLog, dConf, sPathInfo)
	if not dSrc:
		return 7

	# Get all the query keys as a dictionary, and preform translations.
	# Ignore:
	#   Form keys that upload files
	#   Form keys that are empty

	dParams = {}
	if ('default' in dSrc) and (sConv in dSrc['default']):  # Insert convention keys
		dInsert = dSrc['default'][sConv]
		for sParam in dInsert:
			dParams[sParam] = dInsert[sParam]

	dTranslate = {}
	if ('translate' in dSrc) and (sConv in dSrc['translate']):
		dTranslate = dSrc['translate'][sConv]

	for sKey in form.keys():
		if form[sKey].file: continue
		sVal = form.getfirst(sKey, None)
		if sVal:
			if sKey in dTranslate:
				if dTranslate[ sKey ]: # Some items map away to nothing
					dParams[ dTranslate[ sKey ] ] = sVal
			else:
				dParams[sKey] = sVal

	# For now just be a dummy and check on the reader and the formatters.
	# Fancier things like PSD can wait.

	# See if a unique reader is triggered.
	lRdrs = [dRdr for dRdr in dCmds['read'] if _isTriggered(dRdr, dParams) ]
	
	if len(lRdrs) == 0:
		U.webio.queryError("Insufficent information required to generate requested data stream")
		return 12
	
	lFmtrs = []
	if 'format' in dCmds: lFmtrs = dCmds['format']
	if len(lRdrs) > 1:

		# Eliminate readers that can't get to the desired output format via formatters
		# the desired format is carried by:  format.type, format.version, format.serial.
		lRdrs = [dRdr for dRdr in lRdrs if _canProduce(dRdr, dParams, lFmtrs)]

		if len(lRdrs) == 0:
			U.webio.queryError("Unable to create desired output type from this data source.")
			return 12

	# If we still have more then one reader, order by number of pipeline stages
	# and use the first one that works
	lCmds = []
	if len(lRdrs) > 1:


	
	fLog.write("   Exec Host: %s"%platform.node())
	fLog.write("   Exec Cmd: %s"%uCmd)
		
	(sMimeType, sContentDis, sFileExt) = U.webio.getOutputMime(sOutCat, sOutFmt)
		
	# Generate a filename
	sFnBeg = sBeg.replace(":","-").replace(".000Z", "").replace("T00-00-00","")
	sFnEnd = sEnd.replace(":","-").replace(".000Z", "").replace("T00-00-00","")
	sOutFile = "%s_%s_%s.%s"%(bname(sDsdf).replace('.dsdf',''), 
	                          #sBeg.replace(':','_'), sEnd.replace(':','_'),
									  sFnBeg, sFnEnd, sFileExt)
	fLog.write(u"   Filename: %s"%sOutFile)
	
	(nRet, sStdErr, bHdrSent) = U.command.sendCmdOutput(
		fLog, sCmd, sMimeType, sContentDis, sOutFile
	)

	if nRet != 0:
		U.webio.serverError(
			fLog, 
			u"exec: %s\n%s\nNon-zero exit value, %d from pipeline"%(uCmd, sStdErr, nRet ), 
			bHdrSent
		)
	
	return nRet
