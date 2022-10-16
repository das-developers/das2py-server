"""Default handler for 3.0 style catalog level lists"""

import sys
import codecs
import os
import json

from os.path import join as pjoin			

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.handlers.intro.py for a decription of this function
	interface
	"""
	
	if 'DATASRC_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DATASRC_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	# _dirOut and _fileOut append a list of tuples to lOut
	
	lOut = [] 
	tData = ("%s/"%dConf['DATASRC_ROOT'], lOut, fLog)
	
	sPath = os.getenv("PATH_INFO")  
	
	U.webio.pout("Status: 200 OK\r\n")
	U.webio.pout('Access-Control-Allow-Origin: *\r\n')
	U.webio.pout('Access-Control-Allow-Methods: GET\r\n')
	U.webio.pout('Access-Control-Allow-Headers: Content-Type\r\n')	
	
	# Walk the tree, following symlinks
	U.misc.symWalk(fLog, dConf['DATASRC_ROOT'], _fileOut, _dirOut, tData)
	
	lOut.sort(key=_sortNoDesc)
	
	# By default, ignore everything
	lIgnore = [True]*len(lOut)
	
	# Loop through once to make sure directories are in use, don't include
	# empty directories in the output
	for i in range(0, len(lOut)):
	
		# Not a directory, keep it
		if lOut[i][0][-1] != u'/':
			lIgnore[i] = False
		
		# Is a directory, search down the sorted list until you find
		# a file for this directory, if you don't, then drop it.  Ignore
		# subdirectories in this search
		else:
			j = i + 1
			while (j < len(lOut)) and (lOut[j][0].startswith(lOut[i][0])):
				if lOut[j][0][-1] != '/':
					lIgnore[i] = False
					break
				j += 1
	
	sScriptURL = U.webio.getScriptUrl()

	# Output one of three versions:
   # (no path)     - old das2 list
	# /sources.csv  - New das3 list
	# /sources.json - New das3 catalog
	if sPath == "/sources.csv":
		U.webio.pout("Content-Type: text/csv; charset=utf-8\r\n")
		U.webio.pout("Status: 200 OK\r\n")
		U.webio.pout("Expires: now\r\n")
		U.webio.pout('Content-Disposition: attachment; filename="sources.csv"\r\n\r\n')

		U.webio.pout('"Name","Type","Description","Definition"\r\n');
		for i in range(0, len(lOut)):
			if lIgnore[i]: continue

			sName = '"%s"'%(lOut[i][0].replace('"','""'));

			if lOut[i][0].endswith('/'): 
				sType = '"cat"'
				sDef = "" # Directories don't get a URL
			else:
				sType = '"src"'
				
				if lOut[i][2] == None or lOut[i][2].startswith(sScriptURL):
					# This is one of mine
					sDef = '"%s/source/%s/dsdf.d2t"'%(sScriptURL, lOut[i][0].lower())
				else:
					# Somebody else's
					if lOut[i][3] == "das3":
						sDef = '"%s/source/%s/dsdf.d2t"'%(lOut[i][2], lOut[i][0].lower())
					else:
						sDef = '"%s/?server=dsdf&dataset=%s"'%(lOut[i][2], lOut[i][0])
			
			if lOut[i][1] == None: sDesc = ""
			else: sDesc = '"%s"'%(lOut[i][1].replace('"','""'))

			U.webio.pout("%s,%s,%s,%s\r\n"%(sName, sType, sDesc, sDef))

	elif sPath == "/sources.json":
		U.webio.pout("Content-Type: application/json; charset=utf-8\r\n")
		U.webio.pout("Status: 200 OK\r\n")
		U.webio.pout("Expires: now\r\n")
		U.webio.pout('Content-Disposition: inline; filename="sources.json"\r\n\r\n')
	
		if 'SITE_TITLE' in dConf: sSiteName = dConf['SITE_TITLE']
		else: sSiteName = 'local_site'
		dCatalog = {	
			'version':'0.5',
			'type':'Catalog',
			'name':dConf['SERVER_ID'],
			'title': "Data source catalog from das2 server %s at %s"%(
				dConf['SERVER_ID'], sSiteName
			),
			'catalog':{}
		}

		_addEntries(sScriptURL, lOut, lIgnore, dCatalog, fLog)
		
		sCat = json.dumps(dCatalog, ensure_ascii=False, sort_keys=True, indent=3)
		U.webio.pout(sCat)
		U.webio.pout('\n')

	else:
		U.webio.pout("Content-Type: text/plain; charset=utf-8\r\n")
		U.webio.pout("Status: 200 OK\r\n")
		U.webio.pout("Expires: now\r\n")
		U.webio.pout('Content-Disposition: inline; filename="sources.txt"\r\n\r\n')
		for i in range(0, len(lOut)):
			if not lIgnore[i]:
				if lOut[i][1] != None:
					s = u"%s|%s\r\n"%(lOut[i][0], lOut[i][1])
				else:
					s = u"%s\r\n"%lOut[i][0]
							
				U.webio.pout(s)
	
	return 0
