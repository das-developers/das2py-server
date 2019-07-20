"""Default handler for 2.3 style catalog level lists"""

import sys
import codecs
import os
import json

from os.path import join as pjoin

##############################################################################
def getCatalog(U, fLog, sInDir, sDirUrl, sDirUri):
	"""Loop through all the *.dsdf files on a server and make a flat 
	list.  Next, """
	
	if not os.path.isdir(sInDir):
		U.io.serverError(fLog, "Directory %s does not exist"%sInDir)
		return 17
	
	# Try to get a URI if I was not given one
	sDesc = None
	sDirInfo = pjoin(sInDir, "_dirinfo_.dsdf")
	if os.path.isfile(sDirInfo):
		try:
			fIn = open(sDirInfo, "rb")
			dDsdf = U.dsdf.readDsdf(fIn, fLog)
		except Error as e:
			U.io.serverError(fLog, str(e))
		
		if 'uri' in dDsdf:
			sDirUri = dDsdf['uri'].strip("\"' \r\n\t")
		if 'description' in dDsdf:
			sDesc = dDsdf['description'].strip("\"' \r\n\t")
		
		fIn.close()
		
	elif sDirUri is None:
		U.io.serverError(fLog, """Can not determine catalog URI's.
Please create file %s and include the 'uri' keyword."""%sDirInfo )
		return 17
	
	dSummary = {'type':'DasCatalog', 'version':'2.3'}

	if sDirUri[-1] != '/':
		sDirUri += sDirUri[:-1]
	
	i = sDirUri.rfind('/')
	if i < 0:
		U.io.serverError(fLog, "Bad catalog URI '%s', no slashes before the end"%sDirUri)
		return 17
		
	# My name
	sName = sDirUri[:i]
	dSummary['name'] = sName
	if sDesc:
		dSummary['desciption'] = sDesc
	
	lRawItems = os.listdir(sInDir)
	
	lBody = []
	
	# Put 
	
	for sItem in lRawItems:
		sItemPath = pjoin(sInDir, sItem)
		
		if sItem == '_dirinfo_.dsdf':
			continue
			
		elif os.path.isfile(sItemPath) and sItem.endswith(".dsdf"):
			sName = sItem.replace('.dsdf', '')
			sItemUri = "%s%s"%(sDirUri, sItem)  # May be overridden
			sItemUrl = "%s/%s.json"%(sDirUrl, sItem)
			
			dSubHdr = {'name':sName, 'type':'DasDataSource', 
			            'version':'2.3', 'uri': sItemUri }
			fIn = open(sItemPath, 'rb')
			dDsdf = U.dsdf.readDsdf(fIn, fLog)
			if 'description' in dDsdf:
				dSubHdr['description'] = dDsdf['description']
			
			# If this is on the current server the URL is easy, if it's a 
			# remote server we need to do one of two forms of the URL
			lUrl = ["%s/%s.json"%(sDirUrl, sItem)]
			
			lBody.append({ "summary":dSubHdr, "locations":lUrl})
			
		elif os.path.isdir(sItemPath):
			sItemUri = "%s%s"%(sDirUri, sItem)  # May be overridden
			sItemUrl = "%s%s/"%(sDirUrl, sItem)
			
			dSubCat = getCatalog(U, fLog, sItemPath, sItemUrl, sItemUri)
			if dSubCat:
				lBody.append(dSubCat)			
				
	dCat = {"summary":dSummary, "body":lBody}
	
	# Don't send out empty catalogs
	if len(lBody) > 0:
		return dCat
	else:
		return None
	

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface.
	
	This handler will recreate the entire catalog for a server, if it 
	doesn't exist.  Otherwise it will use the cached version (TODO)
	"""	
	if 'DSDF_ROOT' not in dConf:
		U.io.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	# _dirOut and _fileOut append a list of tuples to lOut
	
	lOut = []
	tData = ("%s/"%dConf['DSDF_ROOT'], lOut, fLog)
	
	sPath = os.getenv("PATH_INFO")  # Knock off leading '/source'
	if sPath != None:
		bJsonOut = sPath.lower().endswith(".json")
	else:
		bJsonOut = False	
	
	# For each das root, get a catalog
	lRoots = dConf['DSDF_ROOT'].split(";")
	dSiteCat = {}
	for sRoot in lRoots:
		pass
	
	dCatalog = getCatalog(U, fLog, dConf['DSDF_ROOT'], U.io.getScriptUrl(), None)
	if dCatalog != None:	
		uCat = json.dumps(dCatalog, ensure_ascii=False, encoding='utf8', 
		                  sort_keys=True, indent=3)
	else:
		uCat = json.dumps({}, ensure_ascii=False, sort_keys=True, indent=3)
	
	sys.stdout.write("Status: 200 OK\r\n")
	sys.stdout.write("Content-Type: application/json; charset=utf-8\r\n\r\n")
	sys.stdout.write(uCat.encode('utf8'))
		
	return 0
