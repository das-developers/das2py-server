"""Default request handler for server side image generation"""

import sys
import platform
import subprocess
import platform
import os

from os.path import join as pjoin
from os.path import basename as bname

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.handlers.intro.py for a decription of this function
	interface
	"""
	
	sDsdf = form.getfirst('dataset', '')
	
	fLog.write("\nDas 2.1 Dataset Handler")
	
	if sys.platform.startswith('win'):
		U.webio.todoError(fLog, u"Not yet compatible with windows:\n"+\
		      u"Change the shell pipelines to use the python subprocess "+\
				u"module before running on windows.")
		return 7	
	
	if 'DATASRC_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DATASRC_ROOT not set in %s"%dConf['__file__'])
		return 17
					
	# All das2.1 queries require a start and end time
	sBeg = form.getfirst('start_time','')
	sEnd = form.getfirst('end_time','')
	sRes = form.getfirst('resolution', '')
	sParams = form.getfirst('params','')
		
	if sRes == '':
		sRes = form.getfirst('interval', '')
		
	if sBeg == '':
		U.webio.queryError(fLog, u"Invalid das2.1 query, start_time was not specified")
		return 17
	if sEnd == '':
		U.webio.queryError(fLog, u"Invalid das2.1 query, end_time was not specified")
		return 17
	
	# Okay this looks like a decent query, load the dsdf
	dDsdf = U.dsdf.load(fLog, dConf, form, sDsdf)
	if dDsdf == None:
		return 17
		
	# Handle redirects, if these are not being ignored	
	if 'IGNORE_REDIRECT' not in dConf or \
	   not U.dsdf.isTrue('IGNORE_REDIRECT', dConf):
		if u'server' in dDsdf:	
			sScriptStr = U.webio.getScriptUrl()
			sDsdfScriptStr = dDsdf[u'server'].encode('ascii', 'replace')
			if sScriptStr != sDsdfScriptStr:
				sRefer = getUrl().replace(sScriptStr, sDsdfScriptStr)
				
				pout("Status: 301 Permanently moved")
				pout("Location: %s\r\n"%sRefer)
			
				return 0
	
	if 'PNG_MAKER' not in dConf:
		U.webio.todoError(fLog, u"Set the keyword PNG_MAKER in %s to "%dConf['__file__'] +\
		               u"generate server side images.")
		return 17
		
	
	sTmpDir = dConf['LOG_PATH']
	sMaker = dConf['PNG_MAKER']

	# Need two image names, one for output and another for
	sDiskImage = bname(sDsdf).replace('.dsdf','')
	sOutImage = "%s_%s_%s.png"%(sDiskImage, sBeg, sEnd)
	sDiskImage = "%s_%d.png"%(sDiskImage, os.getpid())
	sDiskImage = pjoin(sTmpDir, sDiskImage)

	uCmd = u"%s server=%s dataset=%s start_time=%s end_time=%s image=%s 'params=%s'"%(
		      sMaker, U.webio.getScriptUrl(), sDsdf, sBeg, sEnd, 
				sDiskImage, sParams)
	
	
	fLog.write(u"   Exec Host: %s"%platform.node())
	fLog.write(u"   Exec Cmd: %s"%uCmd)
		
	# Change shell=False, and fix fillDsdfDefaults to work on windows
	proc = subprocess.Popen(uCmd, shell=True, stdout=None, 
	                        stderr=subprocess.PIPE)
	sLog = proc.communicate()[1]
		
	if proc.returncode != 0:
		U.webio.serverError(fLog, u"%s\nNon-zero exit value, %d from image generator %s"%(
				sLog, proc.returncode, sMaker))
		return 17
		
	if not os.path.isfile(sDiskImage):
		U.webio.serverError(fLog, u"%s\nExpected image file %s is not present."%(
		                 sLog, sDiskImage))
		return 17
			
	# Save image maker output in the case that everything worked
	fLog.write(sLog)
	
	pout("Content-Type: image/png")
	pout("Expires: now")
	pout("Content Disposition: inline; filename=%s.png\r\n"%sOutImage)
	
	fImg = open(sDiskImage, 'rb')
	if sys.version_info[0] == 2:
		sys.stdout.write(fImg.read())
	else:
		sys.stdout.buffer.write(fImg.read())
	fImg.close()
	
	# Could build up a cache of these, at least temporarily...
	os.remove(sDiskImage)	
	
	return 0
	
