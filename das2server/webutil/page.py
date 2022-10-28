"""Utilities to help with page display for browser based das2 server users"""

import os
import sys
from os.path import join as pjoin
import json

from . import webio

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

##############################################################################
# Provide a list of name and directory tuples from a given data level

def isVisible(sDsdfFile):
	if not os.path.isfile(sDsdfFile): return False
	
	try:
		fIn = open(sDsdfFile, 'r')

		for sLine in fIn:
			if sLine.find('#') != -1:
				sLine = sLine[: sLine.find('#') ]
			sLine = sLine.strip()
			if sLine.startswith('hidden'):
				lLine = [s.strip().strip("'") for s in sLine.split('=')]
				if len(lLine) > 1:
					if lLine[1].lower() in ('yes','true','1'):
						fIn.close()
						return False;

		fIn.close()
	except:
		return False
	return True

# ########################################################################## #

def getWebTargets(dConf, fLog, sRelPath):
	"""Get a list of display names, filesystem names and links and names for
   everything at a particular level
	
	Args:
	   dConf (dict):   Server configuration

	   fLog  (object): An object with a .write method

		sRelPath (str): Level under SCRIPT/source, use a '/' to get information
		   for the top of the dsdf root
   
   Returns [(str, str, str)]: A list of the: 
      Item label, the sub-relative path (for recursive calls), the URL target
	"""

	if 'DATASRC_ROOT' not in dConf:
		fLog.write("   ERROR: Configuration item DATASRC_ROOT missing")
		return None

	sCatRoot = dConf['DATASRC_ROOT']
	
	if not os.path.isdir(sCatRoot):
		fLog.write("   ERROR: DATASRC_ROOT dir '%s' does not exist"%sCatRoot)
		return None
	
	if sRelPath == '/':
		sPath = pjoin(sCatRoot, 'root.json')
	else:
		sMiddle = sRelPath.strip('/').replace('/', os.sep)
		sPath = pjoin(sCatRoot, 'root', sMiddle + ".json")
		
		sRelPath = "/%s/"%(sRelPath.strip('/'))
		
	if not os.path.isfile(sPath):
		fLog.write("   ERROR: Catalog node '%s' does not exist"%sPath)
		return None
	
	lOut = []
	
	try:
		with open(sPath) as fIn:
			dCat = json.load(fIn)
	except Exception as e:
		fLog.write("   ERROR: %s"%str(e))
		return None

	if ('catalog' not in dCat) or (len(dCat['catalog']) == 0):
		fLog.write("   WARN: Catalog node '%s' is empty"%sPath)
		return None

	#fLog.write("   INFO: Listing items in %s for relpath %s"%(sPath, sRelPath))

	lItems = list(dCat['catalog'].keys())
	lItems.sort()
	lOut = []

	sScriptUrl = webio.getScriptUrl()
	
	# Don't open sub catlogs, just print details from this one
	for sItem in lItems:

		dItem = dCat['catalog'][sItem]
		sItemUrl = "%s/source%s%s.html"%(sScriptUrl, sRelPath, sItem)
	
		lOut.append( (dItem['label'], "%s%s"%(sRelPath, sItem), sItemUrl) )
	
	#fLog.write("TARGETS: %s"%str(lOut))
	return lOut

# ########################################################################## #

def header(dConf, fLog, sTitle=None): 
	"""Write a div with CSS class 'header'
		the div will contain 3 sub divs: hdr_left, hdr_center, hdr_right
	"""
	
	dReplace = {'script':webio.getScriptUrl()}
	
	if sTitle:
		dReplace['SITE_TITLE'] = sTitle
	elif 'SITE_TITLE' in dConf:
		dReplace['SITE_TITLE'] = dConf['SITE_TITLE']
	else:
		dReplace['SITE_TITLE'] = "Set SITE_TITLE in %s"%dConf['__file__']

	if 'SERVER_ID' in dConf:
		sServerId = dConf['SERVER_ID'].upper()
	else:
		sServerId = "{Set SERVER_ID in %s}"%dConf['__file__']
	dReplace['SERVER_ID'] = sServerId

	dReplace['SERVER_VER'] = "Das2/3"
	
	pout('''	
<div class="header">
	<div class="hdr_left">
		<a href="%(script)s/">
		<img src="%(script)s/static/logo.png" alt="%(SERVER_ID)s" >
		</a>
	</div> 
	<div class="hdr_center">
	%(SERVER_ID)s, a %(SERVER_VER)s Server
	<h1>%(SITE_TITLE)s</h1>
	</div>
	<div class="hdr_right">
		<a href="http://das2.org">
		<img src="%(script)s/static/das2logo_rv.png" alt="das2" width="80" height="80">
		</a>
	</div>
</div>
'''%dReplace)

##############################################################################
def allowViewLog(dConf, fLog, sIP):
	"""Check the config and see if sIP is allowed to view log files"""
	
	fLog.write("   WARNING: das2server.util.page.allowViewLog not implemented, always says yes")
	
	return True

# ########################################################################## #

def sidenav(dConf, fLog, bAddExtra=False):
	"""Write a div with CSS class 'nav' that includes the upper two levels
	of the data source hierarchy.

	Args:
		dConf - The server configuration file
		fLog  - A file-like object
		bAddExtra - If true extra logo's etc. are added.  This is useful when
		   a page header is not output.

	This div should be written inside your "main" div, before the central 
	'article' div is written
	"""
	
	sScriptUrl = webio.getScriptUrl()

	sValidationNav = ""
	if 'ENABLE_VALIDATOR' in dConf:
		sVal = dConf['ENABLE_VALIDATOR']
		if sVal.lower() in ('1','true'):
			sValidationNav = '<a href="%s/verify">Stream Validator</a>'%sScriptUrl

	sViewLogNav = ""
	if 'VIEW_LOG_URL' in dConf:
		if len(dConf['VIEW_LOG_URL']) > 0:
			sViewLogNav = '<a href="%s">Activity Log</a>'%dConf['VIEW_LOG_URL']

	pout('<div class="nav">')

	if bAddExtra:
		if 'SITE_TITLE' in dConf:
			sSite = dConf['SITE_TITLE']
		else:
			sSite = "Set SITE_TITLE in %s"%dConf['__file__']

		if 'SITE_URL' in dConf:
			sSite = '<a href="%s">%s</a>'%(dConf['SITE_URL'], sSite)

		if 'SERVER_NAME' in dConf:
			sServer = dConf['SERVER_NAME']
		elif 'SERVER_ID' in dConf:
			sServer = dConf['SERVER_ID'].upper()
		else:
			sServer = "{Set SERVER_NAME in %s}"%dConf['__file__']
			
		pout('''<b>%s</b><br>
<a href="%s/">
<img src="%s/static/logo.png" alt="%s" height="64" ></a>
<br>
'''%(sSite, sScriptUrl, sScriptUrl, sServer))

		#pout('<hr>\n<i>%s</i>'%sServer)
	#else:
	pout('<hr>\n<i>Data Sources</i>')

	pout('<ul>')
	
	lTop = getWebTargets(dConf, fLog, '/')
	if lTop != None:
		for (sName, sPathName, sUrl) in lTop:
			pout('    <li><a href="%s">%s</a><br>'%(sUrl, sName))

			lSub = getWebTargets(dConf, fLog, sPathName)
			if lSub != None:
				for (sSubName, sSubPathName, sSubUrl) in lSub:
					pout('    &nbsp; &nbsp; <a href="%s">%s</a><br>'%(sSubUrl, sSubName))
			
			pout('   <br></li>')

	pout('  </ul><hr>')
	pout('<a href="%s/catalog.json">Full Catalog</a><br><br>'%sScriptUrl)
	pout('<a href="%s/nodes.csv">Catalog Nodes</a><br><br>'%sScriptUrl)
	pout('''%s<br><br>
  %s<br><br>
  <a href="%s/peers.xml">Peer Servers</a>
'''%(sValidationNav, sViewLogNav, sScriptUrl))

	# If no top header, then add das2-logo below with info link
	if bAddExtra:
		pout('''<hr>
<a href="http://das2.org">
<img src="%s/static/das2logo_rv.png" alt="das2" width="65" height="65">
</a>'''%sScriptUrl)

	pout('</div>')

# ########################################################################## #

def navheader(dConf, fLog, sPathInfo):
	"""Write an unordered list of the current source path as CSS style 'navlist'"""
	
	sScriptUrl = webio.getScriptUrl()
	
	sDataSet = sPathInfo.replace('/source/', '').replace('.html','')
	
	# Split the path up into parts that retain the trailing '/'
	lParts = sDataSet.split('/')
	
	if lParts[-1] == '/':
		lParts = lParts[:-1]
	
	if len(lParts) < 1:
		return
	
	# TODO: Consult the filesystem for each part and get the capitalization
	#       from there.
	
	pout('  <ul id="navlist">')
	if 'SERVER_NAME' in dConf:
		sTmp = dConf['SERVER_NAME']
		sTmp = sTmp[0].upper() + sTmp[1:]
		pout('    <li> <a href="%s">%s</a>'%(sScriptUrl, sTmp))
	else:
		pout('    <li> <a href="%s">This Server</a>'%sScriptUrl)
	
	nParts = len(lParts)
	for i in range(0, len(lParts)):
		sPart = lParts[i]
		sName = 	lParts[i].replace('_',' ')
		sName = sName[0].upper() + sName[1:]
		
		if i < (nParts - 1):
			sUrl = '%s/source/%s.html'%(sScriptUrl, '/'.join(lParts[:i+1]))
			pout('    <li> &gt; <a href="%s">%s</a></li>'%(sUrl, sName))
		else:
			pout('    <li> &gt; &nbsp; <i>%s</i></li>'%sName)
	
	pout('  </ul>')


# ########################################################################## #

def footer(dConf, fLog):
	"""write a div with CSS class 'footer'.  This shoudld be written after your
	main div."""
	
	pout('''<div class="footer">
  <div>More information about das2 can be found at:
  <a href="http://das2.org/">http://das2.org/</a>.</div>
  <div>%s</div>
</div>'''%os.getenv('SERVER_SIGNATURE'))
