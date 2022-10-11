""" dsdf compiler - Converts DSDF source description files into various useful 
things
"""

from os.path import dirname as dname
from os.path import basename as bname
from urllib.parse import quote_plus
from io import StringIO

from . import formats

g_tKeyConvention = formats.g_tKeyConvention

import das2

#########################################################################

g_d1s_mime = "application/octet-stream"
g_d2s_mime = "application/vnd.das2.das2stream"
g_d2x_mime = "application/vnd.das2.das2doc+xml" #; charset=utf-8 (*.d2x)
g_qs_mime  = "application/vnd.das2.qstream"

g_dStdKeys = {
	'das2':{
		"read.time.min":"start_time",
		"read.time.max":"stop_time",
		'read.time.intr':'interval',
		'bin.time.max':'resolution',
		'read.opts':'params'
	},
	'hapi':{
		'read.time.min':'time.min',
		'read.time.max':'time.max',
		'read.time.intr':None,
		'bin.time.max':None,
		'read.opts':'parameters'
	}
	# Add others here.  Note the das3 keys are just notional, they
	# can be changed as long as the public interface is changed to
	# match
}

def stdFormKeys(sConvention):
	"""Get the standard time parameter keys based on the call convention
	In das3 the key names are picked for coordinate names to help the
	developer keep different physical dimensions separate.

	Returns 
		(sTimeBegKey, sTimeEndKey, sTimeMaxBinSzKey, sIntervalKey, sOptKey)
	"""
	if sConvention in ("h-api","hapi"):
		return ('time.min', 'time.max', None, None, 'parameters')
	else:
		return ('start_time','end_time','resolution','interval','params')

##############################################################################

def _rawReadDsdf(fIn, fLog):
	"""Pass an open file handle in, get a dictionary out.
	Use codecs.open to read unicode files, and end a unicode string for the
	comment character.

	Throws ValueError with a line number if there is a syntax problem in
	the file.
	"""

	# custom config reader, can improve with a lib later if someone wants to
	lLines = fIn.readlines()
	#fLog.write("   TRACE: %s"%lLines)

	dDsdf = {}
	nLine = 0
	i = -1
	while i < len(lLines) - 1:
		i += 1

		#fLog.write("   TRACE: Reading line %d of %d"%(i+1, len(lLines)))
		sLine = lLines[i].strip()

		iComment = sLine.find(';')
		if iComment > -1:
			sLine = sLine[:iComment]

		if len(sLine) == 0:
			continue

		# Need to strip ' from the end of the current line before appending
		# and strip ' from the beginning of the next line before appending
		while sLine[-1] == '$':

			sLine = sLine[:-1].strip()

			if sLine[-1] == '+':
				sLine = sLine[:-1].strip()

			if sLine[-1] == "'":
				sLine = sLine[:-1]

			if i < (len(lLines) - 1):
				i += 1
				sNext = lLines[i].strip()
				if sNext[0] == "'":
					sNext = sNext[1:]

				sLine += sNext

		iEquals = sLine.find('=')
		if iEquals < 1 or iEquals > len(sLine) - 2:
			fIn.close()
			raise ValueError(u"Error in %s line %d"%(fIn.name, nLine))

		sKey = sLine[:iEquals].strip()
		sVal = sLine[iEquals + 1:].strip(' \t\v\r\n')
		if sVal[0] == "'":
			sVal = sVal[1:]
		if sVal[-1] == "'":
			sVal = sVal[:-1]

		
		# Make every value a dictionary
		sPriKey = sKey
		sSubKey = '00'
		
		n = sKey.find('_')
		if n != -1:
			sPriKey = sKey[:n]

			sSubKey = sKey[n+1:]

			if (not sSubKey.isdigit()) or (len(sSubKey) != 2):
				#Actual _ not list item separater, set the key
				# back the way it was
				sPriKey = sKey
			else:
				sSubKey = "%02d"% int(sKey[n+1:], 10)

		elif sKey[-2:].isdigit():  # Handle thing00 i.e. '_' is missing (questionable)
			sPriKey = sKey[:-2]
			sSubKey = sKey[-2:]
		
		if sPriKey not in dDsdf:
			dDsdf[sPriKey] = {}

		dDsdf[sPriKey][sSubKey] = sVal

	return dDsdf

# ########################################################################## #

def _loadDsdf(dConf, sName, sPath, fLog):
		"""Load a dsdf as a dictionary of dictionaries.  Every parameter becomes
		the key name for a dictionary of values.  Thus single values and
		lists take on the same form.

		dDsdf = {
			"reader":{"00": "/project/juno/etc/invoke.sh waves_survey_rdr"}
			"param" :{
				"00": "LFR_B | Low Frequency receiver, B channel",
				"01": "LFR_LO | Low frequency receiver E-lo channel"
			}

			... etc.
		}
		
		"""
		dDsdf = {}

		fLog.write("Reading: %s"%sPath)

		fIn = open(sPath, encoding='UTF-8')

		try:
			dDsdf = _rawReadDsdf(fIn, fLog)
		except ValueError as e:
			raise errors.ServerError(str(e))

		fIn.close()

		if len(dDsdf) == 0:
			raise errors.ServerError("Data source file is empty")

		dDsdf['__path__'] = sPath  # Save case-sensitive name and disk path
		dDsdf['__name__'] = bname(sName)

		# The case sensitive path portion that leads to this dsdf, without ".dsdf"
		dDsdf['__caseid__'] = sPath.replace(dConf['DATASRC_ROOT'],'')
		dDsdf['__caseid__'] = dDsdf['__caseid__'].rstrip('.dsdf')
		dDsdf['__caseid__'] = dDsdf['__caseid__'].strip('/')

		return dDsdf

##############################################################################
# These are used so much, just give it a variable

sV="value"
sT="title"

##############################################################################

def _atOrUnder(lTestPath, lTargPath):
	"""Does the front part of the lTestPath match the lTargPath"""

	# Test is too short to be at or under target
	if len(lTestPath) < len(lTargPath): return False

	for i in range(0, len(lTargPath)):
		if lTestPath[i] != lTargPath[i]:
			return False

	return True


def _leadsTo(lTestPath, lTargPath):
	"""Does the test path lead to the target path, any empty test path is
	assumed to lead to everything """

	# /a/b  (targ)

	# /     (test: true)
	# /a    (test: true)
	# /a/b  (test: false)

	if len(lTestPath) >= len(lTargPath): return False

	for i in range(0, len(lTestPath)):
		if lTestPath[i] != lTargPath[i]:
			return False

	return True

def _getDict(d, key):
	if key not in d: d[key] = {}
	return d[key]

def _getList(d, key):
	if key not in d: d[key] = []
	return d[key]
	
def _isTrue(d, key):
	if key not in d: return False
	if d[key].lower() in ('true','1','yes'):
		return True
	return False

def _isPropTrue(dProps, key):
	if key not in dProps: return False
	
	dSub = dProps[key]
	if '00' not in dSub: return False
	
	if dSub['00'].lower() in ('true','1','yes'):
		return True
	
	return False

def _dropKey(dDict, sKey):
	"""If the given dictionary has a top level key named 'internal', remove
	it and return the rest of the dictionary
	"""
	if sKey in dDict:
		dDict.pop(sKey)
	
	return dDict

def _confItem(dConf, sKey, sDefault):
	if (sKey in dConf) and (dConf[sKey] != None) and len(dConf[sKey]) > 0:
		return dConf[sKey]
	else:
		return sDefault

def _ageAuthNote(dProps):
	"""Returns a note indicating how old the data must be without requiring
	authentication.

	return (str) If an age note should be appended, None otherwise
	"""

	sRet = None

	if ('readAccess' not in dProps) or ('00' not in dProps['readAccess']):
		return sRet

	lMethods = [s.strip() for s in dProps['readAccess']['00'].split('|')]
	if len(lMethods) > 0:
		lMethOut = []
		for i in range(0, len(lMethods)):

			lMeth = [s.strip() for s in lMethods[i].split(':')]
			
			if len(lMeth) < 2:
				raise errors.ServerError("Syntax error in readAccess key value")

			sCheckType = lMeth[0].lower().strip()
				
			if sCheckType == 'age':
				sAge = lMeth[1].replace('y', ' years ').replace('m', ' months ')
				sAge = sAge.replace('d',' days ')
				
				sRet = "Request for data older than %s "%sAge +\
				       "will not prompt for authentication."
				break
				
	return sRet

##############################################################################
def _mergeContacts(dOut, dProps, fLog):
	"""Dsdfs list sci contacts using the following format:
	
	name <email>[ , NEXT_NAME, <NEXT_EMAIL> ] ...
	
	Reformat this into a list of  { 'name', 'EMAIL'} and add to 'SCI_CONTACT'
	"""
	
	lOut = _getList(dOut, 'contacts')

	if 'sciContact' in dProps:
	
		lContacts = [ s.strip() for s in dProps['sciContact']['00'].split(',') ]
	
		for sContact in lContacts:
			iTmp = sContact.find('<')
			sWho = sContact
			if iTmp != -1:
				sWho = sContact[:iTmp].strip()
				sEmail = sContact[iTmp + 1:-1].strip()
				if len(sEmail) < 1: sEmail = None
				dContact = {'type':'scientific', 'name':sWho, 'email':sEmail}
			else:
				dContact = {'type':'scientific', 'name':sWho}
			
			if dContact not in lOut: lOut.append( dContact )

	
	if 'techContact' in dProps:
	
		lContacts = [ s.strip() for s in dProps['techContact']['00'].split(',') ]
	
		for sContact in lContacts:
			iTmp = sContact.find('<')
			sWho = sContact
			if iTmp != -1:
				sWho = sContact[:iTmp].strip()
				sEmail = sContact[iTmp + 1:-1].strip()
				if len(sEmail) < 1: sEmail = None
				dContact = {'type':'technical', 'name':sWho, 'email':sEmail} 
			elif len(sWho) > 0:
				dContact = {'type':'technical', 'name':sWho} 
		
			if dContact not in lOut: lOut.append( dContact )

def _mergeProto(dOut, dConf, dProps, fLog):
	# Drop remote server information.  The catalog will take care of 
	# remote servers.  No need to encourage fixed URLs

	dProto = _getDict(dOut, 'protocol')
	dProto['method'] = 'GET'
	
	sServer = dConf['SERVER_URL']
	
	dProto['convention']	= 'HTTP/1.1'
	sBaseUrl = "%s/source/%s/data"%(sServer, dProps["__caseid__"].lower())

	dProto['baseUrls'] = [sBaseUrl]

	return sBaseUrl


def _mergeSrcCoordInfo(dOut, dProps, fLog):
	"""Add "coordinates" info to the output dictionary.
	"""
	dIface  = _getDict(dOut, 'interface')
	dCoords = _getDict(dIface, 'coords')
	
	# By default das2/2.2 servers only know that there is a time coordinate
	# so set that one up.  
	dTime = _getDict(dCoords, 'time')

	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = g_tKeyConvention
	
	if 'label' not in dTime: dTime['label']  = 'Time'

	# Use the lowest numbered example for the default range, interval
	dTime['minimum'] = {'label':'Minimum', sV:None}
	dTime['maximum'] = {'label':'Maximum', sV:None}
	
	dTime['units'] = {'value':'UTC'}
		
	if 'requiresInterval' in dProps:
		dTime['interval'] = {sV:None}
	else:
		dTime['resolution'] = {sV:None, "units":"s"}
	
	sNum = None
	if 'exampleRange' in dProps:
		lNums = list(dProps['exampleRange'].keys())
		lNums.sort()
		sNum = lNums[0]
	
		lTmp = [s.strip() for s in dProps['exampleRange'][sNum].split('|')]
		lTmp = [s.strip() for s in lTmp[0].split('to')]
		dTime['minimum'][sV] = lTmp[0]		
		if len(lTmp) > 1:
			dTime['maximum'][sV] = lTmp[1].replace('UTC','').strip()
	
	if 'exampleInterval' in dProps:
		lNums = list(dProps['exampleRange'].keys())
		if not sNum or (not (sNum in lNums)):
			lNums.sort()
			sNum = lNums[0]
		if 'interval' not in dTime:
			fLog.write("ERROR: Updating from %s\n"%dOut['path'])
			
		dTime['interval'][sV] = dProps['exampleInterval'][sNum]
	else:	
		# Default to 1/2000th of the range, here's where we need the
		# das2 module.
		if dTime['minimum'][sV] and dTime['maximum'][sV]:
			dtBeg = das2.DasTime(dTime['minimum'][sV])
			dtEnd = das2.DasTime(dTime['maximum'][sV])
			dTime['resolution'][sV] = (dtEnd - dtBeg) / 2000.0
				
	# Set up the alteration rules
	dTime['minimum']['set'] = {'param':sBegKey, 'required':True}
	dTime['maximum']['set'] = {'param':sEndKey, 'required':True}
	
	if 'validRange' in dProps:
		lTimeRng = [ s.strip() for s in dProps['validRange']['00'].split('to') ]
		if len(lTimeRng) > 1:
			dTime['validRange'] = lTimeRng
	
	if 'interval' in dTime:
		dTime['interval']['set'] = {'param':sIntKey, 'required':True}
	else:
		dTime['resolution']['set'] = {'param':sResKey, 'required':False}


	if 'coord' in dProps:
		for sNum in dProps['coord']:
			lItem = [s.strip() for s in dProps['coord'][sNum].split('|')]
			if lItem[0].lower() == 'time':
				if len(lItem) > 1:  dTime['title'] = lItem[1]
			else:
				dVar = _getDict(dCoords, lItem[0])
				dVar['label'] = lItem[0][0].upper() + lItem[0][1:]
				if len(lItem) > 1: dVar['title'] = lItem[1]
				if len(lItem) > 2: dVar['units'] = {'value':lItem[2]}
	

def _mergeSrcDataInfo(dOut, dProps, fLog):
	"""In general the das2 server has no understanding of output data 
	values.  This information can be given explicitly in a .json file
	or as a fallback, the .dsdf file can be scraped for hints.
	"""

	# Fallback to scraping the dsdf, if nothing here don't make an
	# empty section
	if ('item' not in dProps) and ('data' not in dProps): return
	
	# Make minimal entries for the data items
	dIface  = _getDict(dOut, 'interface')
	dData = _getDict(dIface, 'data')
	if 'item' in dProps:
		for sNum in dProps['item']:
			lItem = [s.strip() for s in dProps['item'][sNum].split('|')]
			
			dVar = _getDict(dData, lItem[0])
			dVar['label'] = lItem[0][0].upper() + lItem[0][1:]
			if len(lItem) > 1: dVar['title'] = lItem[1]
			if len(lItem) > 2: dVar['units'] = lItem[2]
		
	if 'data' in dProps:
		for sNum in dProps['data']:
			lItem = [s.strip() for s in dProps['data'][sNum].split('|')]
		
			dVar = _getDict(dData, lItem[0])
			dVar['label'] = lItem[0][0].upper() + lItem[0][1:]
			if len(lItem) > 1: dVar['title'] = lItem[1]
			if len(lItem) > 2: dVar['units'] = lItem[2]

def _mergeDas2Params(dOut, dProps, fLog):
	"""Merge in params.  This is a das 2.2 thing.  Any option that is needs
	to be handled by the reader and is not a time parameter is crammed into
	params, seriously overloading that one setting.  
	
	Arguments
	  dOut - A dictionary representing the entire JSON output document
	  dProps - The parsed DSDF properties as output by parseDas22SrcProps
	
	We'll classify this object as a string or a flag-set.  If the dsdf
	props provides keys that look like this:
	
	  param_00 = 'thing | description of thing'
	  param_01 = 'other | description of other'
	  ...
	  
	Then set this up as a flagset, otherwise use a generic string option.
	
	Though the final file will likely be hand edited make an Reader Options
	entry as a courtesy.
	"""

	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = g_tKeyConvention

	dProto = _getDict(dOut, 'protocol')
	dGet = dProto['httpParams']
	
	bAnyParams = False
	bFlagSet = False
	if 'param' in dProps:
		bAnyParams = True
		bFlagSet = True
		for sNum in dProps['param']:
			lParam = [s.strip() for s in dProps['param'][sNum].split('|') ]
			if len(lParam) != 2:
				bFlagSet = False
				break
	
	# Some readers have no options at all
	if not bAnyParams: return
	
	lNums = list(dProps['param'])
	lNums.sort()
	
	if bFlagSet:
		dFlags = {}
		dGet[sOptKey] = {
			'type':'FlagSet',
			'required':False,
			'title': 'Optional reader arguments',
			'flag_sep': ' ',
			'flags': dFlags
		}
		
		for sNum in lNums:
			lParam = [s.strip() for s in dProps['param'][sNum].split('|') ]
			sFlag = lParam[0].lower()
			if lParam[0].lower() == 'integer':
				dFlags[sFlag] = {'type':'integer', 'title':lParam[1] }
			elif lParam[0].lower() == 'real':
				dFlags[sFlag] = {'type':'real', 'title':lParam[1] }
			else:
				dFlags[sFlag] = {'value':lParam[0], 'title':lParam[1] }
	
	else:
		# For readers that don't have FLAGSET make a description that preserves
		# new lines
		lLines = [ dProps['param'][sNum] for sNum in lNums]

		dGet[sOptKey] = {
			'type':'string', 
			'required':False, 
			'title':'Optional reader arguments',
			'description' : '\n'.join(lLines), 		
			'name':'Reader Parameters'
		}
	
	
	dIface = _getDict(dOut, 'interface')
	dOpts = _getDict(dIface, 'options')
	
	# If the params element is handled as a string then just output a single
	# text option.
	
	if dGet[sOptKey]['type'] == 'string':
		dOpt = _getDict(dOpts, 'extra')
		dOpt['value'] = ''
		
		if 'exampleParams' in dProps:
			for sNum in lNums:
				if sNum in dProps['exampleParams']:
					dOpt['value'] = dProps['exampleParams'][sNum]
				break # Only take the first one since that's what's used for the
				      # example time.  We want the entire example to hang together
				
		dOpt['set'] = {'param':sOptKey}
		dOpt['name'] = 'Extra Reader Parameters'
		if 'description' in dGet[sOptKey]:
			dOpt['description'] = dGet[sOptKey]['description']
		
	# If it's a flag_set, output one option per flag.  Be on the lookout
	# for flags that have type 'integer' and 'real'  These should became
	# text options not booleans
	else:
		for sFlag in dFlags:
			dFlag = dFlags[sFlag]
			sOptName = sFlag.strip('-').strip().lower()
			dOpt = _getDict(dOpts, sOptName)
			dOpt['title'] = dFlag['title']
			
			if ('type' in dFlag) and (dFlag['type'] in ('real','integer')):
				dOpt['value'] = None
				dOpt['set'] = {'param':sOptKey, 'flag':sFlag}
						
			else:
				dOpt['type'] = 'boolean'
				dOpt['value'] = False
				dOpt['set'] = {'value':True, 'param':sOptKey, 'flag':sFlag}
				
	# If we want to do this as an enum this it would look like:
	#
	#    "units":{
	#    "value":"V/m",
	#    "set":{
	#    	"param":"read.options",
	#    	"map":[
	#    		{"value":"raw", "flag":"--units=DN"},
	#    		{"value":"V**2 m**-2 Hz**-1", "flag":"--units=SD"},
	#    		{"value":"W m**-2 Hz**-1", "flag":"--units=PF"}
	#    	]
	#    }	
						
	
def _mergeExamples(dOut, dProps, sBaseUrl, fLog):
	'''Merge in examples from the DSDF into the interface section.
	
	Note: This is a bit difficult as examples are specified from the point of
	view of the final user interface.  This is important because examples 
	shouldn't change depending on the underlying protocol.  In catalog terms
	this means examples can be defined at the source collection level.

	By skiping over the protocol level definition for examples, this function
	must by tightly coupled with decisions made in _mergeDas2Params.  For the
	
	"name":  (required)
	"title": (optional)
	"query":{
	   "coord.time.min":  (required)
	   "coord.time.max":  (required)
	   "coord.time.res":  (optional - set if reducable, or an interval)
	   "option.extra":    (optional - Set if extra parameters not parsable)
	   "option.[A, B, ]:  (optional - Set if extra parameters are flags)
	}
	
	Args:
		dOut - The output HttpStreamSrc object which must have it's
		   'interface' section already defined!
	'''

	if 'interface' not in dOut:
		raise ValueError('inteface section not defined, call _mergeDas2Params() first')
	
	# Match up the example range with example params and example interval
	# Stuff like this is annoying and why we should have moved to a
	# structured config file long ago
	lRange = []
	lParams = []
	lInterval = []
	
	if 'exampleRange' in dProps:
		lRange = list(dProps['exampleRange'].keys())
		lRange.sort()
		
	if 'exampleParams' in dProps:
		lParams = list(dProps['exampleParams'].keys())
		
	if 'exampleInterval' in dProps:
		lInterval = list(dProps['exampleInterval'].keys())
	
	if len(lRange) == 0: return   # No examples provided
	
	lExamples = []
	for sNum in lRange:
		bKeep = True
		dQuery = {}
		dExample = {"params":dQuery}
		dExample['label'] = "Example %s"%sNum
			
		lTmp = [s.strip() for s in dProps['exampleRange'][sNum].split('|')]
		if len(lTmp) > 1:
			dExample['label'] = lTmp[1]
			
		lTmp = [s.strip() for s in lTmp[0].split('to')]
		
		if len(lTmp) < 2: continue  # Invalid range string
			
		sBeg = lTmp[0]
		sEnd = lTmp[1].replace('UTC','').strip()
		dQuery["coord.time.max"] = sBeg
		dQuery["coord.time.min"] = sEnd
			
		# See if we need resolution or interval
		if sNum in lInterval:
			dQuery['coord.time.res'] = dProps['exampleInterval'][sNum]
		else:
			# Default to 1/2000th of the range, here's where we need the das2 module.
			dtBeg = das2.DasTime(sBeg)
			dtEnd = das2.DasTime(sEnd)
			dQuery["coord.time.res"] = (dtEnd - dtBeg) / 2000.0
		
		# By default flags are coverted to individual options by value.  This
		# means there is a translation from:
		#
		#  param_00 = "10khz | display data sampled at 25.2 ksps with a 10 kHz filter"
		#  param_01 = "1khz | display data sampled at 25.2 ksps with a 1 kHz filter" 
		#
		# To these interface values:
		# 
		#  read.opt.10kHz = true
		#  read.opt.1kHz = true
		#
		# And to these HTTP param flags:
		#
		#  ?read.opts=10kHz 1kHz&
		#
		# So if a given set of exampleParams exists, we have to determine which
		# UI options to set based on the example parameters.  The fall back is
		# Always the option.extra string value.
		
		if sNum in lParams:
			sOpts = dProps['exampleParams'][sNum]
			if ('option' not in dOut['interface']) or ('extra' in dOut['interface']['option']):
				# Assume no 'param_' items in the DSDF so all options must just
				# be crammed into a string.  Same thing is true if the interface
				# parser just gave up on made an 'extra' item.
				dQuery['option.extra'] = {'extra': sOpts}
			else:
				# Okay, param_00 and friends were defined, so set each one
				lFlags = sOpts.split()
				for sFlag in lFlags:
					dQuery['option.%s'%sFlag] = 'true'
				
		
		lQuery = [
			"%s=%s"%(sKey, quote_plus(str(dQuery[sKey])))
			for sKey in dQuery
		]

		#if sBaseUrl[-1] in ('?','&'): sSep = ""
		#elif '?' in sBaseUrl: sSep = '&'
		#else: sSep = '?'

		#dExample['url'] = "%s%s%s"%(sBaseUrl, sSep, '&'.join(lQuery))
		
		# TODO: Merge in examples from the DSDFs with hand entered ones
		lExamples.append( dExample )
		
	if len(lExamples) > 0:
		dProto = _getDict(dOut, 'interface')
		dProto['examples'] = lExamples

# ########################################################################## #

def _mergeFormat(dConf, dOut, dProps, fLog):

	# Different das3 servers can have different capabilities so we *really*
	# shouldn't make api.json files for others.  I have done so here, but
	# they aren't in the catalog at least and they are hidden from wget.
	
	# If this really is one of my data sources, add in the extra formatting
	# options provided by this server

	sMe = dConf['SERVER_URL']
	bIsMe = True

	if 'server' in dProps and '00' in dProps['server']:
		sSrv = dProps['server']['00']
		lSrv = [ s.strip() for s in sSrv.split('|')]
		if len(lSrv) > 1:
			sServer = lSrv[1].strip('/')
		else:
			sServer = lSrv[0].strip('/')

		bIsMe = (sServer == sMe)
		if sServer != sMe:
			dOut['interface']['formats'] = {}
	
	lRdrOut = ['das', '1.0', 'binary']  # The default
	if _isPropTrue(dProps, 'qstream'):
		lRdrOut = ['qstream', None, 'binary']

	elif _isPropTrue(dProps, 'das2Stream'):
		lRdrOut = ['das', '2.2', 'binary']
		
	elif _isPropTrue(dProps, 'das3Stream'):
		lRdrOut = ['das', '3.0', 'binary']

	# Add our supported output conversion interface controls and parameters
	dOut['interface']['formats'] = formats.getFormatSelection(dConf, lRdrOut)
	
	formats.addFormatHttpParams(dConf, dOut['protocol']['httpParams'], lRdrOut)


# ########################################################################## #

def makeGetSrc(fLog, dConf, sPath):
	"""Create an HttpStreamSrc object from a DSDF file and the given server
	configuration information.

	Output makes assumptions about the query parameter interface of the 
	server and format conversion capabilities.

	Args:
		dConf - The das2 server configuration dictionary
		sPath - The path to the DSDF file
		fLog - An object with a .write method
		sTarget - The information target, one of 'internal', 'exteral' or 
			'any'.  Mostly used to avoid loading suggested GUI info for 
			internal processing, or command handling for external clients.

	Throws:
		QueryError if dsdf doesn't exist
		RemoteServer if dsdf is for someone else
		ServerError if there is a syntax error or other misconfiguration
	"""

	sName = bname(sPath).replace(".dsdf","")
	dDsdf = _loadDsdf(dConf, sName, sPath, fLog)

	dOut = {}

	# The disk entries may have been hand edited.  Don't override the name and
	# description, go ahead and smash the type and path
	dOut['label'] = dDsdf['__name__']
	if 'description' in dDsdf: 
		dOut["title"] = dDsdf['description']['00']
	dOut['type'] = 'HttpStreamSrc'
	dOut['version'] = "0.7"

	# potentially override the base url and set the protocol convention
	sBaseUrl = _mergeProto(dOut, dConf, dDsdf, fLog)
	
	# make an ID for the datasource if requested
	#if sIdRoot:
	#	sSrvPath = '.'.join(dNode['_srvPath'])
	#	sUid = sIdRoot + sSrvPath.lower().replace(' ','_')
	#	if 'uris' in dNode:
	#		if sUid not in dNode['uris']:
	#			dNode['uris'].append(sUid)
	#	else:
	#		dNode['uris'] = [sUid]
	#if 'uris' in dNode:
	#	dOut['uris'] = dNode['uris']
		
	_mergeContacts(dOut, dDsdf, fLog)
	
	_mergeSrcCoordInfo(dOut, dDsdf, fLog)
	_mergeSrcDataInfo(dOut, dDsdf, fLog)
	
	# Set the authentication information
	dProto = dOut['protocol']	
	if 'securityRealm' in dDsdf:
		sAuthContact = None
		for dContact in dOut['contacts']:
			if dContact['type'] == 'scientific':
				sAuthContact = dContact['name']
				break

		dProto['authorization'] = {'required':True, 'contact':sAuthContact}
		dProto['authentications'] = [{
			'method':'HTTP/Basic','realm':dDsdf['securityRealm']['00']
		}]

		sAgeNote = _ageAuthNote(dDsdf)
		if sAgeNote:
			dProto['authorization']['description'] = sAgeNote
	else:
		dProto['authorization'] = {'required':False}
	
	dGet = {}
	dProto['httpParams'] = dGet
	
	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = g_tKeyConvention

	dGet[sBegKey] = {
		'required':True, 'type':'isotime',
		'label':'Min Time', 'title':'Minimum time value to stream',
	}
		
	dGet[sEndKey] = {
		'required':True, 'type':'isotime',
		'label':'Max Time', 'title':'Maximum Time Value to stream',
	}
	
	# See if requires interval is set, if not
	if _isPropTrue(dDsdf, 'requiresInterval'):
		dGet[sIntKey] = {
			'required':True, 'type':'real', 'units':'s',
			'label':'Interval', 
			'title':'Time interval between model calculations/interpolations',
			'description': 'This parameter is used with data generated from models '
			   'or table interpolations such as SPICE Ephemerides and '
				'magnetic field models',
		}

	else:
		dGet[sResKey] = {
			'required':False, 'type':'real', 'units':'s',
			'label':'Resolution', 
			'title':'The maximum time bin width for bin-reduced data in seconds',
			'description':'The server will return data at or better than the given '
            'x-axis resolution if possible.  Leave un-specified to get data '
			   'at intrinsic resolution without server side averages',
		}

	# Convert any read params to a read.options parameter
	_mergeDas2Params(dOut, dDsdf, fLog)
		
	# Provide examples for external interfaces
	_mergeExamples(dOut, dDsdf, sBaseUrl, fLog)
	_mergeFormat(dConf, dOut, dDsdf, fLog)

	return dOut

# ########################################################################## #

def _mergeWsProto(dOut, dConf, dProps, fLog):
	# Drop remote server information.  The catalog will take care of 
	# remote servers.  No need to encourage fixed URLs

	dProto = _getDict(dOut, 'protocol')
	
	sServer = dConf['SERVER_URL']
	
	dProto['subprotocols'] = ['forward-stream-v1.das2.org']
	sBaseUrl = "%s/%s/data"%(dConf['WEBSOCKET_URI'], dProps["__caseid__"].lower())

	dProto['baseUrls'] = [sBaseUrl]

	return sBaseUrl

# ########################################################################## #

def _mergeWsFormat(dConf, dOut, dProps, fLog):

	# Different das3 servers can have different capabilities so we *really*
	# shouldn't make api.json files for others.  I have done so here, but
	# they aren't in the catalog at least and they are hidden from wget.
	
	# If this really is one of my data sources, add in the extra formatting
	# options provided by this server

	sMe = dConf['SERVER_URL']
	bIsMe = True

	if 'server' in dProps and '00' in dProps['server']:
		sSrv = dProps['server']['00']
		lSrv = [ s.strip() for s in sSrv.split('|')]
		if len(lSrv) > 1:
			sServer = lSrv[1].strip('/')
		else:
			sServer = lSrv[0].strip('/')

		bIsMe = (sServer == sMe)
		if sServer != sMe:
			dOut['interface']['formats'] = {}
	
	lRdrOut = ['das', '1.0', 'binary']  # The default
	if _isPropTrue(dProps, 'qstream'):
		lRdrOut = ['qstream', None, 'binary']

	elif _isPropTrue(dProps, 'das2Stream'):
		lRdrOut = ['das', '2.2', 'binary']
		
	elif _isPropTrue(dProps, 'das3Stream'):
		lRdrOut = ['das', '3.0', 'binary']

	# Add our supported output conversion interface controls and parameters
	dOut['interface']['formats'] = formats.getFormatSelection(dConf, lRdrOut, True)
	
	formats.addFormatHttpParams(dConf, dOut['protocol']['httpParams'], lRdrOut, True)

# ########################################################################## #
def hasRtSupport(fLog, dConf, sPath):

	sName = bname(sPath).replace(".dsdf","")
	dProps = _loadDsdf(dConf, sName, sPath, fLog)

	return ('realTime' in dProps)

# ########################################################################## #
def makeSockSrc(fLog, dConf, sPath):
	"""Create an WebSockSrc object from a DSDF file and the given server
	configuration information.  

	Requires a DSDF with the setting:

	   realTime = 1  (or equivalent)

	The difference between the HTTP get interface an the websocket interface
	is that web-sockets exist to support real-time display.  Real time readers
	must be able to handle the new time range parameters:

	   start: "isotime" or "now"
	   stop:  "isotime" or "forever"

	if the reader does not support the meta-times above for its time range
	then it can't support a real-time query and thus 

	   realTime = 0 

	should be set, or not included at all.

	In addition, the a websocket server must be enabled.  To enable the
	websocket server set:

	   WEBSOCKET_URI

	in the corresponding das2server.conf.

	returns (dict): If the source has realTime = 1, None otherwise.
	"""

	sName = bname(sPath).replace(".dsdf","")
	dProps = _loadDsdf(dConf, sName, sPath, fLog)

	if ('realTime' not in dProps) or ('WEBSOCKET_URI' not in dConf):
		return None

	sName = bname(sPath).replace(".dsdf","")
	dDsdf = _loadDsdf(dConf, sName, sPath, fLog)

	dOut = {}

	# The disk entries may have been hand edited.  Don't override the name and
	# description, go ahead and smash the type and path
	dOut['label'] = dDsdf['__name__']
	if 'description' in dDsdf: 
		dOut["title"] = dDsdf['description']['00']
	dOut['type'] = 'WebSockSrc'
	dOut['version'] = "0.1"

	# potentially override the base url and set the protocol convention
	sBaseUrl = _mergeWsProto(dOut, dConf, dDsdf, fLog)
	
	# make an ID for the datasource if requested
	#if sIdRoot:
	#	sSrvPath = '.'.join(dNode['_srvPath'])
	#	sUid = sIdRoot + sSrvPath.lower().replace(' ','_')
	#	if 'uris' in dNode:
	#		if sUid not in dNode['uris']:
	#			dNode['uris'].append(sUid)
	#	else:
	#		dNode['uris'] = [sUid]
	#if 'uris' in dNode:
	#	dOut['uris'] = dNode['uris']
		
	_mergeContacts(dOut, dDsdf, fLog)
	
	_mergeSrcCoordInfo(dOut, dDsdf, fLog)
	_mergeSrcDataInfo(dOut, dDsdf, fLog)
	
	# Set the authentication information
	dProto = dOut['protocol']	
	if 'securityRealm' in dDsdf:
		sAuthContact = None
		for dContact in dOut['contacts']:
			if dContact['type'] == 'scientific':
				sAuthContact = dContact['name']
				break

		dProto['authorization'] = {'required':True, 'contact':sAuthContact}
		dProto['authentications'] = [{
			'method':'HTTP/Basic','realm':dDsdf['securityRealm']['00']
		}]
	else:
		dProto['authorization'] = {'required':False}
	
	dGet = {}
	dProto['httpParams'] = dGet
	
	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = g_tKeyConvention

	dGet[sBegKey] = {
		'required':True, 'type':'isotime',
		'label':'Min Time', 'title':'Minimum time value to stream',
	}
		
	dGet[sEndKey] = {
		'required':True, 'type':'isotime',
		'label':'Max Time', 'title':'Maximum Time Value to stream',
	}
	
	# See if requires interval is set, if not
	if _isPropTrue(dDsdf, 'requiresInterval'):
		dGet[sIntKey] = {
			'required':True, 'type':'real', 'units':'s',
			'label':'Interval', 
			'title':'Time interval between model calculations/interpolations',
			'description': 'This parameter is used with data generated from models '
			   'or table interpolations such as SPICE Ephemerides and '
				'magnetic field models',
		}

	else:
		dGet[sResKey] = {
			'required':False, 'type':'real', 'units':'s',
			'label':'Resolution', 
			'title':'The maximum time bin width for bin-reduced data in seconds',
			'description':'The server will return data at or better than the given '
            'x-axis resolution if possible.  Leave un-specified to get data '
			   'at intrinsic resolution without server side averages',
		}

	# Convert any read params to a read.options parameter
	_mergeDas2Params(dOut, dDsdf, fLog)
		
	# Provide examples for external interfaces
	_mergeExamples(dOut, dDsdf, sBaseUrl, fLog)
	_mergeWsFormat(dConf, dOut, dDsdf, fLog)

	return dOut

# ########################################################################## #

def makeInternal(fLog, dConf, sPath):
	"""Get all the items needed for the internal server interface that are
	not to be sent out to the clients.  This includes:

	commands
		.read      (from reader=, das2Stream=, qstream=)
		.date
		.bin       (from reducer=, das2Stream=, qstream=)
		.format

	authorization (from readAccess=)

	authentication (from securityRealm=)
	"""

	dOut = {}

	sName = bname(sPath).replace(".dsdf","")
	dProps = _loadDsdf(dConf, sName, sPath, fLog)
	
	# Save the mime-type for the command inputs and outputs
	dOutType = {'type':"das",'version':"1.1"}
	if _isPropTrue(dProps, 'qstream'):
		dOutType = {'type':"qstream"}
	elif _isPropTrue(dProps, 'das2Stream'):
		dOutType = {'type':'das','version':'2.2'}

	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = g_tKeyConvention

	# Put in translations for other systems by default
	dTr = _getDict(dOut, 'translate')
	for sSys in ('das2','hapi'):
		(sBegTr, sEndTr, sResTr, sIntTr, sOptTr) = stdFormKeys(sSys)
		dTr[sSys] = {
			sBegTr:sBegKey, sEndTr:sEndKey, sResTr:sResKey, sOptTr:sOptKey,
			'start':sBegKey, 'stop':sEndKey
		}

	dCmds = _getDict(dOut, 'commands')
	
	# By default, both das2 and das3 sources output the same thing
	# User can customize if desired downstream
	
	# Reader Section #################################
	lRead = _getList(dCmds, 'read')

	if 'reader' in dProps and '00' in dProps['reader']:
		sRdr = dProps['reader']['00']

		# Look for $(PARAMS) substitutions in the file to make a read.options
		# subsitution in the command line
		iBeg = sRdr.find('$(PARAMS')
		if iBeg != -1:
			iEnd = sRdr[iBeg:].find(')')
			if iEnd == -1:
				fLog.write("Invalid DSDF: %s"%dProps['__path__'])
				return
			else:
				iEnd += iBeg + 1
			
			sSub = sRdr[iBeg+2:iEnd-1]
			lSub = sSub.split(',')
			
			if len(lSub) > 1:
				sOptTplt = '#[%s # @ # %s]'%(sOptKey, lSub[1])
			else:
				sOptTplt3 = '#[%s # @ #]'%sOptKey

			sCmd = "%s%s%s"%(sRdr[:iBeg], sOptTplt, sRdr[iEnd+1:])
		else:
			sCmd = sRdr

		# Two variations, one for requires interval
		sInterval = ''
		if _isPropTrue(dProps, 'requiresInterval'):  # Ephemeris readers
			 sInternal = '#[%s] '%sIntKey
			
		if _isPropTrue(dProps, 'dropParams'):
			dReader = {'template':'%s %s#[%s] #[%s]'%(sCmd, sInterval, sBegKey, sEndKey)}
		else:
			dReader = {'template':
				'%s %s#[%s] #[%s] #[%s#@#]'%(sCmd, sInterval, sBegKey, sEndKey, sOptKey
			)}

		# A command order: 10, 20, 30, 40 etc
		# and a command parameter set: can be used to determine what to read
		# out of cache and what to re-generate.
		#
		# For example if we have commands: 
		#
		# 0  -> reader
		# 10 -> psd
		# 20 -> reducer
		# 30 -> format as CSV
		#
		# If a request comes in for a vo-table, and the cache runs up to processing
		# level 30, then we can run this:
		#
		#   read.cache | das2vo -> output
		#
		# Without invoking the whole chain.
		
		dReader['order'] = 0
		dReader['output'] = dOutType

		lRead.append(dReader)

	# Is reduction allowed? ####################################
	bReduce = True
	if ('reducer' in dProps) and '00' in dProps['reducer']:
		if dProps['reducer']['00'] in ('not_reducable','not_reducible'):
			bReduce = False

	if bReduce:
		sReducer = None
		# Specific reducer overrides any automatic decisions
		if ('reducer' in dProps) and '00' in dProps['reducer']:
			sReducer = dProps['reducer']['00']
		else:
			# Go by data type and config settings.  Assume the reducer
			# doesn't change the format
			if dOutType['type'] == 'das':
				if dOutType['version'] == '2':
					if 'D2S_REDUCER' in dConf:
						sReducer = dConf['D2S_REDUCER']

			elif dOutType['type'] == 'qstream':
				if 'QDS_REDUCER' in dConf:
					sReducer = dConf['QDS_REDUCER']

		if sReducer:
			lBin = _getList(dCmds, 'bin')
			lBin.append({
				'template':'%s #[%s]'%(sReducer, sResKey),
				'trigger':[{"key":sResKey,"value":0,"compare":"gt"}],
				'order': 20, 'input': dOutType, 'output': dOutType
			})
	
	# Cache Section #####################################
	if 'cacheLevel' in dProps:
		
		dCache = _getDict(dOut, 'cache')
		
		# The coordinate map for this cache is just the conventional items
		dCache['min_coord_params'] = [sBegKey],
		dCache['max_coord_params'] = [sEndKey],
		
		dSchemeToSize = {
			"yearly":"1 year", "monthly":"1 month", "daily":"1 day", 
			"hourly":"1 hour", "perminute":"1 minute", "persecond":"1 s"
		}

		dSets = _getDict(dCache, 'blockSets')
		for sLevel in dProps['cacheLevel']:
			l = [s.strip() for s in dProps['cacheLevel'][sLevel].split('|')]
			if len(l) < 2:
				fLog.write("ERROR: Misconfigured cache level in %s"%dProps['cacheLevel'][sLevel])
				continue
			sRes = l[0]
			
			if l[1] not in dSchemeToSize:
				fLog.write("ERROR: Misconfigured cache block size in %s"%l)
				continue
			sBlkSz = dSchemeToSize[l[1]]
			dBlk = {"block_size":[sBlkSz]}

			if sRes != 'intrinsic':
				dBlk['resolution'] = [sRes]
				dBlk['resolutionParams'] = [sResKey]
		
			if len(l) > 2: # Has read.options
				dBlk['fixed_params'] = {sOptKey:l[2]}
			
			try:
				n = int(sLevel, 10)
				sLevel = "%d"%n
			except:
				pass
			dSets[sLevel] = dBlk

	# Authorization
	if 'readAccess' in dProps and '00' in dProps['readAccess']:
		dAuth = _getDict(dOut, 'authorization')

		lMethods = [s.strip() for s in dProps['readAccess']['00'].split('|')]
		if len(lMethods) > 0:
			lMethOut = []
			lGroups = []
			lUsers = []
			for i in range(0, len(lMethods)):

				lMeth = [s.strip() for s in lMethods[i].split(':')]
				#fLog.write("DEBUG: auth methods %s"%lMeth)
				if len(lMeth) < 2:
					raise errors.ServerError(
						"Syntax error in readAccess key value"
					)

				sCheckType = lMeth[0].lower().strip()
				
				if sCheckType == 'age':
					dAuth['params'] = [{
						"key":sEndKey, "reference":"now", "delta":"-%s"%lMeth[1],
						"compare":"lt"
					}]
				elif sCheckType == 'group':
					lGroups.append(lMeth[1])
				elif sCheckType == 'user':
					lUsers.append(lMeth[1])

			if len(lGroups) > 0:
				dAuth['user_in_group'] = lGroups
			if len(lGroups) > 0:
				dAuth['user_is'] = lUsers

	# Authentication
	if 'securityRealm' in dProps and '00' in dProps['securityRealm']:
		dAuth = _getDict(dOut, 'authentication')
		dAuth['securityRealm'] = dProps['securityRealm']['00']

	# Formatting commands
	lRdrOut = ['das', '1.0', 'binary']  # The default
	if _isPropTrue(dProps, 'qstream'):
		lRdrOut = ['qstream', None, 'binary']

	elif _isPropTrue(dProps, 'das2Stream'):
		lRdrOut = ['das', '2.2', 'binary']
		
	elif _isPropTrue(dProps, 'das3Stream'):
		lRdrOut = ['das', '3.0', 'binary']

	# Add our supported output conversion interface controls and parameters
	dFmts = _getDict(dCmds, 'format')
	formats.addFormatCommands(dConf, dFmts, lRdrOut)

	return dOut

# ########################################################################### #
# Given a dsdf, make an old das2 interface file #

def makeD2t(fLog, dConf, sPath):

	sName = bname(sPath).replace(".dsdf","")
	dProps = _loadDsdf(dConf, sName, sPath, fLog)

	tDrop = (
		'reader', 'reducer', 'compressor', 'readAccess', 'groupAccess',
		'hapi', 'subSource', 'hapi', 'readerCmd', 'reducerCmd', 'exampleQuery',
		'readerTrans','coverageReducer','hasCoverage', '__path__'
	
		# Autoplot developers built a hard limit buffer into their das2 info
		# parser.  Try to route around the problem by dropping extra stuff
		,'paramValInfo'
	)

	tSingletons = (
		'description','das2Stream','qstream','validRange','server',
		'techContact','sciContact', 'securityRealm'
	)

	"""Write a utf-8 string that contains the stream"""
	fOut = StringIO()
	
	fOut.write("<stream version=\"2.2\">\r\n")
	fOut.write("  <properties\r\n")
	
	for sKey in dProps.keys():

		bCont = False
		for sTmp in tDrop:
			if sKey.startswith(sTmp):
				bCont = True
				break
		
		if bCont: continue

		if not isinstance(dProps[sKey], dict): continue

		# Now we're at the level where each item is a list, need to put them
		# back together for output
		for sSubKey in dProps[sKey]:
		
			# Replace special characters
			lValue = list( dProps[sKey][sSubKey])
			dReplace = {'&':'&amp;', '"':'&quot;', "'":'&apos;', "<":"&lt;",
		            	'>':'&gt;', '(':'', ')':''}
			lRepKeys = dReplace.keys()
			
			lNewValue = [None]*len(lValue)
			for i in range(0, len(lValue)):
				if lValue[i] in lRepKeys:
					lNewValue[i] = dReplace[ lValue[i] ]
				else:
					lNewValue[i] = lValue[i]
					
			sValue = "".join(lNewValue)

			if (sSubKey == '00') and (sKey in tSingletons):
				fOut.write( '    %s="%s"\r\n'%(sKey, sValue.strip("'")))
			else:
				fOut.write( '    %s_%s="%s"\r\n'%(sKey, sSubKey, sValue.strip("'")))

	fOut.write('  />\r\n')
	fOut.write('</stream>')
	sOut = fOut.getvalue()

	sRet = "[00]%06d%s"%(len(sOut), sOut)
	
	return sRet

# ########################################################################## #
# A real blast from the past... das1! 

def makeDas1(fLog, dConf, sPath):

	# If this does not have das2stream or qstream for formats, output the
	# dsdf itself
	sName = bname(sPath).replace(".dsdf","")
	dProps = _loadDsdf(dConf, sName, sPath, fLog)

	if (not _isPropTrue(dProps, 'qstream')) and \
	   (not _isPropTrue(dProps, 'das2Stream')) and \
	   (not _isPropTrue(dProps, 'das3Stream')):

		fIn = open(sPath, 'r')
		sDsdf = fIn.read()
		fIn.close()	
		return sDsdf
	else:
		return None

	


