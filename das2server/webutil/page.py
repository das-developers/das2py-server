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

def _unquote(sVal):
	if (len(sVal) > 0) and (sVal[0] == '"') and (sVal[-1] == '"'):
		sVal = sVal[1:-1]
	return sVal.replace('""','"')

def _parseCatRows(lRows):
	"""Handle CSV escapes etc. to parse a row of csv data.  if it's not a 
	catalog item, ignore it.  This is the tightest CSV parser I've seen,
	should prob post it somewhere for closer inspection.
	"""
	llOut = []

	for sRow in lRows:
		lRow = []
		bInQuote = False
		iBeg = 0
		iEnd = 0
		nLen = len(sRow)
		while(iEnd < nLen):
		
			if (sRow[iEnd] == ',') and (not bInQuote):
				lRow.append( _unquote(sRow[iBeg:iEnd]) )
				iBeg = iEnd + 1

			elif sRow[iEnd] == '"':
				bInQuote = not bInQuote

			iEnd += 1

		# Handle last item
		lRow.append(_unquote(sRow[iBeg:iEnd]))

		# Ignore stuff I don't care about
		if (len(lRow) > 1) and (len(lRow[0]) > 0) and (lRow[1] in ('Catalog','SourceSet')):
			llOut.append(lRow)

	return llOut


def pullNavItems(dConf):
	""" Get a list of side name items based off the nodes.csv file  Reading
	this one file is faster then looking at a lot of disk locations.
	Args:
		dConf - Server config (could be cashed)

	Returns list( (sName, nIndent, sUrl) ): 
		A list of navigation items that should be around 20 items long
	"""

	LOCAL_ID  = 0
	TYPE      = 1
	TITLE     = 2
	URL       = 3
	ITEM_MIME = 4
	PROV_MIME_0 = 5

	sNodes = pjoin(dConf['DATASRC_ROOT'], 'nodes.csv')
	with open(sNodes, 'r') as fIn:
		lRows = [s.strip() for s in fIn.read().split('\n')]
	
	llRows = _parseCatRows(lRows)  # pull out the catalog items

	dLevels = {}                   # key = level, val = count
	for i in range(len(llRows)):
		lRow = llRows[i]

		iLevel = lRow[LOCAL_ID].count('/')
		if iLevel in dLevels: dLevels[iLevel] += 1
		else: dLevels[iLevel] = 1

	if len(dLevels) == 0:  # No data sources !!!
		return []

	nMaxCatLevels = max(dLevels.keys()) + 1
	lLevels = [0]*(nMaxCatLevels)  # Make into a list
	for i in range(nMaxCatLevels):
		lLevels[i] = dLevels[i]

	# How far can I go down the list and be less than 40 ?
	iMaxPrnLevel = -1
	nTotal = 0
	
	for i in range(len(lLevels)):
		if lLevels[i] + nTotal < 50:
			iMaxPrnLevel += 1
			nTotal += lLevels[i]
		else:
			break

	# Always show at least the first level no matter how crazy big it is
	if iMaxPrnLevel < 0: iMaxPrnLevel = 0 

	# Now Build the output down to level X
	lOut = []
	for i in range(len(llRows)):
		lRow = llRows[i]
		iLevel = lRow[LOCAL_ID].count('/')
		if iLevel > iMaxPrnLevel:
			continue

		#print(lRow)
		sPage = lRow[URL].replace('.json','.html')
		lOut.append( (lRow[LOCAL_ID].split('/')[-1], iLevel, sPage) )

	return lOut

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

	# Returns an ordered list of: (sName, nIndent, sUrl) 
	# Uses fuzzy algorithm to decide how many levels to decend
	lItems = pullNavItems(dConf)

	pout('<hr>\n<i>Data Sources</i>')

	if len(lItems) == 0:
		pout("<br><br><b>None Defined!</b><i><br>Use <tt>dasflex_sdef</tt>"+\
		     "<br>to import<br>definitions.</i><br><br>")
	else:
		pout('<ul>')
		for i in range(len(lItems)):
			(sName, nIndent, sUrl) = lItems[i]
			if nIndent == 0:
				if i > 0: pout('   <br></li>') # Close previous top level

				pout('    <li><a href="%s">%s</a><br>'%(sUrl, sName))
			else:
				sIndent = "&nbsp;&nbsp;"*nIndent
				pout('    %s<a href="%s">%s</a><br>'%(sIndent, sUrl, sName))

		if len(lItems) > 0: pout('   <br></li>')
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
