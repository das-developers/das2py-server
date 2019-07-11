"""Provides general functions to help with general web-site functionality.
These functions are not needed if the client is not a web browser, infact
they are not even loaded
"""

import sys
import os
import os.path

from os.path import join as pjoin
from os.path import dirname as dname

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
##############################################################################
# Provide a list of name and directory tuples from a given data level

def getDataDirs(U, dConf, fLog, sRelPath):
	"""Get a list of links and names for everything at a particular level
	
	sRelPath - Level under SCRIPT/source, use a '/' to get
	           information for the top of the dsid root
	"""

	sScriptURL = U.io.getScriptUrl()
	
	# Keep a list of directories

	if not dConf.has_key('DSDF_ROOT'):
		fLog.write("   ERROR: Configuration item DSDF_ROOT missing")
		return None

	sRoot = dConf['DSDF_ROOT']
	
	if not os.path.isdir(sRoot):
		fLog.write("   ERROR: DSID_ROOT dir '%s' does not exist"%sRoot)
		return None
	
	if sRelPath == '/':
		sPath = sRoot
	else:
		sPath = pjoin(sRoot, sRelPath)
		
	if not os.path.isdir(sPath):
		fLog.write("   ERROR: Data directory '%s' does not exist"%sPath)
		return None
	
	lOut = []
	
	lDirs = os.listdir(sPath)
	lDirs.sort()
	
	fLog.write("   INFO: Listing data in %s"%sPath)
	for sDir in lDirs:
		if not os.path.isdir( pjoin(sPath, sDir) ):
			continue
		
		bVisible = True
		sDirDsdf = pjoin(sPath, sDir, '_dirinfo_.dsdf')
		if os.path.isfile(sDirDsdf):
			try:
				fIn = file(sDirDsdf, 'rb')
				for sLine in fIn:
					if sLine.find('#') != -1:
						sLine = sLine[: sLine.find('#') ]
					sLine = sLine.strip()
					if sLine.startswith('browse'):
						lLine = [s.strip().strip("'") for s in sLine.split('=')]
						if len(lLine) > 1:
							if lLine[1].lower() in ('no','0'):
								bVisible = False
						break
			except:
				pass
									
		
		if bVisible:
			sUrl = '%s/source%s%s/'%(sScriptURL, sRelPath, sDir)
		
			sName = sDir.replace('_',' ').upper()
			lOut.append( (sName, sUrl) )
	
	
	return lOut

##############################################################################
def allowViewLog(dConf, fLog, sIP):
	"""Check the config and see if sIP is allowed to view log files"""
	
	fLog.write("   WARNING: das2server.util.site.allowViewLog not implemented, always says yes")
	
	return True
	

##############################################################################
# Helper for browseHeader, provides an optional header that shows the data
# hierarchy down to the current level

def _dataNavHeader(U, sReqType, dConf, fLog, form, sPathInfo):
	
	sScriptURL = U.io.getScriptUrl()
	
	sDataSet = sPathInfo.replace('/source/', '')
	
	# Split the path up into parts that retain the trailing '/'
	lParts = [ '%s/'%s for s in sDataSet.split('/')]
	
	if lParts[-1] == '/':
		lParts[-2] = "%s/"%(lParts[-2])
		lParts = lParts[:-1]
		
	if len(lParts) < 1:
		return
	
	pout('  <center><ul id="datanav">')
	
	
	for i in xrange(0, len(lParts)):
		sPart = lParts[i]
		sName = 	lParts[i].rstrip('/').replace('_',' ').upper()
		
		sUrl = '%s/data/%s'%(sScriptURL, ''.join(lParts[:i+1]))
		
		if i > 0:
			sSep = ' &gt '
		else:
			sSep = ''
			
		pout('    <li>%s<a href="%s">%s</a></li>'%(sSep, sUrl, sName))
	
	pout(' </ul></center>')
	
	

##############################################################################
# A general header for browser based access to the das22 server
def browserHeader(U, sReqType, dConf, fLog, form, sPathInfo):

	sScriptURL = U.io.getScriptUrl()
	
	if dConf.has_key('SITE_NAME'):
		sSiteId = dConf['SITE_NAME']
	else:
		sSiteId = "Set SITE_NAME in %s"%dConf['__file__']
	
	if dConf.has_key('STYLE_SHEET'):
		sCssLink = "%s/resource/%s"%(sScriptURL, dConf['STYLE_SHEET'])
	else:
		sCssLink = "%s/resource/das2server.css"%sScriptURL
	
	pout('Content-Type: text/html; charset=utf-8\r\n')
	pout('<html>')
	pout('<head>')
	pout('  <title>Das 2.3 Server</title>')
	pout('  <link rel="stylesheet" type="text/css" media="screen" href="%s" />'%sCssLink)
	pout('</head>')
	
	pout('<body>')
	
	pout('<div id="header">')
	pout('  <h1>')
	pout('  <img src="%s/logo" />'%sScriptURL)
	pout('%s</h1>'%sSiteId)
	pout('</div>')
	
	pout('<div id="sidenav">')
	pout('  <ul>')
	
	lTop = getDataDirs(U, dConf, fLog, '/')
	
	if lTop != None:
		for (sName, sUrl) in lTop:
			pout('    <li><a href="%s">%s</a></li>'%(sUrl, sName))
	
	#pout('    <li><a href="%s/server/examples">Queries</a></li>'%sScriptURL)
	
	#if dConf.has_key('VIEW_LOG_URL'):
	#	if len(dConf['VIEW_LOG_URL']) > 0:
	#		if allowViewLog(dConf, fLog, os.environ['REMOTE_ADDR']):
	#			
	#			if dConf['VIEW_LOG_URL'].find('//') == -1:
	#				sLogURL = "%s/%s"%(dname(sScriptURL), 	dConf['VIEW_LOG_URL'])
	#			else:
	#				sLogURL = dConf['VIEW_LOG_URL']
	#			
	#			pout('    <li><a href="%s">Server Log</a></li>'%sLogURL)
	
	pout('  </ul>')
	pout('</div>')
	pout('<div id="main">')
	
	if sPathInfo.startswith('/source/'):
		if sPathInfo != '/source/':
			_dataNavHeader(U, sReqType, dConf, fLog, form, sPathInfo)
	

##############################################################################
def browserFooter(U, sReqType, dConf, fLog, form, sPathInfo):
	
	pout("</ul>")
		
	pout("""
<h2>Documentation</h2>
<p>More information about das2 can be found at:
<a href="http://das2.org/">
  http://das2.org/</a>.
</p>
""")

	pout("<hr><p>%s</p>"%os.getenv('SERVER_SIGNATURE'))

	pout('</body></html>')


