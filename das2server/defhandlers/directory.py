"""Default handler for 2.3 style catalog level lists"""

import sys
import codecs
import os
import json

from os.path import join as pjoin
from os.path import dirname as dname
from os.path import basename as bname

##############################################################################
# How URI's cascade
#
# Data catalog
#
#  1. If my _dirinfo_.dsdf has a uri = tag then this catalog has 
#     exactly that URI.
#
#  2. If not read up the stack until hitting a _dirinfo_.dsdf 
#     with a URI.  My uri is the relative path from the nearest
#     one set.
#
#  3. If no _dirinfo_.dsdf have a uri then my uri is the site
#     uri from the config file with my relative path appended.
#
#  4. If the site uri is missing, issue an error message and
#     quit.
def getDirUri(U, fLog, dConf, dDirInfo, sCatDir):
	if "uri" in dDirInfo:
		sUri = dDirInfo["uri"].strip("\"' /r/n")
		fLog.write("INFO: Using exlicit URI for directory %s, %s"%(sPath, sUri))
		return sUri
	
	sRelPath = None
	_sOrigCatDir = sCatDir
	while sCatDir != dConf['DSDF_ROOT']:
	
		# Go up one
		if sRelPath == None:
			sRelPath = bname(sCatDir)
		else:
			sRelPath = "%s/%s"%(bname(sCatDir), sRelPath)
		sCatDir = dname(sCatDir)

		sCatDsdf = pjoin(sCatDir, '_dirinfo_.dsdf')
		
		if os.path.isfile(sCatDsdf):
			fIn = open(sCatDsdf, "rb")
			dCatDsdf = U.dsdf.readDsdf(fIn, fLog)
			fIn.close()
			if "uri" in dCatDsdf:
				fLog.write("INFO:  Directory %s URI set relative to directory %s URI"%(
				           _sOrigCatDir, sCatDir))
				sUri = dDsdf["uri"].strip("\"' /r/n")
				return "%s/%s"%( sUri, sRelPath)
	
	# Still here huh, okay
	if "SITE_PATHURI" not in dConf:
		U.webio.serverError(fLog, 
			"No pathUri setting along the path of _dirinfo_.dsdf files leading "+\
		   "the path to file %s and fall back value SITE_PATHURI not set in %s"%(
							  pjoin(_sOrigCatDir, '_dirinfo_.dsdf'), dConf['__file__']))
		return None
	
	fLog.write("INFO:  Directory %s URI set relative to config file SITE_PATHURI: %s"%(
	           _sOrigCatDir, dConf['SITE_PATHURI']))

	return "%s/%s"%(dConf['SITE_PATHURI'], sRelPath)
	
##############################################################################
def getLocations(dDsdf):

	lKeys = dDsdf.keys()
	lKeys.sort()
	lLocs = []
	for sKey in lKeys:
		if sKey.startswith("location"):
			lLocs.append( dDirInfo[sKey].strip("\"' \t\r\n" ) )
	return lLocs

	
##############################################################################
def getCatBody(U, fLog, dConf, sParentUri, sParentUrl, sCatDir):

	lRawItems = os.listdir(sCatDir)
	
	dBody = {}
	
	for sItem in lRawItems:
	
		# I've already read my _dirinfo_.dsdf
		if sItem == '_dirinfo_.dsdf':
			continue
	
		sItemPath = pjoin(sCatDir, sItem)
		
		if os.path.isfile(sItemPath) and sItem.endswith(".dsdf"):
			sItem = sItem.replace('.dsdf','')
			
			fLog.write("INFO:  Reading dsdf %s"%sItemPath)
			
			# Getting Data source URI's
			#
			# 1. If the datasource or catalog has a uri = tag, then it has
			#    exactly that URI
			#
			# 2. If not then the datasource has it's relative path from
			#    this catalog's URI appended to the end.
			dItem = {'TYPE':'DasStreamSource'}
			fIn = open(sItemPath, 'rb')
			dDsdf = U.dsdf.readDsdf(fIn, fLog)
			fIn.close()
			
			if 'description' in dDsdf:
				dItem['TITLE'] = dDsdf['description'].strip("\"' \r\n")
			if 'pathUri' in dDsdf:
				dItem['PATH_URI'] = dDsdf['uri'].strip("\"' \r\n")
			else:
				dItem['PATH_URI'] = "%s/%s"%(sParentUri, sItem)
			
			# Data source descriptions are handled differently from
			# directory descriptions.  We know the datasource is here 
			# because there is a dsdf.  It's location parameters are for
			# the actual data read
			dItem['URL'] = [ "%s/%s.json"%(sParentUrl, sItem) ]
			
			dBody[sItem] = dItem
			
		elif os.path.isdir(sItemPath):
			sDsdfPath = pjoin(sItemPath, '_dirinfo_.dsdf')
			if not os.path.isfile(sDsdfPath):
				fLog.write("INFO: Skipping directory %s, _dirinfo_.dsdf missing"%sDsdfPath)
				continue
				
			# Hack to skip low-case directories that have any alphabetic
			# characters in them
			if "SKIP_LOWCASE" in dConf and dConf['SKIP_LOWCASE'] in ('1','yes','true'):
				if sItem.lower() == sItem:
					bHasAlpha = False
					for c in sItem:
						if c.isalpha():
							bHasAlpha = True
					if bHasAlpha:
						continue
				
				
			dItem = {'TYPE':'DasCatalog'}
			fIn = open(sDsdfPath, 'rb')
			dDsdf = U.dsdf.readDsdf(fIn, fLog)
			fIn.close()
			if 'description' in dDsdf:
				dItem['TITLE'] = dDsdf['description'].strip("\"' \r\n")
			if 'pathUri' in dDsdf:
				dItem['PATH_URI'] = dDsdf['uri'].strip("\"' \r\n")
			else:
				dItem['PATH_URI'] = "%s/%s"%(sParentUri, sItem)

			lLocs = getLocations(dDsdf)
			if len(lLocs) > 0:
				dItem['URL'] = lLocs
			else:
				dItem['URL'] = [ "%s/%s/index.json"%(sParentUrl, sItem) ]
				
			dBody[sItem] = dItem
		
		else:
			pass  # Just some random junk, move along
				
	return dBody


##############################################################################
def sendDict(fLog, dDict):	
	uCat = json.dumps(dDict, ensure_ascii=False, encoding='utf8', 
		               sort_keys=True, indent=3)
	
	sys.stdout.write("Status: 200 OK\r\n")
	sys.stdout.write("Content-Type: application/json; charset=utf-8\r\n\r\n")
	sys.stdout.write(uCat.encode('utf8'))
	

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
	
	sCatPath = os.getenv("PATH_INFO")  # Knock off leading '/source'
	
	if sCatPath.endswith("index.json"):  # knock off trailing index.json
		sCatPath = sCatPath.replace("index.json", "")
		
	if sCatPath.startswith('/source/'):
		sCatPath = sCatPath[len('/source/'):]
	
	if sCatPath.endswith('/'):
		sCatPath = sCatPath[:-1]
	
	sPath = pjoin(dConf['DSDF_ROOT'], sCatPath)
	
	sDirInfo = pjoin(sPath, '_dirinfo_.dsdf')
	if not os.path.isfile(sDirInfo):
		# _dirinfo_.dsdf files are now required
		U.webio.serverError(fLog, """Catalog directory file %s missing"""%sDirInfo)
		return 17
	fIn = open(sDirInfo, 'rb')
	dDirInfo = U.dsdf.readDsdf(fIn, fLog)
	fIn.close()

	sUri = getDirUri(U, fLog, dConf, dDirInfo, sPath)

	if sUri == None:
		return 17
	
	dCat = {"TYPE":"DasCatalog", "PATH_URI":sUri}
	
	if "description" in dDirInfo:
		dCat['TITLE'] = dDirInfo['description'].strip("\"' \t\r\n")
		
	# See if this is a remote catalog, if so just give the links and
	# move on.
	lLocs = getLocations(dDirInfo)

	if len(lLocs) > 0:
		dCat['locations'] = lLocs
		sendDict(fLog, dCat)
		return 0
	
	# We are not a remote catalog, find all sub items of this directory
	if len(sCatPath) > 0:
		sMyUrl = pjoin( U.webio.getScriptUrl(), "source", sCatPath)
	else:
		sMyUrl = pjoin( U.webio.getScriptUrl(), "source")
	dBody = getCatBody(U, fLog, dConf, sUri, sMyUrl, sPath)
	if dBody == None:
		return 17
	
	dCat['CATALOG'] = dBody
	sendDict(fLog, dCat)
	return 0
