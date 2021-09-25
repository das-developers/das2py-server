"""Grab bag of utilities for the Das2.2 server"""

import os
from . import webio

##############################################################################
def normalizeOpts(sParams):
	"""This is to support caching.

	Take an arbitrary parameter string and normalize it.  Here's the rules:

	 1. an empty string becomes the string '_noparam'

	 2. arguments that simply space separated items are sorted alphabetically
	    and groups of spaces are replaced by _

	 3. '-' characters are transformed to '_'

	 4. -r thing and --big-option=thing needs more work...  Should keep these
	    together
	"""

	if sParams == None or len(sParams) == 0:
		return "_noparam"

	lWords = [ s.replace('-','_') for s in sParams.split()]
	lWords.sort()
	sNorm = '_'.join(lWords)

	return sNorm


##############################################################################
def checkParams(fLog, form):
	"""Check the parameter values for obvious shell injection stuff such as
	pipes, redirects, ../ directories, etc"""

	for sKey in form.keys():
		sValue = form.getfirst(sKey, '')	
		for sTest in [';', '|','../','..\\', ':\\', '>', '&', '$']:
			if sValue.find(sTest) != -1:
				webio.queryError(fLog,
					"Illegal character(s) in the value for query parmeter: %s"%sKey
				)
				return False

		return True


##############################################################################
class recursionError(Exception):
	"""Little exception class to denote reaching a recursion limit, didn't
	see one built into the standard library"""

	def __init__(self, nMax, sMsg=None):
		self.sMsg = sMsg
		self.nMax = nMax

	def __str__(self):
		if self.sMsg == None:
			return "Maximum recursion depth %s exceeded"%self.nMax
		else:
			return "%s Maximum recursion depth %s exceeded"%(self.sMsg, self.nMax)


############################################################################
def symWalk(fLog, sRoot, fileCallBack = None, dirCallBack = None, tData = None, 
            nMaxDepth=20, _n=0):
	"""Walk a directory tree, following symlinks.  

	WARNING: Other code depends on the callback order (dirs then files)
	         so DON'T CHANGE IT!

	For each file encountered call the fileCallback which looks like:
	
	   bContinue fileCallback(sAbsPathToFile, userData)
		
	For each directory encountered 1st call the dir callback which looks like
	
	   (bContinue, sNewDirPath) dirCallBack(sAbsPathToDir, userData)
		
	And then walk into the directory.  If either call back returns False for
	bContinue, walking is halted.  The dir callback *must* return the current
	abs name of the directory for which it was called.  Because it is okay
	of the dir callback to change the directory name, or to delete it altogether.
	
	If the dir is deleted by the dir callback then "" should be returned for
	sNewDirName.
	
	nMaxDepth defaults to 20 and is the maximum recursion limit for decending
	a directory tree.  If the directory tree is deeper than nMaxDepth then
	a util.recursionError will be thrown.
	
	Returns:  True if walking was not halted, False if a halt was sent by
	one of the callback functions.
	"""
	
	_sRoot = sRoot
	if nMaxDepth < 1:
		raise ValueError("In find, nMaxDepth must be at least 1")
	
	nCurDepth = _n + 1
	if nCurDepth > nMaxDepth:
		raise recursionError("In symWalk:", nMaxDepth)
	
	try:
		lItems = os.listdir(_sRoot)
	except OSError as e:
		sErr = u"WARNING:  Couldn't list directory '%s'"%_sRoot
		fLog.write(sErr.encode('utf-8'))
		return True
		
	lItems.sort()
	
	for sItem in os.listdir(_sRoot):
		sPath = os.path.join(_sRoot, sItem)
		
		if os.path.isfile(sPath) and fileCallBack != None:
			if not fileCallBack(sPath, tData):
				return False
		
		elif os.path.isdir(sPath):
			
			if dirCallBack != None:
				(bContinue, sPath) = dirCallBack(sPath, tData)
				if not bContinue:
					return False
					
				if sPath == "" or sPath == None:
					continue
			
			if not symWalk(fLog, sPath, fileCallBack, dirCallBack, tData, 
			               nMaxDepth, nCurDepth):
				return False
			
	return True
	
##############################################################################
def parseKeyVal(fIn, cCmt='#'):
	"""Pass an open file handle in, get a dictionary out.
	Use codecs.open to read unicode files, and end a unicode string for the
	comment character.
	
	Use the simple file() constructor to read ascii files.
	
	Throws ValueError with a line number if there is a syntax problem in
	the file.
	"""
	
	# custom config reader, can improve with a lib later if someone wants to
	dConf = {}
	nLine = 0
	for sLine in fIn:
		nLine += 1
		iComment = sLine.find(cCmt)
		if iComment > -1:
			sLine = sLine[:iComment]
	
		sLine = sLine.strip()
		if len(sLine) == 0:
			continue
		
		iEquals = sLine.find('=')
		if iEquals < 1 or iEquals > len(sLine) - 2:
			fIn.close()
			raise ValueError(u"Error in %s line %d"%(fIn.name, nLine))
		
		sKey = sLine[:iEquals].strip()
		sVal = sLine[iEquals + 1:].strip(' \t\v\r\n\'"')
		dConf[sKey] = sVal
	
	return dConf

##############################################################################
g_lTrue = ['1',u'1','true',u'true']

def isTrue(sVal, dDict=None):
	"""Find out if an entry in a dsdf dictionary has the value 'true',
	Missing entries are automatically assigned the value 'false'
	"""
	
	if dDict != None:
		if sVal not in dDict:
			return False
		else:
			return dDict[sVal].lower() in g_lTrue
	else:
		return sVal.lower() in g_lTrue
		
	
############################################################################
def envPathMunge(sEnvVar, sAdd, sAddSep=':'):

	if sAdd == None or len(sAdd.strip()) == 0:
		return
	
	lAdd = sAdd.split(sAddSep)
	
	if sEnvVar in os.environ:
		lPath = os.environ[sEnvVar].split(os.pathsep)
	
		for i in range(len(lAdd)-1, -1, -1):
			sAdd = lAdd[i]
			if sAdd not in lPath:
				lPath.insert(0, sAdd)
	else:
		lPath = lAdd
		
	os.environ[sEnvVar] = os.pathsep.join(lPath)	






























