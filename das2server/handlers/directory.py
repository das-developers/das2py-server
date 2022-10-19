"""Default handler for das3 style catalog level lists"""

import sys
import codecs
import os
from datetime import datetime
import json

from os.path import join as pjoin
from os.path import dirname as dname
from os.path import basename as bname

# NEW VERSION STARTS HERE #

# Copy in from das2server.util.catalog.py
g_sStdDas1 = 'das1.pro'
g_sStdDas2 = 'das2.d2t'
g_sStdDas3 = 'das3.json'
g_sStdRt   = 'das3rt.json'
g_sStdHapi2 = 'hapi2.json'
g_sStdVo  = 'voservice.xml'
g_sStdIntern = 'internal.json'

# ########################################################################## #
# Helpers #

def _errResponse(U, fLog, lHdrs, sReponse):
	U.webio.pout("%s\r\n\r\n"%("\r\r".join(lHdrs)))
	if sResponse:
		U.webio.pout(sResponse)
	return 3

def _getUtcMod(sPath):
	s = datetime.utcfromtimestamp(os.path.getmtime(sPath)).strftime('%Y-%m-%d %H:%M:%S')
	return "%s UTC"%s

def _getSize(sPath):
	"""Return a file size string that always takes up 4 spaces"""
	if not os.path.isfile(sPath): return "";

	lUnit = [" ","K","M","G","T","P"]

	rSz = float(os.path.getsize(sPath))

	iUnit = 0
	while rSz > 1000:
		rSz /= 1000
		iUnit += 1

	nSz = int(rSz)
	if nSz < 10:
		return "%.1f%s"%(rSz, lUnit[iUnit])
	if nSz < 100:
		return " %.0f%s"%(rSz, lUnit[iUnit])
	else:
		return "%.0f%s"%(rSz, lUnit[iUnit])

def _loadJson(sInPath):
	"""The missing 1-liner from the json module"""
	with open(sInPath) as fIn:
		dObj = json.load(fIn)
	return dObj


def _sortKey(sThing):
	if sThing.endswith('.json'): return sThing.replace('.json','_1')
	return sThing + '_2'

# ########################################################################## #
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.handlers.intro.py for a decription of this function
	interface.

	The job of this source is to create directory listings to assist wget
	of pages from a das server
	"""
	sRequestUrl = "%s%s"%(U.webio.getScriptUrl(), os.getenv("PATH_INFO"))

	sNotFound = "Directory %s does not exist on this server."%sRequestUrl
	lNotFound = [
		"Status:  404 Not Found",
		"Content-Type: text/plain; charset=utf-8",
		"Expires: now"
	]
	lSrvErr = [
		"Status:  500 Internal Server Error",
		"Content-Type: text/plain; charset=utf-8",
		"Expires: now"
	]
	lDenied = [
		"Status: 403 Forbidden",
		"Content-Type: text/plain; charset=utf-8",
		"Expires: now"	
	]
	lOkay = [
		"Status: 200 "
	]
	
	if 'DATASRC_ROOT' not in dConf:
		return errResponse(lSrvErr, "DATASRC_ROOT not set in %s"%dConf['__file__'])
		
	#lOut = [] 
	#tData = ("%s/root/"%dConf['DATASRC_ROOT'], lOut, fLog)
	
	sWebPath = os.getenv("PATH_INFO")  # Knock off leading '/source'
	if sWebPath == '/source': sWebPath = '/source/'
	
	if not sWebPath.startswith('/source/'):
		return _errResponse(lNotFound, sNotFound)
	else:
		sDirPath = pjoin(dConf['DATASRC_ROOT'], 'root', 
			sWebPath[len('/source/'):].replace('/', os.sep)
		)
	
	if not os.path.isdir(sDirPath):
		return _errResponse(lNotFound, sNotFound)

	lOut = [
		"<!DOCTYPE html>","<html>","<head>","<title>Index of %s</title>"%sWebPath,
		"</head>","<body>","<h1>Index of %s</h1>"%sWebPath,
	]

	# Don't show the parent directory link if we are the top item.
	nMaxName = 0
	if sWebPath == '/source/': nMaxName = len("Parent Directory")

	# Before we can make the header row, we need to know the max length of any 
	# of our sub items.
	lItems = os.listdir(sDirPath)
	lItems = sorted(lItems, key=_sortKey)

	nMaxName = 0
	for sItem in lItems:
		# We only show: 
		#  files that don't start with the name 'internal'
		if sItem == g_sStdIntern: continue
		if len(sItem) > nMaxName: nMaxName = len(sItem)

	sNameCol = " Name" + " "*(nMaxName + 4)
	sModCol  = "   Last Modified          "
	sSizeCol = "    Size   "
	sDescCol = "Description"
	sStaticUrl = "%s/static"%(U.webio.getScriptUrl())

	lOut.append('<pre><img src="%s/blank.gif" alt="Icon ">%s%s%s%s<hr>'%(
		sStaticUrl, sNameCol, sModCol, sSizeCol, sDescCol
	))

	if sWebPath != '/source/':
		sUpUrl = "%s%s/"%(U.webio.getScriptUrl(), dname(sWebPath[:-1]))
		lOut.append(
			'<img src="%s/up22.png" alt="[PARENTDIR]"> <a href="%s">Parent Directory</a>\n'%(
			sStaticUrl, sUpUrl
		))
	else:
		sUpUrl = "%s"%(U.webio.getScriptUrl())
		lOut.append(
			'<img src="%s/up22.png" alt="[SERVERHOME]"> <a href="%s">Server Home</a>\n'%(
			sStaticUrl, sUpUrl
		))

	# Output grouped items
	for sItem in lItems:
		if sItem in ('.','..'): continue

		sSubPath = pjoin(sDirPath, sItem)
		if sItem == g_sStdIntern: continue
		sMod = _getUtcMod(sSubPath)

		sDesc = ""
		if os.path.isdir(sSubPath):
			
			if os.path.isfile(sSubPath + '.json'): 
				sDesc = "contents of %s.json"%bname(sSubPath)

			sMod = _getUtcMod(sSubPath)
			sName = '<a href="%s/">%s/</a>'%(sItem, sItem) + ' '*(nMaxName - len(sItem) + 8)
			lOut.append('<img src="%s/folder20.png" alt="[DIR]"> %s  %s      -    %s\n'%(
				sStaticUrl, sName, sMod, sDesc 		
			))

		else:
			sSize = _getSize(sSubPath)
			sIcon = 'plot20.png'
			sFormRow = None
			if sItem == g_sStdDas1: sDesc = "das1 local source definition"
			elif sItem == g_sStdDas2: sDesc = 'das2 http/get source definition'
			elif sItem == g_sStdDas3: sDesc = 'das3 http/get source definition'
			elif sItem == g_sStdRt:   sDesc = 'das3 web socket source definition'
			elif sItem == g_sStdHapi2:sDesc = 'hapi2 source definition'
			elif sItem == g_sStdVo:   sDesc = 'IVOA service definition'
			elif sItem.endswith('.json'):

				if os.path.isdir(sSubPath.replace('.json','')):
					sIcon = 'globe22.png'
					
				try:
					dFile = _loadJson(sSubPath)
					if ('type' in dFile) and (dFile['type'] in ('Catalog','SourceSet')):
						sGuiDesc = 'interface for %s'%sItem
						sFormIcon = 'form20.png'
						sForm = sItem.replace('.json','.html')
						sFormName = '<a href="%s">%s</a> '%(sForm, sForm) + \
						   ' '*(nMaxName - len(sForm) + 8)
						sFormRow = '<img src="%s/%s" alt="[FORM]"> %s  %s      -    %s'%(
							sStaticUrl, sFormIcon, sFormName, sMod, sGuiDesc
						)
						sDesc = 'das %s object'%dFile['type']
				except:
					fLog.write("ERROR: %s is not a parsable JSON file"%sSubPath)

			sName = '<a href="%s">%s</a>'%(sItem, sItem) + ' '*(nMaxName - len(sItem) + 8)
			lOut.append('<img src="%s/%s" alt="[FILE]"> %s  %s    %s   %s'%(
				sStaticUrl, sIcon, sName, sMod, sSize, sDesc
			))

			if sFormRow: lOut.append(sFormRow)


	lOut +=['<hr></pre>','</body>','</html>']

	lHeaders = [
		"Status: 200 OK",
		'Access-Control-Allow-Origin: *',
		'Access-Control-Allow-Methods: GET',
		'Access-Control-Allow-Headers: Content-Type',
		'Content-Type: text/html; charset=utf-8'
		"Expires: now",
	]

	U.webio.pout("%s\r\n\r\n"%("\r\n".join(lHeaders)))
	U.webio.pout("\n".join(lOut))

	return 0
