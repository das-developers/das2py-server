"""Producing HttpStreamSrc information, this is a standalone module and
   doesn't need the (overloaded) dsdf module.
"""
import os
import os.path
from os.path import join as pjoin
from os.path import basename as bname
from os.path import dirname as dname
from urllib.parse import quote_plus

from . import errors
from . import webio

import das2

#########################################################################
#def _getInternalInterface(self, fLog, dConf, dSrc):
#	"""Get all the items needed for the internal server interface that are
#	not to be sent out to the clients.

#	"""
#	dImpl = {}


#	if 'OPTIONS' not in dSrc['QUERY_PARAMS']:
#		raise errors.ServerError("OPTIONS section missing from QUERY_PARAMS")
#	dOpts = dSrc['QUERY_PARAMS']['OPTIONS']


#	if 'readerCmd' in self.d:
#		dImpl['_reader'] = {'_cmd':self.d['readerCmd']}
#	else:
#		if 'requiresInterval' in self.d:
#			dImpl['_reader'] = {
#				'_cmd':"%s %%{time.int} %%{time.min} %%{time.max}"%self.d['reader']
#			}
#		else:
#			dImpl['_reader'] = {'_cmd':
#				"%s %%{time.min} %%{time.max}"%self.d['reader']
#			}
#			if len(dOpts) == 0:
#				dImpl['_reader']['_cmd'] += " %{params}"

#		# now add in all options...
#		for sKey in dOpts:
#			dImpl['_reader']['_cmd'] += " %%{%s}"%sKey

#	if 'reducerCmd' in self.d:
#		dImpl['_reducer'] = {'_cmd':self.d['reducerCmd']}
#	else:
#		if 'reducer' in self.d and \
#			(self.d['reducer'] not in ('not_reducable','not_reducible')):

#			dImpl['_reducer'] = {'_cmd':"%s %%{time.res}"%self.d['reducer']}

#		elif 'reducer' not in self.d:
#			# Get default reducer based on the stream type
#			if 'qstream' in self.d:
#				if 'QDS_REDUCER' in dConf:
#					dImpl['_reducer'] = {'_cmd':"%s %%{time.res}"%dConf['QDS_REDUCER']}
#			else:
#				if 'D2S_REDUCER' in dConf:
#					dImpl['_reducer'] = {'_cmd':"%s -b %%{time.min} %%{time.res}"%dConf['D2S_REDUCER']}

#	if 'cacheReader' not in self.d:
#		sCacheDir =  pjoin(dConf['CACHE_ROOT'], 'data', self.sName)
#		sCacheRdrArgs = "%s %s ${NORM_OPTIONS} %%{time.beg} %%{time.end} %%{time.res}"%(
#			self.sPath, sCacheDir)

#		if 'qstream' in self.d:
#			if 'QDS_CACHE_RDR' in dConf:
#				dImpl['_cache_reader'] = {'_cmd':"%s %s"%(dConf['QDS_CACHE_RDR'], sCacheRdrArgs)}
#		else:
#			if 'D2S_CACHE_RDR' in dConf:
#				dImpl['_cache_reader'] = {'_cmd':"%s %s"%(dConf['D2S_CACHE_RDR'], sCacheRdrArgs)}

#	else:
#		dImpl['_cache_reader'] = {'_cmd':self.d['cacheReader']}

#	# Reader command line translations
#	dTrans = self._getArgTrans(fLog, 'reader', dSrc)
#	if len(dTrans) > 0:
#		dImpl['_reader']['_translate'] = dTrans


#	# Cache control information (internal)

#	# This is hard locked for now to just be time
#	# in the future support looking this up, say for example
#	# ['lat','long']
#	# ['time','freq']
#	lCacheCoords = ['time']
#	dRawLvls = self.getCacheLevels()
#	if len(dRawLvls) > 0:
#		if 'time' not in dSrc['COORDINATES']:
#			raise errors.ServerError(
#				"Time based cache blocks defined for non-time datasource"
#			)

#		dCachInCoords = {'_block_by':lCacheCoords}
#		dLvls = {}
#		for sKey in dRawLvls:
#			dLvls[sKey] = {
#				'_resolution':dRawLvls[sKey][0],
#				'_units':dRawLvls[sKey][1],
#				'_scheme':dRawLvls[sKey][2]
#			}
#			if dRawLvls[sKey][3]:
#				dLvls[sKey]['_reader_args'] = dRawLvls[sKey][3]

#		dCachInCoords['_lines'] = dLvls
#		dImpl['_cache'] = dCachInCoords

#	# Security authorization

#	if 'readAccess' in self.d:
#		dAuth = {'_dsdf_compat':self.d['readAccess']}
#		if 'securityRealm' in self.d:
#			dAuth['_realm'] = self.d['securityRealm']

#		lMethods = [s.strip() for s in self.d['readAccess'].split('|')]
#		if len(lMethods) > 0:
#			lMethOut = []
#			for i in range(0, len(lMethods)):

#				lMeth = [s.strip() for s in lMethods[i].split(':')]
#				#fLog.write("DEBUG: auth methods %s"%lMeth)
#				if len(lMeth) < 2:
#					raise errors.ServerError(
#						"Syntax error in readAccess key value"
#					)

#				sCheckType = lMeth[0].upper().strip()

#				lMethOut.append({'_check':sCheckType, '_values': lMeth[1:]})

#			dAuth['_methods'] = lMethOut
#			dImpl['_authorization'] = dAuth


#	dImpl['_local_id'] = self.sName
#	dImpl['_local_path'] = self.sPath

#	return dImpl

##############################################################################

def _findDsdfNoCase(sRoot, sDsdf, fLog):
	"""Look up dsdf files using a case sensitive root and a case insensitive
	remaning path.  If sDsdf doesn't end in .dsdf, that string is appended 
	"""

	if not sDsdf.endswith('.dsdf'):
		sDsdf = "%s.dsdf"%sDsdf

	if not os.path.isdir(sRoot): return (None,None)

	lIn = sDsdf.split('/')
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

def _loadDsdf(dConf, sDsdf, fLog):
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

		# New for v2.3, allow dataset IDs to be case insensitive
		(sName, sPath) = _findDsdfNoCase(dConf['DSDF_ROOT'], sDsdf, fLog);
		if sPath == None:
			raise errors.QueryError(u"Data source %s doesn't exist on this server"%sDsdf)

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


##############################################################################
def _mergeContacts(dOut, dProps):
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
	

def _mergeColCoordInfo(dOut, dProps):
	dCoords = _getDict(dOut, 'coordinates')
	
	# By default das2/2.2 servers only know that there is a time coordinate
	# so set that one up.  
	dTime = _getDict(dCoords, 'time')
	
	if 'name' not in dTime: dTime['name']  = 'Time'
		
	if 'validRange' in dProps:
		lRng = [ s.strip() for s in dProps['validRange']['00'].split('to') ]
		if len(lRng) > 1:
			dTime['valid_min'] = lRng[0]
			dTime['valid_max'] = lRng[1]

				
	# See if any other coordinates are mentioned, if so give them a 
	# token entry assume the values are 'name','description','units'
	if 'coord' in dProps:
		for sNum in dProps['coord']:
			lItem = [s.strip() for s in dProps['coord'][sNum].split('|')]
			if lItem[0].lower() == 'time':
				if len(lItem) > 1:  dTime['title'] = lItem[1]
			else:
				dVar = _getDict(dCoords, lItem[0])
				dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
				if len(lItem) > 1: dVar['title'] = lItem[1]
				if len(lItem) > 2: dVar['units'] = lItem[2]
	

def _mergeSrcCoordInfo(dOut, dProps):
	"""Add COORDs info to the output dictionary.  There are two styles,
	complete - used for actual HttpStreamSrc entries
	overview - used for collection entries
	"""
	dIface  = _getDict(dOut, 'interface')
	dCoords = _getDict(dIface, 'coordinates')
	
	# By default das2/2.2 servers only know that there is a time coordinate
	# so set that one up.  
	dTime = _getDict(dCoords, 'time')
	
	if 'name' not in dTime: dTime['name']  = 'Time'

	# Use the lowest numbered example for the default range, interval
	dTime['minimum'] = {sV:None}
	dTime['maximum'] = {sV:None}
	
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
			print("Error updating from %s"%dOut['path'])
			
		dTime['interval'][sV] = dProps['exampleInterval'][sNum]
	else:	
		# Default to 1/2000th of the range, here's where we need the
		# das2 module.
		if dTime['minimum'][sV] and dTime['maximum'][sV]:
			dtBeg = das2.DasTime(dTime['minimum'][sV])
			dtEnd = das2.DasTime(dTime['maximum'][sV])
			dTime['resolution'][sV] = (dtEnd - dtBeg) / 2000.0
				
	# Set up the alteration rules
	dTime['minimum']['set'] = {'param':'start_time', 'required':True}
	dTime['maximum']['set'] = {'param':'end_time', 'required':True}
	
	if 'validRange' in dProps:
		lTimeRng = [ s.strip() for s in dProps['validRange']['00'].split('to') ]
		if len(lTimeRng) > 1:
			dTime['minimum']['set']['range'] = lTimeRng
			dTime['maximum']['set']['range'] = lTimeRng
	
	if 'interval' in dTime:
		dTime['interval']['set'] = {'param':'interval', 'required':True}
	else:
		dTime['resolution']['set'] = {'param':'resolution', 'required':False}
		
	
	# See if any other coordinates are mentioned, if so give them a 
	# token entry assume the values are 'name','description','units'
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


def _mergeColDataInfo(dOut, dProps):

	if ('item' not in dProps) and ('data' not in dProps): return
	
	# Make minimal entries for the data items
	dData = _getDict(dOut, 'data')
	if 'item' in dProps:
		for sNum in dProps['item']:
			lItem = [s.strip() for s in dProps['item'][sNum].split('|')]
			
			dVar = _getDict(dData, lItem[0])
			dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
			if len(lItem) > 1: dVar['title'] = lItem[1]
			if len(lItem) > 2: dVar['units'] = {'value':lItem[2]}
		
	if 'data' in dProps:
		for sNum in dProps['data']:
			lItem = [s.strip() for s in dProps['data'][sNum].split('|')]
		
			dVar = _getDict(dData, lItem[0])
			dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
			if len(lItem) > 1: dVar['title'] = lItem[1]
			if len(lItem) > 2: dVar['units'] = {'value':lItem[2]}
	

def _mergeSrcDataInfo(dOut, dProps):

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


def _mergeDas2Params(dOut, dProps):
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
	
	dProto = _getDict(dOut, 'protocol')
	dGet = dProto['http_params']
	
	lNums = list(dProps['param'])
	lNums.sort()
	
	if bFlagSet:
		dFlags = {}
		dGet['params'] = {
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

		dGet['params'] = {
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
	
	if dGet['params']['type'] == 'string':
		dOpt = _getDict(dOpts, 'extra')
		dOpt['value'] = ''
		
		if 'exampleParams' in dProps:
			for sNum in lNums:
				if sNum in dProps['exampleParams']:
					dOpt['value'] = dProps['exampleParams'][sNum]
				break # Only take the first one since that's what's used for the
				      # example time.  We want the entire example to hang together
				
		dOpt['set'] = {'param':'params'}
		dOpt['name'] = 'Extra Reader Parameters'
		if 'description' in dGet['params']:
			dOpt['description'] = dGet['params']['description']
		
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
				dOpt['set'] = {'param':'params', 'flag':sFlag}
						
			else:
				dOpt['type'] = 'boolean'
				dOpt['value'] = False
				dOpt['set'] = {'value':True, 'param':'params', 'flag':sFlag}
				
	# If we want to do this as an enum this it would look like:
	#
	#    "units":{
	#    "value":"V/m",
	#    "set":{
	#    	"param":"params",
	#    	"map":[
	#    		{"value":"raw", "flag":"--units=DN"},
	#    		{"value":"V**2 m**-2 Hz**-1", "flag":"--units=SD"},
	#    		{"value":"W m**-2 Hz**-1", "flag":"--units=PF"}
	#    	]
	#    }	
						
	
def _mergeExamples(dOut, dProps, sBaseUrl):
	# A das 2.1 example looks like:
	#
	#   "QUERY":{
	#      "end_time":   (required)
	#      "params":     (optional)
	#      "resolution": (present if interval missing)
	#      "interval":   (optional)
	#      "start_time": (required)
	#   }
	#   "name": (required)
	#   "title" (optional)
	#   "URL":  (required)
	
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
		dExample = {"http_params":dQuery}
		sId = "example_%s"%sNum
		dExample['name'] = "Example %s"%sNum
			
		lTmp = [s.strip() for s in dProps['exampleRange'][sNum].split('|')]
		if len(lTmp) > 1:
			dExample['title'] = lTmp[1]
			
		lTmp = [s.strip() for s in lTmp[0].split('to')]
		
		if len(lTmp) < 2: continue  # Invalid range string
			
		sBeg = lTmp[0]
		sEnd = lTmp[1].replace('UTC','').strip()
		dQuery['start_time'] = sBeg
		dQuery['end_time']   = sEnd
			
		# See if we need resolution or interval
		if sNum in lInterval:
			dQuery['interval'] = dProps['exampleInterval'][sNum]
		else:
			# Default to 1/2000th of the range, here's where we need the
			# das2 module.
			dtBeg = das2.DasTime(sBeg)
			dtEnd = das2.DasTime(sEnd)
			dQuery['resolution'] = (dtEnd - dtBeg) / 2000.0
			
		if sNum in lParams:
			dQuery['params'] = dProps['exampleParams'][sNum]
		
		lQuery = [
			"%s=%s"%(sKey, quote_plus(str(dQuery[sKey])))
			for sKey in dQuery
		]
		
		dExample['url'] = "%s&%s"%(sBaseUrl, '&'.join(lQuery))
		
		# TODO: Merge in examples from the DSDFs with hand entered ones
		dExamples[sId] = dExample
		
	if len(dExamples) > 0:
		dProto = _getDict(dOut, 'protocol')
		dProto['examples'] = dExamples
	

def _mergeFormat(dOut, dProps):

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
	elif _isPropTrue(dProps, 'das2Stream'):
		dDefFmt =  {
			"name":"das2 binary",
			"title":"das2 binary stream, application/vnd.das2.das2stream (*.d2s)",
			"mime":"application/vnd.das2.das2stream",
			"extension":".d2s",
			"enabled":{"value":True},
		}
	else:
		dDefFmt =  {
			"name":"das1 binary",
			"mime":"application/octet-stream",
			"title":"das1 binary stream, application/octet-stream (*.bin)",
			"extension":".bin",
			"enabled":{"value":True},
		}

	dOut['interface']['format'] = {'default':dDefFmt}


# ########################################################################## #

def fromDsdf(dConf, sDsdf, sBaseUrl, fLog, bInternal=False):
	"""Create an HttpStreamSrc object from a DSDF file and the given server
	configuration information.

	If bInternal is true, an aditional top level section named:

			"internal"

	is added to the dictionary which contains stuff like cache levels
	sub sources, and various commandlines.

	Output make assumptions about the query parameter interface of the 
	server and format conversion capabilities.

	Todo: Add overrides for adjacent *.json file.

	Throws:
		QueryError if dsdf doesn't exist
		RemoteServer if dsdf is for someone else
		ServerError if there is a syntax error or other misconfiguration
	"""
	
	(sName, sPath) = _findDsdfNoCase(dConf['DSDF_ROOT'], sDsdf, fLog);
	if sPath == None:
		raise errors.QueryError(u"Data source %s doesn't exist on this server"%sDsdf)

	dProps = _loadDsdf(dConf, sDsdf, fLog)

	# Check to see if this is some other server's problem
	if 'server' in dProps and '00' in dProps['server']:
		sRmt = dProps['server']['00']
		if sRmt.strip('/') != webio.getScriptUrl().strip('/'):
			raise errors.RemoteServer("Source is for server %s not this one"%sRmt)
	
	# TODO: Could merge in json data from disk here, but skip it for now...
	dOut = {}

	#sCustom = sDsdf.replace('.dsdf','.json')
	#if sDsdf.endswith('.dsdf') and os.path.isfile(sCustom) :
	#	fIn = open(dNode['filename'])
	#	dOut = json.load(fIn)
	#	fIn.close()

	# End load custom settings

	# The disk entries may have been hand edited.  Don't override the name and
	# description, go ahead and smash the type and path
	if 'name' not in dOut: dOut['name'] = dProps['__name__']
	if 'title' not in dOut and 'description' in dProps: 
		dOut["title"] = dProps['description']['00']
	dOut['type'] = 'HttpStreamSrc'
	dOut['version'] = "0.6"
	dProto = _getDict(dOut, 'protocol')
	dProto['convention'] = 'das2/2.3'

	
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
		
		
	_mergeContacts(dOut, dProps)
	
	_mergeSrcCoordInfo(dOut, dProps)
	
	_mergeSrcDataInfo(dOut, dProps)
	
	_mergeFormat(dOut, dProps)   # Just the format for now, but hand edited
	                             # items could be in there
	
	# Make sure this base url is included
	lUrls = _getList(dProto, 'base_urls')
	lUrls.clear()
	lUrls = [sBaseUrl]
		
	if 'securityRealm' in dProps:
		dProto['authentication'] = {
			'required':True, 'realm':dProps['securityRealm']['00']
		}
	else:
		dProto['authentication'] = {'required':False}
	
	dGet = {}
	dProto['http_params'] = dGet
	
	dGet['start_time'] = {
		'required':True, 'type':'isotime',
		'name':'Min Time', 'title':'Minimum time value to stream',
	}
		
	dGet['end_time'] = {
		'required':True, 'type':'isotime',
		'name':'Max Time', 'title':'Maximum Time Value to stream',
	}
	
	# See if requires interval is set, if not
	if _isPropTrue(dProps, 'requiresInterval'):
		dGet['interval'] = {
			'required':True, 'type':'real', 'units':'s',
			'name':'Interval', 
			'title':'Time interval between model calculations/interpolations',
			'description': 'This parameter is used with data generated from models '
			        'or table interpolations such as SPICE Ephemerides and '
					  'magnetic field models',
		}

	else:
		dGet['resolution'] = {
			'required':False, 'type':'real', 'units':'s',
			'name':'Resolution', 
			'title':'Maximum resolution between output time points',
			'description':'The server will return data at or better than the given '
                'resolution if possible.  Leave un-specified to get data '
			       'at intrinsic resolution without server side averages',
		}

		
	# See if there is any sign of this source supporting extra parameters
	# this could come from having a param or exampleParams
	_mergeDas2Params(dOut, dProps)
		
	# Could ask server if text output is supported, old servers don't 
	# have a way to do this.
	_mergeExamples(dOut, dProps, sBaseUrl)

	return dOut