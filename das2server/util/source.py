"""Producing HttpStreamSrc information, this is a standalone module and
   doesn't need the (overloaded) dsdf module.
"""
import os
import sys
import os.path
from os.path import join as pjoin
from os.path import basename as bname
from os.path import dirname as dname
from urllib.parse import quote_plus
import json
from copy import deepcopy

from . import errors
from . import webio
from . import output

import das2

#########################################################################

def stdFormKeys(sConvention):
	"""Get the standard time parameter keys based on the call convention
	In das2/v2.3 the key names are picked for coordinate names to help
	the developer keep different physical dimensions separate.

	Returns 
		(sTimeBegKey, sTimeEndKey, sTimeMaxBinSzKey, sIntervalKey, sOptKey)
	"""
	if sConvention in ("das2.3","das2/v2.3","v2.3"):
		return (
			"read.time.min",
			"read.time.max",
			"bin.time.max",
			"read.time.interval",
			"read.options"
			# Other possible keys
			# bin.freq.max
         # bin.merge.avg
         # bin.merge.peaks
         # bin.merge.min
         # bin.merge.max
         # dft.length
         # dft.slide
         # format.mime
		)
	else:
		return ('start_time','end_time','resolution','interval','params')

##############################################################################

def _findSrcNoCase(sRoot, sSource, sExt, fLog):
	"""Look up source files using a case sensitive root and a case insensitive
	remaning path.  If sSource doesn't end in sExt, that string is appended 
	"""

	if not sSource.endswith(sExt):
		sSource = "%s%s"%(sSource, sExt)

	if not os.path.isdir(sRoot): return (None,None)

	lIn = sSource.split('/')
	sPath = sRoot
	
	lName = []
	while len(lIn) > 0:
		sPart = None
		for sEntry in os.listdir(sPath):
			#fLog.write("Checking %s vs %s"%(sEntry, lIn[0]))
			if sEntry.lower() == lIn[0].lower():
				sPart = sEntry
				lIn.pop(0)
				lName.append(sEntry)
				break;
		if sPart == None: return (None,None)
		sPath = "%s/%s"%(sPath, sPart)
	
	if not os.path.isfile(sPath): return (None,None)
	
	sName = '/'.join(lName)
	sName = sName.rstrip('.dsdf');
	return (sName, sPath)

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

		fLog.write("   Reading: %s"%sPath)

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
		dDsdf['__caseid__'] = sPath.replace(dConf['DSDF_ROOT'],'')
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

def _mergeProto(dOut, dProps, fLog):
	# If this is a remote server assume it's das2.2 until proved otherwise
	# This can be confusing, because this server can be listed in the dsdf
	# as well as remote servers.
	#
	# Also, the server value may have one or two parts
	
	dProto = _getDict(dOut, 'protocol')
	dProto['method'] = 'GET'
	
	sMe = webio.getScriptUrl().strip('/')
	sSrvType = 'das2.3'
	
	if 'server' in dProps and '00' in dProps['server']:
		sSrv = dProps['server']['00']
		lSrv = [ s.strip() for s in sSrv.split('|')]
		if len(lSrv) > 1:
			sSrvType = lSrv[0]
			sServer = lSrv[1].strip('/')
		else:
			# If no server type given, assume 2.2
			sSrvType = "das2.2"
			sServer = lSrv[0].strip('/')

		if sServer == sMe:  # If the listed server is me, override the type
			sSrvType = "das2.3"
	else:
		sServer = sMe
	
	if sSrvType == "das2.3":
		dProto['convention']	= 'das2/v2.3'
		sBaseUrl = "%s/source/%s/data"%(sServer, dProps["__caseid__"].lower())
	else:
		dProto['convention']	= 'das2/v2.2'
		sBaseUrl = "%s?server=dataset&dataset=%s"%(sServer, dProps["__caseid__"])

	dProto['base_urls'] = [sBaseUrl]
	return sBaseUrl


def _mergeSrcCoordInfo(dOut, dProps, dUser, fLog):
	"""Add "coordinates" info to the output dictionary.
	"""
	dIface  = _getDict(dOut, 'interface')
	dCoords = _getDict(dIface, 'coord')
	
	# By default das2/2.2 servers only know that there is a time coordinate
	# so set that one up.  
	dTime = _getDict(dCoords, 'time')

	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = stdFormKeys(
		dOut['protocol']['convention']
	)
	
	if 'name' not in dTime: dTime['name']  = 'Time'

	# Use the lowest numbered example for the default range, interval
	dTime['min'] = {sV:None}
	dTime['max'] = {sV:None}
	
	dTime['units'] = {'value':'UTC'}
		
	if 'requiresInterval' in dProps:
		dTime['interval'] = {sV:None}
	else:
		dTime['res'] = {sV:None, "units":"s"}
	
	sNum = None
	if 'exampleRange' in dProps:
		lNums = list(dProps['exampleRange'].keys())
		lNums.sort()
		sNum = lNums[0]
	
		lTmp = [s.strip() for s in dProps['exampleRange'][sNum].split('|')]
		lTmp = [s.strip() for s in lTmp[0].split('to')]
		dTime['min'][sV] = lTmp[0]		
		if len(lTmp) > 1:
			dTime['max'][sV] = lTmp[1].replace('UTC','').strip()
	
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
		if dTime['min'][sV] and dTime['max'][sV]:
			dtBeg = das2.DasTime(dTime['min'][sV])
			dtEnd = das2.DasTime(dTime['max'][sV])
			dTime['res'][sV] = (dtEnd - dtBeg) / 2000.0
				
	# Set up the alteration rules
	dTime['min']['set'] = {'param':sBegKey, 'required':True}
	dTime['max']['set'] = {'param':sEndKey, 'required':True}
	
	if 'validRange' in dProps:
		lTimeRng = [ s.strip() for s in dProps['validRange']['00'].split('to') ]
		if len(lTimeRng) > 1:
			dTime['min']['set']['range'] = lTimeRng
			dTime['max']['set']['range'] = lTimeRng
	
	if 'interval' in dTime:
		dTime['interval']['set'] = {'param':sIntKey, 'required':True}
	else:
		dTime['res']['set'] = {'param':sResKey, 'required':False}


	if 'coord' in dProps:
		for sNum in dProps['coord']:
			lItem = [s.strip() for s in dProps['coord'][sNum].split('|')]
			if lItem[0].lower() == 'time':
				if len(lItem) > 1:  dTime['title'] = lItem[1]
			else:
				dVar = _getDict(dCoords, lItem[0])
				dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
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
			dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
			if len(lItem) > 1: dVar['title'] = lItem[1]
			if len(lItem) > 2: dVar['units'] = lItem[2]
		
	if 'data' in dProps:
		for sNum in dProps['data']:
			lItem = [s.strip() for s in dProps['data'][sNum].split('|')]
		
			dVar = _getDict(dData, lItem[0])
			dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
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

	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = stdFormKeys("das2/v2.3")

	dProto = _getDict(dOut, 'protocol')
	dGet = dProto['http_params']
	
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
			'type':'flag_set',
			'required':False,
			'title': 'Optional reader arguments',
			'flag_sep': ' ',
			'flags': dFlags
		}
		
		for sNum in lNums:
			lParam = [s.strip() for s in dProps['param'][sNum].split('|') ]
			if lParam[0].lower() == 'integer':
				dFlags[sNum] = {'type':'integer', 'name':lParam[0], 'title':lParam[1] }
			elif lParam[0].lower() == 'real':
				dFlags[sNum] = {'type':'real', 'name':lParam[0], 'title':lParam[1] }
			else:
				dFlags[sNum] = {'value':lParam[0], 'name':lParam[0], 'title':lParam[1] }
	
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
	dOpts = _getDict(dIface, 'option')
	
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
			sOptName = dFlag['name'].strip('-').strip().lower()
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
	
	dExamples = {}
	for sNum in lRange:
		bKeep = True
		dQuery = {}
		dExample = {"params":dQuery}
		sId = "example_%s"%sNum
		dExample['name'] = "Example %s"%sNum
			
		lTmp = [s.strip() for s in dProps['exampleRange'][sNum].split('|')]
		if len(lTmp) > 1:
			dExample['title'] = lTmp[1]
			
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
		#  option.10kHz = true
		#  option.1kHz = true
		#
		# And to these HTTP param flags:
		#
		#  ?read.options=10kHz 1kHz&
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
				dQuery['option.extra'] = {'extra': sOuts}
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
		dExamples[sId] = dExample
		
	if len(dExamples) > 0:
		dProto = _getDict(dOut, 'interface')
		dProto['example'] = dExamples
	

def _mergeFormat(dConf, dOut, dProps, fLog):

	# Set base reader output format, downstream processors may add other
	# avaialble formats.
	if _isPropTrue(dProps, 'qstream'):
		dDefFmt = {
			"name":"QStream",
			"title":"QStream, application/vnd.das2.qstream (*.qds)",
			"mime": "application/vnd.das2.qstream", 
			"extension": ".qds",
			"enabled": {"value":True },
		}
		sDefKey = 'qstream'
	elif _isPropTrue(dProps, 'das2Stream'):
		dDefFmt =  {
			"name":"das2 binary",
			"title":"das2 binary stream, application/vnd.das2.das2stream (*.d2s)",
			"mime":"application/vnd.das2.das2stream",
			"extension":".d2s",
			"enabled":{"value":True},
		}
		sDefKey = 'das2binary'
	else:
		dDefFmt =  {
			"name":"das1 binary",
			"mime":"application/octet-stream",
			"title":"das1 binary stream, application/octet-stream (*.bin)",
			"extension":".bin",
			"enabled":{"value":True},
		}
		sDefKey = 'das1binary'

	dOut['interface']['format'] = {sDefKey:dDefFmt}
	dOut['interface']['default'] = sDefKey

	
	# Different das2/v2.3 servers can have different capabilities so 
	# we *really* shouldn't make api.json files for others.  I have here
	# but they aren't in the catalog at least and they are hidden from
	# wget.
	
	# If this really is one of my data sources, add in the extra formatting
	# options provided by this server

	sMe = webio.getScriptUrl().strip('/')
	bIsMe = True
	
	if 'server' in dProps and '00' in dProps['server']:
		sSrv = dProps['server']['00']
		lSrv = [ s.strip() for s in sSrv.split('|')]
		if len(lSrv) > 1:
			sServer = lSrv[1].strip('/')
		else:
			sServer = lSrv[0].strip('/')

		bIsMe = (sServer == sMe)
	
	if bIsMe and not _isPropTrue(dProps, 'qstream'):
		# Add our supported output conversion interface controls and parameters
		output.addFormatSelection(dConf, dOut['interface']['format'])
		output.addFormatHttpParams(dConf, dOut['protocol']['http_params'])


# ########################################################################## #
def _mergeInternal(dOut, dDsdf, fLog):
	"""Get all the items needed for the internal server interface that are
	not to be sent out to the clients.

	"""
	dImpl = {}


	if 'OPTIONS' not in dSrc['QUERY_PARAMS']:
		raise errors.ServerError("OPTIONS section missing from QUERY_PARAMS")
	dOpts = dSrc['QUERY_PARAMS']['OPTIONS']


	if 'readerCmd' in self.d:
		dImpl['_reader'] = {'_cmd':self.d['readerCmd']}
	else:
		if 'requiresInterval' in self.d:
			dImpl['_reader'] = {
				'_cmd':"%s %%{time.int} %%{time.min} %%{time.max}"%self.d['reader']
			}
		else:
			dImpl['_reader'] = {'_cmd':
				"%s %%{time.min} %%{time.max}"%self.d['reader']
			}
			if len(dOpts) == 0:
				dImpl['_reader']['_cmd'] += " %{params}"

		# now add in all options...
		for sKey in dOpts:
			dImpl['_reader']['_cmd'] += " %%{%s}"%sKey

	if 'reducerCmd' in self.d:
		dImpl['_reducer'] = {'_cmd':self.d['reducerCmd']}
	else:
		if 'reducer' in self.d and \
			(self.d['reducer'] not in ('not_reducable','not_reducible')):

			dImpl['_reducer'] = {'_cmd':"%s %%{time.res}"%self.d['reducer']}

		elif 'reducer' not in self.d:
			# Get default reducer based on the stream type
			if 'qstream' in self.d:
				if 'QDS_REDUCER' in dConf:
					dImpl['_reducer'] = {'_cmd':"%s %%{time.res}"%dConf['QDS_REDUCER']}
			else:
				if 'D2S_REDUCER' in dConf:
					dImpl['_reducer'] = {'_cmd':"%s -b %%{time.min} %%{time.res}"%dConf['D2S_REDUCER']}

	if 'cacheReader' not in self.d:
		sCacheDir =  pjoin(dConf['CACHE_ROOT'], 'data', self.sName)
		sCacheRdrArgs = "%s %s ${NORM_OPTIONS} %%{time.beg} %%{time.end} %%{time.res}"%(
			self.sPath, sCacheDir)

		if 'qstream' in self.d:
			if 'QDS_CACHE_RDR' in dConf:
				dImpl['_cache_reader'] = {'_cmd':"%s %s"%(dConf['QDS_CACHE_RDR'], sCacheRdrArgs)}
		else:
			if 'D2S_CACHE_RDR' in dConf:
				dImpl['_cache_reader'] = {'_cmd':"%s %s"%(dConf['D2S_CACHE_RDR'], sCacheRdrArgs)}

	else:
		dImpl['_cache_reader'] = {'_cmd':self.d['cacheReader']}

	# Reader command line translations
	dTrans = self._getArgTrans(fLog, 'reader', dSrc)
	if len(dTrans) > 0:
		dImpl['_reader']['_translate'] = dTrans


	# Cache control information (internal)

	# This is hard locked for now to just be time
	# in the future support looking this up, say for example
	# ['lat','long']
	# ['time','freq']
	lCacheCoords = ['time']
	dRawLvls = self.getCacheLevels()
	if len(dRawLvls) > 0:
		if 'time' not in dSrc['COORDINATES']:
			raise errors.ServerError(
				"Time based cache blocks defined for non-time datasource"
			)

		dCachInCoords = {'_block_by':lCacheCoords}
		dLvls = {}
		for sKey in dRawLvls:
			dLvls[sKey] = {
				'_resolution':dRawLvls[sKey][0],
				'_units':dRawLvls[sKey][1],
				'_scheme':dRawLvls[sKey][2]
			}
			if dRawLvls[sKey][3]:
				dLvls[sKey]['_reader_args'] = dRawLvls[sKey][3]

		dCachInCoords['_lines'] = dLvls
		dImpl['_cache'] = dCachInCoords

	# Security authorization

	if 'readAccess' in self.d:
		dAuth = {'_dsdf_compat':self.d['readAccess']}
		if 'securityRealm' in self.d:
			dAuth['_realm'] = self.d['securityRealm']

		lMethods = [s.strip() for s in self.d['readAccess'].split('|')]
		if len(lMethods) > 0:
			lMethOut = []
			for i in range(0, len(lMethods)):

				lMeth = [s.strip() for s in lMethods[i].split(':')]
				#fLog.write("DEBUG: auth methods %s"%lMeth)
				if len(lMeth) < 2:
					raise errors.ServerError(
						"Syntax error in readAccess key value"
					)

				sCheckType = lMeth[0].upper().strip()

				lMethOut.append({'_check':sCheckType, '_values': lMeth[1:]})

			dAuth['_methods'] = lMethOut
			dImpl['_authorization'] = dAuth


	dImpl['_local_id'] = self.sName
	dImpl['_local_path'] = self.sPath

	return dImpl


# ########################################################################## #

def _dsdf2Source(dConf, sPath, fLog, sTarget="any"):
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
	dDsdf = _loadDsdf(dConf, sName, sPath, fLog)

	dOut = {}

	#sCustom = sSource.replace('.dsdf','.json')
	#if sSource.endswith('.dsdf') and os.path.isfile(sCustom) :
	#	fIn = open(dNode['filename'])
	#	dOut = json.load(fIn)
	#	fIn.close()

	# End load custom settings

	# The disk entries may have been hand edited.  Don't override the name and
	# description, go ahead and smash the type and path
	if 'name' not in dOut: dOut['name'] = dDsdf['__name__']
	if 'title' not in dOut and 'description' in dDsdf: 
		dOut["title"] = dDsdf['description']['00']
	dOut['type'] = 'HttpStreamSrc'
	dOut['version'] = "0.7"


	# If this is an internal call load the command and cache info
	if sTarget in ('internal','any'):
		_mergeInternal(dOut, dDsdf, fLog)

	# potentially override the base url and set the protocol convention
	sBaseUrl = _mergeProto(dOut, dDsdf, fLog)
	
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
	
	if sTarget in ('external', 'full'):
		_mergeSrcCoordInfo(dOut, dDsdf, fLog)
		_mergeSrcDataInfo(dOut, dDsdf, fLog)
	
	# Set the authentication information
	dProto = dOut['protocol']	
	if 'securityRealm' in dDsdf:
		dProto['authentication'] = {
			'required':True, 'realm':dDsdf['securityRealm']['00']
		}
	else:
		dProto['authentication'] = {'required':False}
	
	dGet = {}
	dProto['http_params'] = dGet
	
	# Assume that dsdf files only support the old das2.2 API.
	# The .json files can do whatever they want.
	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = stdFormKeys(dProto['convention'])

	dGet[sBegKey] = {
		'required':True, 'type':'isotime',
		'name':'Min Time', 'title':'Minimum time value to stream',
	}
		
	dGet[sEndKey] = {
		'required':True, 'type':'isotime',
		'name':'Max Time', 'title':'Maximum Time Value to stream',
	}
	
	# See if requires interval is set, if not
	if _isPropTrue(dDsdf, 'requiresInterval'):
		dGet[sIntKey] = {
			'required':True, 'type':'real', 'units':'s',
			'name':'Interval', 
			'title':'Time interval between model calculations/interpolations',
			'description': 'This parameter is used with data generated from models '
			   'or table interpolations such as SPICE Ephemerides and '
				'magnetic field models',
		}

	else:
		dGet[sResKey] = {
			'required':False, 'type':'real', 'units':'s',
			'name':'Resolution', 
			'title':'The maximum time bin width for bin-reduced data in seconds',
			'description':'The server will return data at or better than the given '
            'x-axis resolution if possible.  Leave un-specified to get data '
			   'at intrinsic resolution without server side averages',
		}

	# Convert any read params to a read.options parameter
	_mergeDas2Params(dOut, dDsdf, fLog)
		
	# Provide examples for external interfaces
	if sTarget in ('external', 'full'):
		_mergeExamples(dOut, dDsdf, sBaseUrl, fLog)
		_mergeFormat(dConf, dOut, dDsdf, fLog)

	# Provide command and cache handling for internal operations
	

	return dOut

# ########################################################################## #

def _json2Source(dConf, sPath, fLog, sTarget='external'):
	"""
	Since the files on disk are pretty much the expected data source,
	Function is pretty simple it just loads the file from disk stripping
	out the comments.
	"""

	fLog.write("INFO: Reading %s"%sPath)
	
	lLines = []
	if not os.path.isfile(sPath):
		return None

	fIn = open(sPath, encoding='UTF-8')
	for sLine in fIn:
		sLine = sLine.strip()
		# Walk the line, if we are not in quotes and see '//' ignore everything
		# from there to the end
		iQuote = 0
		iComment = -1
		n = len(sLine)
		for i in range(n):
			if sLine[i] == '"': 
				iQuote += 1
				continue
			if sLine[i] == '/' and (i < n-1) and (sLine[i+1] == '/') \
				and (iQuote % 2 == 0):
				iComment = i
				break;
				
		if iComment > -1:
			sLine = sLine[:iComment]
			sLine = sLine.strip()
		
		lLines.append(sLine)

	sData = '\n'.join(lLines)
	fIn.close()
	
	try:
		dOut = json.loads(sData)
	except ValueError as e:
		raise errors.ServerError("Syntax error in %s: %s\n"%(sPath, str(e)))

	# If the source had no name, give it one based on the filename
	if 'name' not in dOut:
		dOut['name'] = basename(sPath).replace('.json','')

	return dOut


# ########################################################################## #

def _dsdfOverRide(dSrcDsdf, dSrcJson):
	"""Given two partial HttpStreamSrc dictionaries, override the up-converted
	dsdf dictionary with setting sfrom the new json dictionary.  Sections are
	overridden as follows:
	
	interface.name = Set to 'das2/v2.3 Source'
	protocol.convention = 'das2/v2.3'

	Override, .* means sub items overridden
	------------------
	name
	title
	description
	interface.example.*
	interface.coord.*
	interface.data.*
	interface.option <-- Entire DSDF option area overridden

	protocol.*
	
	internal.commands.*
	internal.cache  <-- Entire DSDF option area overridden
	"""
	
	dOut = dSrcDsdf

	for s in ('name','title','description'):
		if s in dSrcJson:
			dOut[s] = dSrcJson[s]
	
	if 'interface' in dJsonSrc:

		for sSection in ('example','coord','data'):
			if sSection in dJsonSrc['interface']:
				for sKey in dJsonSrc['interface'][sSection]:
					dSection = _getDict(dOut['interface'], sSection)
					dSection[sKey] = dJsonSrc['interface'][sSection][sKey]
			
	if 'protocol' in dJsonSrc:
		for sKey in dJsonSrc['protocol']
			dOut['protocol'][sKey] = dJsonSrc['protocol'][sKey]

	dOut['protocol']['converntion'] = 'das2/v2.3'

	if 'internal' in dJsonSrc:
		if 'cache' in dJsonSrc['internal']:
			dOut['internal']['cache'] = dJsonSrc['internal']['cache']
		if 'command' in dJsonSrc['internal']:
			for sCmd in dJsonSrc['command']:
				dOut['internal']['command'][sKey] = dJsonSrc['internal']['command'][sKey]
	
	return dOut

# ########################################################################## #

def load(dConf, sSource, fLog, sTarget="external"):
	"""Create an HttpStreamSrc object from server configuration files

	The three main section of the HttpStreamSrc definition are:
	
		interface - What clients present to users, or downstream tools
 	   protocol - What clinets use to talk to this server
	   internal - How protocol requests are turned into command lines

	If the main focus of the load is an external API request then then
	'internal' section is dropped.  If the main focus is internal 
	server operations then 'interface' is dropped.

	Args:
		dConf - A dictionary containing the server configuration

		sSource - The on-disk location of the dataset source description.
		   This may be a file that ends in .dsdf or a new one that ends
		   in *.json

		fLog - An object with a .write method.

		sTarget - Has special meaning if given one of the strings
			'internal' or 'external'.  Pretty much ignore otherwise.

	Returns:
		An source dictionary.  If called as 'external' then this is
		a legal 'HttpStreamSrc' file that can be transmitted off the
		server.
	
	Throws:
		QueryError neither a .dsdf and .json file exists for this source
		RemoteServer if source is pointing to another server
		ServerError if there is a syntax error or other misconfiguration
	"""
	
	dSrcDsdf = {}
	dSrcJson = {}

	(sName, sDsdfPath) = _findSrcNoCase(dConf['DSDF_ROOT'], sSource, '.dsdf', fLog)
	if sDsdfPath != None:
		# We have a dsdf
		dSrcDsdf = _dsdf2Source(dConf, sDsdfPath, fLog, sTarget)
		sJsonPath = sDsdfPath.replace('.dsdf','.json')

		# See if there are overrides in a json file
		if os.path.isfile(sJsonPath):
			dSrcJson = _json2Source(dConf, sJsonPath, fLog, sTarget)
			return _dsdfOverRide(dSrcDsdf, dSrcJson)
		else:
			return dSrcDsdf

	else:
		dSrcDsdf = None
		(sName, sJsonPath) = _findSrcNoCase(dConf['DSDF_ROOT'], sSource, '.json', fLog)
		if sJsonPath == None:
			raise errors.QueryError(u"Data source %s doesn't exist on this server"%sSource)
		
		return _json2Source(dConf, sJsonPath, fLog, sTarget)

# ########################################################################## #

def internal(dConf, sSource, fLog):
	"""Short cut for load(dConf, sSource, fLog, 'internal')"""
	return load(dConf, sSource, fLog, 'internal')

def external(dConf, sSource, fLog):
	"""Short cut for load(dConf, sSource, fLog, 'external')"""
	return load(dConf, sSource, fLog, 'external')
