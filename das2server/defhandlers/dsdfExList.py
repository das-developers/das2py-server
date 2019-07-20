"""Default handler for sending dsdfs with example times"""

import sys
import codecs
import os

from os.path import dirname as dname


##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

##############################################################################

g_sTestDir = os.sep + 'test' + os.sep

def _fileOutWithEx(sFile, tData):
	
	fLog = tData[0]
	sPrefix = tData[1]
	lOut = tData[2]
	
	sRelPath = None
	sDescription = None
	
	if not sFile.lower().endswith('.dsdf'):
		return True
	
	if sFile.lower().endswith('_dirinfo_.dsdf'):
		return True
	
	sDir = "%s/"%dname(sFile).replace(sPrefix, '')
			
	# Remove items that are in directories name test from the 
	# output
	if sDir.find(g_sTestDir) != -1:
		return True
	
	fIn = codecs.open(sFile, 'rb', encoding='utf-8')
	#fLog.write("INFO: Parsing %s"%sFile)
	for sLine in fIn:
		iComment = sLine.find(';')
		if iComment != -1:
			sLine = sLine[:iComment]
		
		if sLine.find('exampleRange') != -1:
			sRelPath = sFile.replace(sPrefix, '').replace('.dsdf','')
			
			if sDir != "/" and sDir not in lOut:
				lOut.append(sDir)
				
		if sLine.find('description') != -1:
			lLine = sLine.split('=')
			if len(lLine) > 1:
				sDescription = "".join(lLine[1:])
				sDescription = sDescription.strip("\"' \r\n\t")
				continue
				
		if sLine.find('rename') != -1:
			lLine = sLine.split('=')
			if len(lLine) > 1 and lLine[0].strip().lower() == 'rename':
				fIn.close()
				return True
			
	if sRelPath:
		if sDescription:
			lOut.append( u"%s|%s"%(sRelPath,sDescription ) )
		else:
			lOut.append( sRelPath )
			
	return True


##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface"""
	
	if 'DSDF_ROOT' not in dConf:
		U.io.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
		
	pout("Content-Type: text/plain; charset=utf-8\r\n")
	
	lOut = []
	tData = (fLog, "%s/"%dConf['DSDF_ROOT'], lOut)
	
	# Walk the tree, following symlinks
	U.misc.symWalk(fLog, dConf['DSDF_ROOT'], _fileOutWithEx, None, tData)
	
	lOut.sort()
	
	for sItem in lOut:
		pout(sItem.encode('utf-8'))
	
	return 0
