"""Utilities to help with page display for browser based das2 server users"""

import os
import sys
from os.path import join as pjoin

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
	
	sRelPath - Level under SCRIPT/source, use a '/' to get
	           information for the top of the dsdf root
	"""

	sScriptURL = webio.getScriptUrl()
	
	# Keep a list of directories

	if 'DSDF_ROOT' not in dConf:
		fLog.write("   ERROR: Configuration item DSDF_ROOT missing")
		return None

	sRoot = dConf['DSDF_ROOT']
	
	if not os.path.isdir(sRoot):
		fLog.write("   ERROR: DSDF_ROOT dir '%s' does not exist"%sRoot)
		return None
	
	if sRelPath == '/':
		sPath = sRoot
	else:
		sPath = pjoin(sRoot, sRelPath)
		
	if not os.path.isdir(sPath):
		fLog.write("   ERROR: Data directory '%s' does not exist"%sPath)
		return None
	
	lOut = []
	
	lItems = os.listdir(sPath)
	lItems.sort()
	
	#fLog.write("   INFO: Listing items in %s for relpath %s"%(sPath, sRelPath))
	for sItem in lItems:
		sItemPath = pjoin(sPath, sItem)
		if os.path.isdir( sItemPath ):

			sDirDsdf = pjoin(sItemPath, '_dirinfo_.dsdf')
			if not isVisible(sDirDsdf): continue
			
			if(sRelPath == '/'):
				sUrl = '%s/source/%s/info.html'%(sScriptURL, sItem.lower())
			else:
				sUrl = '%s/source/%s/%s/info.html'%(sScriptURL, sRelPath.lower(), sItem.lower())
			
				
			sName = sItem.replace('_',' ')
			if sRelPath == '/':
				lOut.append( (sName, sItem, sUrl) )
			else:
				lOut.append( (sName, pjoin(sRelPath, sItem), sUrl) )

		elif os.path.isfile( sItemPath ):
			if not sItem.endswith(".dsdf"): continue
			if sItem == "_dirinfo_.dsdf": continue
			if not isVisible(sItemPath): continue

			sSrcDir = sItemPath.strip('.dsdf').lower();
			sUrl = '%s/source/%s/%s/form.html'%(
				sScriptURL, sRelPath.lower(), sItem.lower().replace('.dsdf','')
			)
			sName = sItem.replace('_',' ').replace('.dsdf','')
			if sRelPath == '/':
				lOut.append( (sName, sItem, sUrl) )
			else:
				lOut.append( (sName, pjoin(sRelPath, sItem), sUrl) )
	
	#for t in lOut:
	#	fLog.write(">>>lOut>>> %s"%str(t))
	#fLog.write("<<<")

	return lOut

# ########################################################################## #

def header(dConf, fLog): 
	"""Write a div with CSS class 'header'
		the div will contain 3 sub divs: hdr_left, hdr_center, hdr_right
	"""
	
	dReplace = {'script':webio.getScriptUrl()}
	
	if 'SITE_TITLE' in dConf:
		dReplace['SITE_TITLE'] = dConf['SITE_TITLE']
	else:
		dReplace['SITE_TITLE'] = "Set SITE_TITLE in %s"%dConf['__file__']

	if 'SERVER_ID' in dConf:
		sServerId = dConf['SERVER_ID'].upper()
	else:
		sServerId = "{Set SERVER_ID in %s}"%dConf['__file__']
	dReplace['SERVER_ID'] = sServerId

	dReplace['SERVER_VER'] = "Das2.3 (prototype)"
	
	pout('''	
<div class="header">
	<div class="hdr_left">
		<a href="%(script)s/">
		<img src="%(script)s/static/logo.png" alt="%(SERVER_ID)s" width="70" height="70" >
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

def sidenav(dConf, fLog):
	"""Write a div with CSS class 'nav' that includes the upper two levels
	of the data source hierarchy.

	This div should be written inside your "main" div, before the certral 
	'article' div is written
	"""
	
	sScriptUrl = webio.getScriptUrl()

	sViewLogNav = ""
	if 'VIEW_LOG_URL' in dConf:
		if len(dConf['VIEW_LOG_URL']) > 0:
			sViewLogNav = '<a href="%s">Activity Log</a>'%dConf['VIEW_LOG_URL']

	pout('<div class="nav"><i>Data Sources</i><hr>')
	pout('  <ul>')
	
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
	pout('<a href="%s/sources.csv">Catalog (csv)</a><br><br>'%sScriptUrl)
	pout('<a href="%s/sources.json">Catalog (das2)</a><br><br>'%sScriptUrl)
	pout('''%s
  <br><br>
  <a href="%s/peers.xml">Peer Servers</a>
</div>'''%(sViewLogNav, sScriptUrl))

# ########################################################################## #

def navheader(dConf, fLog, dsdf):
	"""Write an unordered list of the current source path as CSS style 'navlist'"""
	
	sScriptUrl = webio.getScriptUrl()
	
	sPathInfo = os.getenv("PATH_INFO")

	sDataSet = sPathInfo.replace('/source/', '')

	# Split the path up into parts that retain the trailing '/'
	lParts = [ '%s/'%s for s in sDataSet.split('/')]
	
	if lParts[-1] == '/':
		lParts[-2] = "%s/"%(lParts[-2])
		lParts = lParts[:-1]
	else:
		lParts = lParts[:-1]
	
	if len(lParts) < 1:
		return
	
	# TODO: Consult the filesystem for each part and get the capitalization
	#       from there.
	
	pout('  <ul id="navlist">')
	pout('    <li> <a href="%s">%s</a>'%(sScriptUrl, dConf['SERVER_ID']))
	
	for i in range(0, len(lParts)):
		sPart = lParts[i]
		sName = 	lParts[i].rstrip('/').replace('_',' ')
		
		sUrl = '%s/source/%s'%(sScriptUrl, ''.join(lParts[:i+1]))
			
		pout('    <li> &gt <a href="%s">%s</a></li>'%(sUrl, sName))
	
	pout(' </ul></center>')


# ########################################################################## #

def footer(dConf, fLog):
	"""write a div with CSS class 'footer'.  This shoudld be written after your
	main div."""
	
	pout('''<div class="footer">
  <div>More information about das2 can be found at:
  <a href="http://das2.org/">http://das2.org/</a>.</div>
  <div>%s</div>
</div>'''%os.getenv('SERVER_SIGNATURE'))