"""Default handler for 2.3 style catalog level lists"""

import sys
import codecs
import os
import json

from os.path import join as pjoin

##############################################################################
def _dirOut(sDirName, tData):
	
	sPrefix = tData[0]
	lOut = tData[1]
	fLog = tData[2]
	
	sDirInfo = pjoin(sDirName, '_dirinfo_.dsdf')
	
	# Replicating description finding code here instead of making a new 
	# function since the file version has to also look for rename strings
	# at the same time and we don't want to be looping through each file 
	# twice.
	sDescription = None
	try:
		fIn = codecs.open(sDirInfo, 'rb', encoding='utf-8')
		for sLine in fIn:
			iComment = sLine.find(u';')
			if iComment != -1:
				sLine = sLine[:iComment]
		
			if sLine.find(u'description') != -1:
				lLine = sLine.split(u'=')
				if len(lLine) > 1:
					sDescription = u"".join(lLine[1:])
					sDescription = sDescription.strip("\"' \r\n\t")
				break

	except IOError:
		pass
	
	sDataSrcDir = u"%s/"%sDirName.replace(sPrefix, '')
	lOut.append( (sDataSrcDir, sDescription, None, None)  )
		
	return (True, sDirName)
	

def _fileOut(sFileName, tData):
	
	sPrefix = tData[0]
	lOut = tData[1]
	fLog = tData[2]
	
	if not sFileName.lower().endswith('.dsdf'):
		return True
	
	if sFileName.lower().endswith('_dirinfo_.dsdf'):
		return True
		
	sDescription = None
	try:
		fIn = codecs.open(sFileName, 'rb', encoding='utf-8')
	except IOError:
		return True
	
	sServer = None
	sSrvType = None
	
	for sLine in fIn:
		iComment = sLine.find(u';')
		if iComment != -1:
			sLine = sLine[:iComment]
			
		if sLine.find(u'hidden') != -1:
			lLine = sLine.split('=')
			if len(lLine) > 1 and lLine[0].strip().lower() == 'hidden':
				fIn.close()
				return True			
		
		if sDescription == None and sLine.find(u'description') != -1:
			lLine = sLine.split(u'=')
			if len(lLine) > 1:
				sDescription = u"".join(lLine[1:])
				sDescription = sDescription.strip(u"\"' \r\n\t")
				continue
				
		if sLine.find(u'rename') != -1:
			lLine = sLine.split('=')
			if len(lLine) > 1 and lLine[0].strip().lower() == 'rename':
				fIn.close()
				return True
				
		if sLine.find(u'server') != -1:
			lLine = sLine.split(u'=')
			if len(lLine) > 1:
				sServer = lLine[1].strip(u"\"' \r\n\t")
				# If other server is denoted as das2.3, mark as such
				lSrv = [s.strip() for s in sServer.split('|')]
				if len(lSrv) > 1:
					sSrvType = lSrv[0] 
					sServer = lSrv[1]
				else:
					sSrvType = "das2.2"
					sServer = lSrv[0]
	
	fIn.close()
	sRelPath = sFileName.replace(sPrefix, '').replace('.dsdf','')
	lOut.append( (sRelPath, sDescription, sServer, sSrvType) )
		
	return True

def _sortNoDesc(tListItem):
	return tListItem[0]

##############################################################################

def _addEntries(sScriptUrl, lOut, lIgnore, dCat, fLog):
	"""This algorithm depends on directories sorted before files!
	Works because das2server.util.misc.symWalk ALWAYS calls directory 
	callback first"""
	
	# Print the initial list
	#for i in range(len(lOut)):
	#	fLog.write(">>initial>>%s,%s,%s,%s"%tuple(lOut[i]))
	#fLog.write("----")

	# Prune 1: Rm all sources that are not from a das2.3 server
	i = 0;
	while i < len(lOut):
		if lIgnore[i] or lOut[i][0].endswith('/'):  # A Dir, prune later
			i += 1
			continue

		if lOut[i][2] == None or lOut[i][2].startswith(sScriptUrl):
			i += 1  # source is one of mine, keep it 
		else:
			if lOut[i][3] == "das2.3":
				i += 1  # Some other das2.3 server, keep it
			else: 
				lTmp = lOut.pop(i)  # Some das2.2 source, drop it

	# Print the trimmed list:
	#for i in range(len(lOut)):
	#	fLog.write(">>trim srcs>>%s,%s,%s,%s"%tuple(lOut[i]))
	#fLog.write("----")			
		
	# Prune 2: Rm all empty directories (ignore list now invalid)
	i = 0
	while i < len(lOut):
		if not lOut[i][0].endswith('/'):
			i += 1
			continue
		
		# Look down the list for a source that starts with this prefix
		# if don't find it, trim.
		j = i + 1
		bIgnore = True
		while (j < len(lOut)) and (lOut[j][0].startswith(lOut[i][0])):
			if lOut[j][0][-1] != '/':
				bIgnore = False
				break
			j += 1
		
		if bIgnore:  lOut.pop(i)
		else:        i += 1

	# Print the trimmed list:
	#for i in range(len(lOut)):
	#	fLog.write(">>trim dirs>>%s,%s,%s,%s"%tuple(lOut[i]))
	#fLog.write("----")

	# Now run down the remaning items making full catalogs and stub sources
	for i in range(len(lOut)):
		
		if lOut[i][0].endswith('/'):  # add catalog

			dParent = dCat
			lSplit = lOut[i][0].split('/')[:-1] # Ignore empty last item
			for key in lSplit[:-1]: # Ignore my name
				dParent = dParent['catalog'][key.lower()]

			sName = lSplit[-1]
			sId = sName.lower()
			dParent['catalog'][sId] = {
				'type':'Catalog',
				'version':'0.5',
				'name':sName,
				'title':lOut[i][1],
				'catalog':{}
			}
		else:                         # add source
			dParent = dCat
			lSplit = lOut[i][0].split('/')
			for key in lSplit[:-1]: # ignore my name
				dParent = dParent['catalog'][key.lower()]

			sName = lSplit[-1]
			sId = sName.lower()

			if lOut[i][2] == None:
				sUrl = "%s/source/%s/api.json"%(sScriptUrl,lOut[i][0].lower())
			else:
				sUrl = "%s/source/%s/api.json"%(lOut[i][2],lOut[i][0].lower())

			dParent['catalog'][sId] = {
				'type':'HttpStreamSrc',
				'version':'0.6',
				'name':sName,
				'title':lOut[i][1],
				'urls':[sUrl]
			}
			

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.handlers.intro.py for a decription of this function
	interface
	"""
	
	if 'DSDF_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	# _dirOut and _fileOut append a list of tuples to lOut
	
	lOut = [] 
	tData = ("%s/"%dConf['DSDF_ROOT'], lOut, fLog)
	
	sPath = os.getenv("PATH_INFO")  
	
	U.webio.pout("Status: 200 OK\r\n")
	U.webio.pout('Access-Control-Allow-Origin: *\r\n')
	U.webio.pout('Access-Control-Allow-Methods: GET\r\n')
	U.webio.pout('Access-Control-Allow-Headers: Content-Type\r\n')	
	
	# Walk the tree, following symlinks
	U.misc.symWalk(fLog, dConf['DSDF_ROOT'], _fileOut, _dirOut, tData)
	
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
   # (no path) - old das2.1 list
	# /sources.csv - New das2.3 list
	# /sources.json - New das2.3 catalog
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
					if lOut[i][3] == "das2.3":
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
