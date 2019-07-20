"""Default handler for sending data source information as JSON description"""

import StringIO
import sys
import os
import json
import urllib

# Module moved in python3
try:
	from urllib import quote_plus
except ImportError:
	from urllib.parse import quote_plus


##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

##############################################################################
def _dsdfJson(dsdf):
	"""Write a dictionary"""
	
	# Actually let's put some thought into this.  The following transformations 
	# should be done:
	#
	# exampleRange_XX, exampleInterval_XX, exampleParams_XX
	# will be converted to:
	#
	#  examples : {
	#    "01":{"range":"A to B UNITS", "interval":A, "params":"PARAMS"}
	#    "02":{"range":"A to B UNITS", "interval":A, "params":"PARAMS"}
	#  }
	#
	#    cacheLevel_00 = resolution | block  [ | params]
	#
	#  becomes
	#
	#  cache : {
	#    "01":{'resolution':res, 'block':BLOCK, 'params':PARAMS}
	#  }
	#
	# And param_01 etc becomes  get's parsed if possible
	
	dOut = {"MIME":"application/octet-stream"}
	
	lIgnore = [u'reader', u'reducer', u'compressor', u'readAccess', 
	           u'groupAccess', u'subSource', u'coverageReducer', 
	           u'cacheReader', u'hapi']
				  
	# Some upfront conversions
	if dsdf.isTrue("das2Stream"):
		dOut["MIME"] = "application/vnd.das2.das2stream"
		lIgnore.append(u'das2Stream')
	elif dsdf.isTrue("qstream"):
		dOut["MIME"] = "application/vnd.das2.qstream"
		lIgnore.append(u'qstream')

	
	for uKey in dsdf.keys():
	
		if uKey in lIgnore:
			continue
		
		if uKey.find('(') != -1:
			continue
		
		
		# Break off the value using pipe characters if present
		uVal = dsdf[uKey]
		lVal = [s.strip() for s in dsdf[uKey].split('|')]

		# Break off the counter if present
		uCount = None
		iLoc = uKey.find(u'_')
		if iLoc != -1:
			uCount = uKey[iLoc+1:]
			uKey = uKey[:iLoc]
			
			# The sub-key may be in the ignore list
			if uKey in lIgnore:
				continue
		
		# Special handling for cache level
		if uKey == u"cacheLevel":
			if not uCount:
				continue
			
			if len(lVal) < 2:
				continue
			
			if 'cache' not in dOut:
				dOut['cache'] = {}
			if uCount not in dOut['cache']:
				dOut['cache'][uCount] = {}
			
			dOut['cache'][uCount] = {'id':uCount, 'resolution':lVal[0], 
			                         'blockMethod':lVal[1]}
			if len(lVal) > 2:
				dOut['cache'][uCount]['extraParams'] = lVal[2]
			
		# Special handling for example
		elif uKey.startswith(u'example'):
			if not uCount:
				uCount = "00"
			if "examples" not in dOut:
				dOut['examples'] = {}
			if uCount not in dOut['examples']:
				dOut['examples'][uCount] = {}
			uTmp = uKey[7:].lower()
			if uTmp == u'params':
				uTmp = u'extraParams'
			dOut['examples'][uCount][uTmp] = lVal[0]
			if len(lVal) > 1:
				dOut['examples'][uCount]['description'] = lVal[1]
		
		# Special handling for testRange:
		elif uKey.startswith(u'testRange'):
			if not uCount:
				uCount = "00"
			if "testRanges" not in dOut:
				dOut['testRanges'] = {}
			if uCount not in dOut['testRanges']:
				dOut['testRanges'][uCount] = {}	
			dOut['testRanges'][uCount]['range'] = lVal[0]
			if len(lVal) > 1:
				dOut['testRanges'][uCount]['description'] = lVal[1]
		
		# Special handling for param
		elif uKey == u'param':
			if u'extraParams' not in dOut:
				dOut[u'extraParams'] = {}
			dOut[u'extraParams'][uCount] = {'value':lVal[0]}
			if len(lVal) > 1:
				dOut[u'extraParams'][uCount]['description'] = lVal[1]			
		
		# Special handling for sciContact, techContact
		elif uKey.endswith(u'Contact'):
			if u'CONTACTS' not in dOut:
				dOut[u'CONTACTS'] = []
			
			# Split the output on , then extract anything in <> for the address
			lVal = [s.strip() for s in uVal.split(',')]
			
			for uContact in lVal:
				iTmp = uContact.find('<')
				uWho = uContact
				if iTmp != -1:
					uWho = uContact[:iTmp].strip()
					uEmail = uContact[iTmp + 1:-1].strip()
					if len(uEmail) < 1:
						uEmail = None
				
				if uKey == u'sciContact':
					uType = u'SCIENTIFIC'
				elif uKey == u'techContact':
					uType = u'TECHNICAL'
				else:
					uType = u'OTHER'	
					
				dContact = {'type':uType, 'who':uWho} 
				if uEmail:
					dContact['email'] = uEmail
				dOut[u'contacts'].append(dContact)
				
		# Special handling for item
		elif uKey == u'item':
			if u'items' not in dOut:
				dOut[u'items'] = {}
			if lVal[0] not in dOut[u'items']:
				dOut[u'items'][uCount] = {u'id':lVal[0]}
			
			if len(lVal) > 1:
				dOut[u'items'][uCount]['description'] = lVal[1]
				
		else:
			if uCount:
				if uKey not in dOut:
					dOut[uKey] = {}
				dOut[uKey][uCount] = uVal
			else:
				# direct substitutions:
				if uKey == u"info":
					uKey == u"summary"
				dOut[uKey] = uVal
	
	# Post processing, convert the examples and parmeters dictionaries to 
	# lists
	for sDict in ('examples','extraParams', 'items', 'cache', 'testRanges'):
		if sDict in dOut:
			lTmp = []
			if not isinstance(dOut[sDict], dict):
				continue
			for key in dOut[sDict]:
				lTmp.append(dOut[sDict][key])
			dOut[sDict] = lTmp
	
	return dOut

##############################################################################
def _exampleUrl(U, dConf, sScript, sDsdf, dOut, bPathForm):
	if u'examples' not in dOut:
		return None
	
	if not U.misc.isTrue('IGNORE_REDIRECT', dConf):
		if u'server' in dOut:
			sScript = dOut[u'server']
	
	dExample = dOut['examples'][0]
	
	if u'range' not in dExample:
		return NULL
	
	lTimes = [s.strip() for s in dExample['range'].split('to')]
	if len(lTimes) < 2:
		return None
		
	sExBeg = "time.min=%s"%lTimes[0]
	sExEnd = "time.max=%s"%lTimes[1]
	
	if u'extraParams' in dExample:
		sExParam = "&params=%s"% urllib.quote_plus( dExample['extraParams'])
	else:
		sExParam = ""
		
	if u'interval' in dExample:
		sExInter = "&interval=%s"%dExample['interval']
	else:
		sExInter = ""
	
	if not bPathForm:	
		sUrl = "%s?server=dataset&dataset=%s&%s&%s%s%s"%(
   	             sScript, sDsdf, sExBeg, sExEnd, sExInter, sExParam)
	else:
		sPath = os.getenv("PATH_INFO").replace('/source/','/data/')
		sPath = sPath.replace('.json','')
		sUrl = "%s%s?%s&%s%s%s"%(sScript, sPath, sExBeg, sExEnd, 
		                        sExInter, sExParam)
	
	return sUrl

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface
	"""
	bMkPathUrl = False
	sDsdf = form.getfirst('dataset', '')
	if sDsdf == '':
		sDsdf = os.getenv("PATH_INFO")  # Knock off leading '/source'
		if sDsdf.startswith('/source/'):
			sDsdf = sDsdf[len('/source/'):]
			bMkPathUrl = True
		sDsdf = sDsdf.replace(".json", '')
	
	fLog.write("\nDas 2.2 Info Handler")
	
	pout("Content-Type: application/json; charset=utf-8\r\n")
	
	if 'DSDF_ROOT' not in dConf:
		U.io.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
		
	dsdf = U.dsdf.Dsdf(sDsdf, dConf, form, fLog)
	
	dOut = _dsdfJson(dsdf)
	dOut['id'] = sDsdf
	
	sScript = U.io.getScriptUrl()
	sUrl = _exampleUrl(U, dConf, sScript, sDsdf, dOut, bMkPathUrl)
	if sUrl:
		dOut['example'] = sUrl
	
	sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
	sys.stdout.write(sOut.encode('utf-8'))
	return 0



