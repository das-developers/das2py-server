"""Capabilities handler for Helophysics API subsystem"""

import sys
import codecs
import json
import os.path

from os.path import join as pjoin

from . import error

##############################################################################
def pout(sOut):
	if sys.version_info[0] < 3:
		sys.stdout.write(sOut)
		sys.stdout.write('\r\n')
	else:
		sys.stdout.buffer.write(sOut)
		sys.stdout.buffer.write(b'\r\n')


def _keyVal(sLine, sCmt):
	"""Returns the pair (key, value) for any line that has the form
	a = b C some comment.
	
	here C is any character from the string sCmt
	
	If the line dose not contain a keyword and a value, (None, None) 
	is returned.
	"""
	
	for c in sCmt:
		i = sLine.find(c)
		if i != -1:
			sLine = sLine[:i]
			break
	
	i = sLine.find(u'=')
	if i != sLine.find('='):
		raise ValueError("Dude, unicode is wierd")
		
	if (i == -1) or (i == 0) or (i == (len(sLine) - 1)):
		return (None, None)
	
	return (sLine[:i].strip(), (sLine[i+1:]).strip("' \n"))
	

g_lTrue =  ['1', u'1', 'true',  u'true',  'yes', u'yes']
g_lFalse = ['0', u'0', 'false', u'false', 'no',  u'no' ]

##############################################################################
def _dirOut(sDirName, tData):
	"""Open the DSDF for a directory  If the _dirinfo_dsdf has the 
	keyword hapi and the value evaluates to false, don't parse the 
	tree."""
	
	sPrefix = tData[0]
	lOut = tData[1]
	fLog = tData[2]
	
	sDirInfo = pjoin(sDirName, '_dirinfo_.dsdf')
	if not os.path.isfile(sDirInfo):
		return (True, sDirName)
	
	try:
		fIn = codecs.open(sDirInfo, 'rb', encoding='utf-8')
		for sLine in fIn:
			sLine = sLine.strip()

			(sKey, sVal) = _keyVal(sLine, ';#')
			if sKey == None:
				continue
			
			if sKey.lower() == u'hapi' and (sVal.lower() in g_lFalse):
				fLog.write("    Directory tree at %s is not HAPI, skipping\n"%sDirName)
				sDirName = None
				break

	except (IOError, ValueError) as e:
		fLog.write("%s"%str(e))
		sDirName = None
			
	return (True, sDirName)
	
##############################################################################
def _fileOut(sFileName, tData):
	
	sPrefix = tData[0]
	lOut = tData[1]
	fLog = tData[2]
	sScript = tData[3]
	
	if not sFileName.lower().endswith('.dsdf'):
		return True
	
	if sFileName.lower().endswith('_dirinfo_.dsdf'):
		return True
		
	sDescription = None
	try:
		fIn = codecs.open(sFileName, 'rb', encoding='utf-8')
	except IOError:
		return True
		
	bEnable = False
	bValidRange = False
	bIntervalRdr = False
	dSubSource = {}
	for sLine in fIn:
		sLine = sLine.strip()
		(sKey, sVal) = _keyVal(sLine, ';#')
		#fLog.write("%s:  %s = %s"%(sFileName, sKey, sVal))
		if sKey == None:
			continue
		sKey = sKey.lower()
		
		if sKey == u'description':
			sDescription = sVal.strip(u"\"' \r\n\t")
			continue
				
		#Now for the removals.				
		if sKey == u'rename':
			fIn.close()
			return True
		
		# TODO: Change once it is possible to set Qstream to hapi converters
		#       in the config file
		if sKey == u'qstream' and (sVal.lower() in ('1','true','yes')):
			fIn.close()
			return True 
		
		# Ignore stuff ment for other servers.  There are no re-directs in hapi
		if (sKey == u'server') and (sScript != None):
			if sVal != sScript:
				fIn.close()
				return True
				
		if sKey == u'hapi':
			if sVal.lower() not in g_lTrue:
				fIn.close()
				return True
			else:
				bEnable = True
			
		if sKey == 'requiresinterval' and (sVal.lower() in g_lTrue):
			# Maybe keep these if there is a sub-source, ugh this is a pain
			# why do we keep trying to kick a round peg into a square hole...
			bIntervalRdr = True
			
		# HAPI data requires a valid range tag
		if sKey == 'validrange':
			bValidRange = True
			
		# Like many simplistic transports, HAPI expects data cubes.  This reader
		# may be capable of outputting multiple data cubes.  Indicate these
		# as an appended item in the ID
		if sKey.startswith(u'subsource'):
			#fLog.write("    Found subSource for %s\n"%sFileName)
			l = sKey.split('_')
			if len(l) != 2:
				continue
			try:
				idx = int(l[1], 10)
			except:
				continue
			
			dSubSource[idx] = sVal
	
	fIn.close()
	
	if not bEnable:
		return True	
	
	if bValidRange:
		sRelPath = sFileName.replace(sPrefix, '').replace('.dsdf','')
		
		# Check for auto splits of this datasource
		if len(dSubSource) > 0:
			for sKey in dSubSource:
				l = [s.strip("' \t") for s in dSubSource[sKey].split('|') ]
				sSplitPath = "%s,%s"%(sRelPath, l[0].strip())
				sDesc = sDescription
				if len(l) > 1:
					sDesc = l[1].strip()
					
				if bIntervalRdr:
					fLog.write("Attempting to handle listing for interval reader %s\n"%sFileName)
					# Now we get to artificially constrain the ephemeris reader.
					# Yay.  I need to get a local artist to make a Das dragon
					# breaking the HAPI chains.  Title it "Unchain your server..."
					if len(l) > 2:
						try:
							fRes = float(l[2])
							lOut.append( (sSplitPath, sDesc) )
						except ValueError:
							pass
				else:
					lOut.append( (sSplitPath, sDesc) )
		
		else:
			lOut.append( (sRelPath, sDescription) )
		
	return True
	
##############################################################################
def _sortNoDesc(tListItem):
	return tListItem[0]	
	
##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	fLog.write("\nDas 2.2 HAPI Catalog handler\n")
	

	pout(b'Access-Control-Allow-Origin: *')
	pout(b'Access-Control-Allow-Methods: GET')
	pout(b'Access-Control-Allow-Headers: Content-Type')
	pout(b'Content-Type: application/json; charset=utf-8')
	
	if 'DATASRC_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DATASRC_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	if not error.paramCheck(fLog, 'catalog', [], form):
		return 18
			
	pout(b'Status: 200 OK\r\n')
	
	sScript = U.webio.getScriptUrl()

	
	# _dirOut and _fileOut append a list of tuples to lOut
	
	lOut = []
	if U.misc.isTrue('IGNORE_REDIRECT', dConf):
		sCkServer = None
	else:
		sCkServer = sScript
	
	tData = ("%s/"%dConf['DATASRC_ROOT'], lOut, fLog, sCkServer )
	
	# Walk the tree, following symlinks
	U.misc.symWalk(fLog, dConf['DATASRC_ROOT'], _fileOut, _dirOut, tData)
	
	lOut.sort(key=_sortNoDesc)
	
		
	lCat = []
	#fLog.write('Found %d usable DSDFs'%len(lOut))
	
	for i in range(0, len(lOut)):
		dItem = {'id':lOut[i][0]}
		
		# Could have added a url here to help them out, but they chose to ignore
		# age old web patterns, just like das2 did.  Why are they repeating our 
		# mistakes?
		#dItem['x_url'] = "%s/hapi/info?id=%s"%(sScript, dItem['id'])
		
		if lOut[i][1] != None:
			dItem['title'] = lOut[i][1]
				
		lCat.append(dItem)
	
	
	dOut = {
		"HAPI":"1.1", 
		"status":{"code":1200, 
		"message":"OK; Some data sources omitted due to protocol limitiations"},
		"catalog":lCat
	}
	
	sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
	pout(sOut.encode('utf8'))
	
	return 0
