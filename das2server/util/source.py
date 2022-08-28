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
from . import srcfunc

import das2

g_d1s_mime = "application/octet-stream"
g_d2s_mime = "application/vnd.das2.das2stream"
g_d2x_mime = "application/vnd.das2.das2doc+xml" #; charset=utf-8 (*.d2x)
g_qs_mime  = "application/vnd.das2.qstream"

#########################################################################

def stdFormKeys(sConvention):
	"""Get the standard time parameter keys based on the call convention
	In das3 the key names are picked for coordinate names to help the
	developer keep different physical dimensions separate.

	Returns 
		(sTimeBegKey, sTimeEndKey, sTimeMaxBinSzKey, sIntervalKey, sOptKey)
	"""
	if sConvention in ("das3","das2/v3","v3.0","v3"):
		return (
			"read.time.min",
			"read.time.max",
			"bin.time.max",
			"read.time.int",
			"read.opts"
			# Other possible keys
			# bin.freq.max
         # bin.merge.avg
         # bin.merge.peaks
         # bin.merge.min
         # bin.merge.max
         # dft.length
         # dft.slide
         # format.type
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
	sName = sName.rstrip(sExt);
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
	# If this is a remote server assume it's das2.2 until proved otherwise
	# This can be confusing, because this server can be listed in the dsdf
	# as well as remote servers.
	#
	# Also, the server value may have one or two parts

	dProto = _getDict(dOut, 'protocol')
	dProto['method'] = 'GET'
	
	sMe = webio.getScriptUrl().strip('/')
	sSrvType = 'das3'
	
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
			sSrvType = "das3"
	else:
		sServer = sMe
	
	if sSrvType == "das3":
		dProto['convention']	= 'das/3.0'
		sBaseUrl = "%s/source/%s/data"%(sServer, dProps["__caseid__"].lower())
	else:
		dProto['convention']	= 'das/2.2'
		sBaseUrl = "%s?server=dataset&dataset=%s"%(sServer, dProps["__caseid__"])

	dProto['baseUrls'] = [sBaseUrl]

	if ('WEBSOCKET_URI' in dConf) and (len(dConf['WEBSOCKET_URI']) > 6):
		dProto['baseUrls'].append(
			"%s/%s"%(dConf['WEBSOCKET_URI'], dProps["__caseid__"].lower())
		)

	return sBaseUrl


def _mergeSrcCoordInfo(dOut, dProps, fLog):
	"""Add "coordinates" info to the output dictionary.
	"""
	dIface  = _getDict(dOut, 'interface')
	dCoords = _getDict(dIface, 'coordinates')
	
	# By default das2/2.2 servers only know that there is a time coordinate
	# so set that one up.  
	dTime = _getDict(dCoords, 'time')

	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = stdFormKeys(
		dOut['protocol']['convention']
	)
	
	if 'name' not in dTime: dTime['name']  = 'Time'

	# Use the lowest numbered example for the default range, interval
	dTime['minimum'] = {'name':'Min', sV:None}
	dTime['maximum'] = {'name':'Max', sV:None}
	
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
			dTime['minimum']['set']['range'] = lTimeRng
			dTime['maximum']['set']['range'] = lTimeRng
	
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

	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = stdFormKeys("das3")

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
		dProto['examples'] = dExamples

# ########################################################################## #

def _mergeFormat(dConf, dOut, dProps, fLog):

	# Different das3 servers can have different capabilities so we *really*
	# shouldn't make api.json files for others.  I have done so here, but
	# they aren't in the catalog at least and they are hidden from wget.
	
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
		if sServer != sMe:
			dOut['interface']['formats'] = {}
			return

	
	lRdrOut = ['das', '1.0', 'binary']  # The default
	if _isPropTrue(dProps, 'qstream'):
		lRdrOut = ['qstream', None, 'binary']

	elif _isPropTrue(dProps, 'das2Stream'):
		lRdrOut = ['das', '2.2', 'binary']
		
	elif _isPropTrue(dProps, 'das3Stream'):
		lRdrOut = ['das', '3.0', 'binary']

	# Add our supported output conversion interface controls and parameters
	dOut['interface']['formats'] = output.getFormatSelection(dConf, lRdrOut)
	
	output.addFormatHttpParams(dConf, dOut['protocol']['http_params'])
	

# ########################################################################## #
# Merge 

def _mergeInternal(dOut, dConf, dProps, fLog):
	"""Get all the items needed for the internal server interface that are
	not to be sent out to the clients.  This includes:

	internal
		.command
			.read   (from reader=, das2Stream=, qstream=)
			.bin    (from reducer=, das2Stream=, qstream=)
			.cache  (from cacheReader=)

		.cache (from cacheLevel_XX=)  <-- Disk read/write info
		
		.authorization (from readAccess=)

		.authentication (from securityRealm=)
	"""
	
	# Save the mime-type for the command inputs and outputs
	bSkipReduce = False
	if _isPropTrue(dProps, 'qstream'):
		sMime = g_qs_mime
	elif _isPropTrue(dProps, 'das2Stream'):
		sMime = g_d2s_mime
	else:
		sMime = g_d1s_mime
		bSkipReduce = True

	(sBegKey, sEndKey, sResKey, sIntKey, sOptKey) = stdFormKeys(
		dOut['protocol']['convention']
	)

	dIntr = _getDict(dOut, 'internal')
	lCmd = _getList(dIntr, 'commands')

	# Reader Section #################################
	if 'reader' in dProps in '00' in dProps['reader']:
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
				sOptTplt = '#[%s # @ #]'%sOptKey

			sCmd = "%s%s%s"%(sRdr[:iBeg], sOptTplt, sRdr[iEnd+1:])
		else:
			sCmd = sRdr

		# Two variations, one for requires interval
		sInterval = ''
		if _isPropTrue(dProps, 'requiresInterval'):  # Ephemeris readers
			 sInternal = '#[%s] '%sIntKey
			
		if _isPropTrue(dProps, 'dropParams'):
			dCmd = {'template':'%s %s#[%s] #[%s]'%(
				sCmd, sInterval, sBegKey, sEndKey
			)}
		else:
			dCmd = {'template':
				'%s %s#[%s] #[%s] #[%s#@#]'%(sCmd, sInterval, sBegKey, sEndKey, sOptKey
			)}

		dCmd['role'] = 'read.source'
		dCmd['order'] = 1
		dCmd['trigger'] = [
			{'key':sBegKey}, {'key':sEndKey}, {'key':sIntKey}, {'key':sOptKey}
		]
		dCmd['output'] = sMime

		lCmd.append(dCmd)
	

	# Custom reducer ####################################
	if ('reducer' in dProps) and '00' in dProps['reducer']:
		sReducer = dProps['reducer']['00']
	
		if bSkipReduce or (sReducer in ('not_reducable','not_reducible')):
			dIntr['disable'] = [{"role":"reduce"}]
		else:
			lCmd.append({
				'role':'reduce',
				'template':'%s #[%s]'%(sReducer, sResKey),
				'trigger':[{"key":sResKey,"value":0,"compare":"gt"}],
				'order': 30,
				'input': sMime,
				'output': sMime
			})
	
	# no reducer mentioned, so just let the default get assigned by command.py
	
	# Cache Section #####################################
	if 'cacheLevel' in dProps:
		
		# If there is a custom cache reader in the dsdf we'll need to emit a 
		# cache template in the command section as well.
		if ('cacheReader' in dProps) and ('00' in dProps['cacheReader']):
			sCacheBin = dProps['cacheReader']['00']
	
			dCmd['read.cache'] = {"template":[
				"%s #[_DSDF_FILE] #[_CACHE_DIR] #[_NORM_READ_OPTS] "%sCacheBin,
				"#[%s] #[%s] #[%s]"%(sBegKey, sEndKey, sResKey)
			]}
			dCmd['read.cache']['input'] = sMime
			dCmd['read.cache']['output'] = sMime
		
		dCache = _getDict(dOut['internal'], 'cache')
		
		# The coordinate map for this cache is just the conventional items
		dCache['min_coord_params'] = [sBegKey],
		dCache['max_coord_params'] = [sEndKey],
		
		dCache['mime'] = sMime
		
		dSchemeToSize = {
			"yearly":"1 year", "monthly":"1 month", "daily":"1 day", 
			"hourly":"1 hour", "perminute":"1 minute", "persecond":"1 s"
		}

		dSets = _getDict(dCache, 'block_sets')
		for sLevel in dProps['cacheLevel']:
			l = [s.strip() for s in dProps['cacheLevel'][sLevel].split()]
			if len(l) < 2:
				fLog.write("ERROR: Misconfigured cache level in %s"%dProps['__path__'])
				continue
			sRes = l[0]
			
			if l[1] not in dConvert:
				fLog.write("ERROR: Misconfigured cache block size %s"%dProps['__path__'])
				continue
			sBlkSz = dConvert[l[1]]
			dBlk = {"block_size":[sBlkSz]}

			if sRes != 'intrinsic':
				dBlk['resolution'] = sRes
				dBlk['resolution_params'] = [sResKey]
		
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
		
		dIntr = _getDict(dOut, 'internal');
		dAuth = _getDict(dIntr, 'authorization')

		lMethods = [s.strip() for s in self.d['readAccess'].split('|')]
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
		dIntr = _getDict(dOut, 'internal');
		dAuth = _getDict(dIntr, 'authentication')
		
		dAuth['http_basic'] = {'security_realm':dProps['securityRealm']['00']}

# ########################################################################## #

def dsdf2Source(fLog, dConf, sPath, sTarget="any"):
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

	sName = sPath.replace(dConf['DATASRC_ROOT']+'/', '')
	sName.replace(".dsdf","").replace(".json",'')
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
		_mergeInternal(dOut, dConf, dDsdf, fLog)

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

def stripCppComments(fLog, sPath):
	lLines = []
	try:
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

	except FileNotFoundError:
		fIn.close()
		raise errors.ServerError("File '%s' does not exist."%sPath)

	fIn.close()

	return sData

def loadCommentedJson(fLog, sPath):
	"""Read a commented Json file

	Pre-parse a *.json file removing all C++ style commets, '//', and then
	build a dictionary using the standard json.loads function.

	Returns (dict): A dictionary object if the file exists and could be read
		otherwise a ServerError is raised if basic parsing failed.
	"""
	sData = stripCppComments(fLog, sPath)
	
	try:
		dOut = json.loads(sData)
	except ValueError as e:
		raise errors.ServerError("Syntax error in %s: %s\n"%(sPath, str(e)))

	return dOut


# ########################################################################## #

def includePath(fLog, dConf, sPath):
	"""Get the include path for data source definitions, always include
	the current directory first so that actions are predictable to server
	administrators
	"""
	l = [ os.path.abspath(dname(sPath)) ]

	if 'DATASRC_INC' in dConf:
		l.append(dConf['DATASRC_INC'])
	elif 'DATASRC_ROOT' in dConf:
		l.append(pjoin(dConf['DATASRC_ROOT'], '_include_'))

	return l

def include(fLog, dCur, lIncPath, nLevel = 1):
	"""Handle Include sections for das datasource definitons. 

	For a given dictionary dCur:
	
	1. While there are any keys named '$include':
		* Error out if content of the '$include' key is not a list

		* For each filename in the list parse the content and include it
		  as if it were added to the file via a simple C-style include.

	2. Now iterate over all keys: 

		* If the key starts with '$', then ignore it.
		
		If the value for the key is also a dictionary recusively call this
		function on the sub-dictionary.

	The maximum recursion level is 12, which should be good enough for almost
	all cases, but still stops a run-away recursive include.
	"""

	if nLevel > 11:
		raise errors.ServerError(
			"Object depth of 12 encountered, does one of your files accidentally"+\
			" include itself?"
		)

	nIncludes = 0
	while '$include' in dCur:
		nIncludes += 1
		if nIncludes > 12:
			raise errors.ServerError(
				"Recursive $include limit of 12 encountered, does one of your"+\
				" files accidentally include itself?"
			)

		if not isinstance(dCur['$include'], list):
			raise errors.ServerError("$include does not contain a file list.")

		lFiles = dCur.pop('$include')

		for sFile in lFiles:
			bLoaded = False
			sPath = None
			for sDir in lIncPath:
				sPath = pjoin(sDir, sFile)
				if os.path.isfile(sPath):
					sSub = stripCppComments(fLog, sPath)
					bLoaded = True
					break

			if not bLoaded:
				raise errors.ServerError(
					"Couldn't find include file %s in %s"%(sFile,str(lIncPath)
				));

			sSub = '{%s}'%sSub # Put it in a temporary dictionary structure

			dSub = json.loads(sSub)

			for sKey in dSub:
				if sKey in dCur:
					fLog.write("WARNING: Ignoring sub object %s from file %s "+\
						"since it would hide an equivalent object in the parent."%(
						sKey, sPath
					))
				dCur[sKey] = dSub[sKey]


	# All the includes should be done at this level, now step down as needed
	for sKey in dCur:
		if sKey.startswith('$'): continue

		if isinstance(dCur[sKey], dict):
			include(fLog, dCur[sKey], lIncPath, nLevel+1)

# ########################################################################## #
def generate(fLog, dConf, dTop, dCur=None, nLevel=1):
	"""Look for definition generators in the source description and 
	call them with the given aruments.  All generators are called with
	the original top level dictionary as the first argument, and the output
	of the generator must be either a list or a dictionary that is expanded
	in place.

	Generator functions must not output $include directives since that
	processing stage is *over* before this is run.  The basic processing
	path is:

	1. If the top level dictionary contains a key named $generate then
	   then run the indicated generator.

	2. If a sub item is a dictionary, call this function recursively.


	Stop if the object depth hits 13 since that probably means something
	is wrong
	"""

	if nLevel > 11:
		raise errors.ServerError(
			"Object depth of 12 encountered, does one of your files accidentally"+\
			" include itself?"
		)

	if dCur == None:
		dCur = dTop

	# Let's do this bottom up instead of top down so that $generate 
	# sections can't have other generators.
	for sKey in dCur:
		if isinstance( dCur[sKey], dict):
			generate(fLog, dConf, dTop, dCur[sKey], nLevel+1)

	if '$generate' in dCur:
		dFuncs = dCur.pop('$generate')
	
		for sFunc in dFuncs:
			if sFunc not in srcfunc.g_dRegistry:
				raise errors.ServerError(
					"Unknown server side source function '%s' referenced from '%s"%(
					sFunc, bname(dTop['__path__'])
				))

			func = srcfunc.g_dRegistry[sFunc]

			# "whole" file goes to the function to use for global inspection
			dSub = func(fLog, dConf, dTop, dFuncs[sFunc])

			fLog.write("Substituting: %s -> %s"%(sFunc, dSub))

			# Expand the output into the current item, generated commands shouldn't
			# step on other output
			for sKey in dSub:
				if sKey in dCur:
					fLog.write("WARNING: Ignoring generated sub object %s from file %s "+\
						"since it would hide an equivalent object in the parent."%(
						sKey, sPath
					))
				dCur[sKey] = dSub[sKey]


# ########################################################################## #

def json2Source(fLog, dConf, sPath, sTarget='external'):
	"""
	Since the files on disk are pretty much the expected data source,
	Function is pretty simple it just loads the file from disk stripping
	out the comments.
	"""

	fLog.write("INFO: Reading %s"%sPath)
	
	lLines = []
	
	dTop = loadCommentedJson(fLog, sPath)

	# If the external catalog entry had no label, give it one based on the
	# filename
	if 'label' not in dTop['external']:
		dTop['external']['label'] = bname(sPath).replace('.json','')

	# And save the path to the file as a whole
	dTop['__path__'] = sPath

	# Now load any include files
	lIncPath = includePath(fLog, dConf, sPath)
	include(fLog, dTop, lIncPath)

	# Now generate any required sections, if we're not just doing include
	# diagnostics
	if sTarget != 'include':
		generate(fLog, dConf, dTop)

	# If usage is for external clients, then cut out the whole internal section
	if sTarget == 'external':
		dTop.pop('internal')

	# If usage is for internal operations, then cut out the interface section
	elif sTarget == 'internal':
		dTop['external'].pop('interface')

	return dTop

# ########################################################################## #

def _dsdfOverRide(dSrcDsdf, dJsonSrc):
	"""Given two partial HttpStreamSrc dictionaries, override the up-converted
	dsdf dictionary with setting sfrom the new json dictionary.  Sections are
	overridden as follows:
	
	interface.name = Set to 'das3 Source'
	protocol.convention = 'das3'

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
		if s in dJsonSrc:
			dOut[s] = dJsonSrc[s]
	
	if 'interface' in dJsonSrc:

		for sSection in ('examples','coordinates','data','options','formats'):
			if sSection in dJsonSrc['interface']:
				for sKey in dJsonSrc['interface'][sSection]:
					dSection = _getDict(dOut['interface'], sSection)
					dSection[sKey] = dJsonSrc['interface'][sSection][sKey]
			
	if 'protocol' in dJsonSrc:
		for sKey in dJsonSrc['protocol']:
			dOut['protocol'][sKey] = dJsonSrc['protocol'][sKey]

	dOut['protocol']['convention'] = 'das3'

	if 'internal' in dJsonSrc:
		if 'internal' not in dOut: dOut['internal'] = {}

		if 'cache' in dJsonSrc['internal']:
			dOut['internal']['cache'] = dJsonSrc['internal']['cache']
		if 'command' in dJsonSrc['internal']:
			for sCmd in dJsonSrc['command']:
				dOut['internal']['command'][sKey] = dJsonSrc['internal']['command'][sKey]
	
	return dOut

# ########################################################################## #

def load(fLog, dConf, sSource, sTarget="external"):
	"""Create an HttpStreamSrc object from server configuration files.

	Source conflict resolution:
	   * If there exists a *.json file for the source and a .dsdf, then the
	     .json file is read and the *.dsdf file is ignored.

	The three main section of the HttpStreamSrc definition are from the
	outside in:
	
		interface - What clients present to users, or downstream tools
			Sections: example, coord, data, option, format

 	   protocol  - What clients use to talk to this server
      	Sections: method, base_urls, authentication, http_params

	   internal  - How protocol requests are turned into command lines
			Sections: cache, 

	* If the main focus of the load is an external API request then only
	  the external catalog item is returned.

	* If the main focus is internal server operations then everything is
	  returned

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
	
	(sName, sPath) = _findSrcNoCase(dConf['DATASRC_ROOT'], sSource, '.json', fLog)
	if sPath != None:
		dSource = json2Source(fLog, dConf, sPath, sTarget)
		return dSource


	# Fall back to older DSDF if that is avaialable
	(sName, sPath) = _findSrcNoCase(dConf['DATASRC_ROOT'], sSource, '.dsdf', fLog)
	if sPath != None:
		dSource = dsdf2Source(fLog, dConf, sPath, sTarget)
		return dSource

	raise errors.QueryError(u"Data source %s doesn't exist on this server"%sSource)

# ########################################################################## #

def internal(fLog, dConf, sSource):
	"""Short cut for load(dConf, sSource, fLog, 'internal')"""
	return load(fLog, dConf, sSource, 'internal')

def external(fLog, dConf, sSource):
	"""Short cut for load(dConf, sSource, fLog, 'external')"""
	return load(fLog, dConf, sSource, 'external')
