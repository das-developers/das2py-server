"""Default Handler for the resource file interface"""

import sys
import os.path
import mimetypes

from os.path import join as pjoin
from os.path import basename as bname

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface
	"""
	
	#TODO: Handle directory listings as long as they are not in the root
	# of resource
	
	sResource = sPathInfo.replace('/resource/', '')
		
	sFile = pjoin(dConf['RESOURCE_PATH'], sResource)
	
	#fLog.write("\nResource Handler\n   Sending: %s"%sFile)
	
	if not os.path.isfile(sFile):
		U.io.serverError(fLog, u"Resource '%s' doesn't exist"%sResource)
		return 17
		
	# Handle our own mime types...
	tRet = U.io.getMimeByExt(sFile)
	if tRet != None:
		#fLog.write("tuple->'%s'"%str(tRet))
		(sType, sContentDis, sFileExt) = tRet
		
		sOutFile = bname(sFile)
		
		pout("Content-Type: %s"%sType)
		pout('Content-Disposition: %s; filename="%s"\r\n'%(sContentDis, sOutFile))
		
	else:
		(sType, sEncode) = mimetypes.guess_type(sFile)
		if sType == None:
			U.io.serverError(fLog, u"Unrecognized mime type for %s"%sFile)
			return 17
		
		pout("Content-Type: %s\r\n"%sType)
				
	
	fIn = file(sFile, 'rb')
	sys.stdout.write(fIn.read())
	
	return 0

