"""Default handler for 2.3 style catalog level lists"""

import sys
import codecs
import os
import json

from os.path import join as pjoin

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

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
	lOut.append( (sDataSrcDir, sDescription, None)  )
		
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
	
	fIn.close()
	sRelPath = sFileName.replace(sPrefix, '').replace('.dsdf','')
	lOut.append( (sRelPath, sDescription, sServer) )
		
	return True

def _sortNoDesc(tListItem):
	return tListItem[0]

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface
	"""
	pout = sys.stdout.write
	
	if 'DSDF_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	# _dirOut and _fileOut append a list of tuples to lOut
	
	lOut = [] 
	tData = ("%s/"%dConf['DSDF_ROOT'], lOut, fLog)
	
	sPath = os.getenv("PATH_INFO")  # Knock off leading '/source'
	if sPath != None:
		bJsonOut = sPath.lower().endswith(".json")
	else:
		bJsonOut = False
	
	pout("Status: 200 OK\r\n")
	pout("Content-Type: text/plain; charset=utf-8\r\n\r\n")
	
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
	
	for i in range(0, len(lOut)):
		if not lIgnore[i]:
			if lOut[i][1] != None:
				s = u"%s|%s\r\n"%(lOut[i][0], lOut[i][1])
			else:
				s = u"%s\r\n"%lOut[i][0]
						
			pout(s.encode("utf8"))
	
	return 0
