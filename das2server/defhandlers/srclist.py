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
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface
	"""
	
	if 'DSDF_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	# _dirOut and _fileOut append a list of tuples to lOut
	
	lOut = [] 
	tData = ("%s/"%dConf['DSDF_ROOT'], lOut, fLog)
	
	sPath = os.getenv("PATH_INFO")  # Knock off leading '/source'
	
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
	
	# Output one of three versions:
   # (no path) - old das2.1 list
	# /sources.csv - New das2.3 list
	# /sources.json - New das2.3 catalog
	if sPath == "/sources.csv":
		sScriptURL = U.webio.getScriptUrl()
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
				
				if lOut[i][2] == None:
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
		U.webio.pout('Content-Disposition: attachment; filename="sources.json"\r\n\r\n')

		U.webio.pout('{"TODO":"soon"}')

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
