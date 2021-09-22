"""General Utilities for working with DSDF files

Much of this functionality should be moved to a streamsource file
"""
# make py2 code safer by preventing relative imports
from __future__ import absolute_import

import codecs
import os
import os.path
import re
import sys
import time
import urllib

from os.path import join as pjoin
from os.path import basename as bname

from urllib.parse import quote_plus
from urllib.parse import unquote_plus
from urllib.parse import urlencode
	
import das2

from . import webio
from . import errors

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')


##############################################################################
def readDsdf(fIn, fLog):
	"""Pass an open file handle in, get a dictionary out.
	Use codecs.open to read unicode files, and end a unicode string for the
	comment character.

	Throws ValueError with a line number if there is a syntax problem in
	the file.
	"""

	# custom config reader, can improve with a lib later if someone wants to
	lLines = fIn.readlines()
	#fLog.write("   TRACE: %s"%lLines)

	dConf = {}
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

		dConf[sKey] = sVal

	return dConf

###########################################################################

def escSplitStr(sArg, sSep, cEsc):

	if not sSep or len(sSep) == 0:
		raise ValueError("Empty separator string in splitArg")

	if len(cEsc) != 1:
		raise ValueError("Escape pattern must be a one character string, received '%s'"%cEsc)

	nSz = len(sSep)
	lOut = []
	lItem = []

	bEscape = False
	i = 0
	while i < len(sArg):

		if bEscape:
			lItem.append(sArg[i])
			bEscape = False
			i += 1

		elif sArg[i] == cEsc:
			bEscape = True
			i += 1

		elif sArg[i:i+nSz] == sSep:
			lOut.append( ''.join(lItem) )
			lItem = []
			i += nSz
		else:
			lItem.append(sArg[i])
			i += 1

	lOut.append( ''.join(lItem) )

	return [s.strip() for s in lOut]

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

class Dsdf(object):
	"""Represents a Data Source Definition File as a memory object"""

	###########################################################################
	def __init__(self, sDsdf, dConf, form, fLog):
		"""Parses DSDF lines into a dictionary of UTF-8 strings, also handles
		any keyword substitutions required.

		Read each value looking for $(variable).  If $(variable) is found then
		a substitution attempted, in this order:

		  1. If the variable is THIS_FILE, sub in the complete path to the DSDF
		     file that is being read.

		  2. Try to match any other keyword in the dsdf itself

		  3. Try to match any keyword from the client request

		  4. Try to match any value from the server configuration file

		  5. Substitute in the default value if any is provided

		  7. Fail to parse the DSDF

		If none of these substitutions works, an unresolved variable error is
		issued.

		Use of the make syntax for variables rather than the bash/php syntax
		make parsing easier (for me anyway)

		WARNING: Variable subtitutions are preformed in arbitary order, not
		         top down as with make and similar tools.
		"""

		# Do not alter this, it is read only for checking boolean values
		self.lTrue = ['1',u'1','true',u'true']
		self.lFalse = ['0',u'0','false',u'false']

		#self.lExTimes = None
		#self.lExIntervals = None
		self.lExamples = None
		self.lValidTimes = None
		self.dSubSource = None

		ptrn = re.compile('\$\(.*\)')

		# New for v2.3, allow dataset IDs to be case insensitive
		(self.sName, self.sPath) = _findDsdfNoCase(dConf['DSDF_ROOT'], sDsdf, fLog);
		if self.sPath == None:
			raise errors.QueryError(u"Data source %s doesn't exist on this server"%sDsdf)

		fLog.write("   Reading: %s"%self.sPath)

		fIn = open(self.sPath, encoding='UTF-8')

		try:
			self.d = readDsdf(fIn, fLog)
		except ValueError as e:
			raise errors.ServerError(str(e))

		fIn.close()

		if len(self.d) == 0:
			raise ServerError("Data source file is empty")

		lDsdfKeys = list(self.d.keys())

		# Note that Variables can appear right in the middle of a value string,
		# so we have to replace just those parts of the string with the variable
		# value, and then return the complete DSDF value with all substitutions
		# in place.

		bRunAgain = True
		if ('substitutions' in self.d) and (self.d['substitutions'] in self.lFalse):
			bRunAgain = False


		nPass = 0
		while bRunAgain and nPass < 50:
			bRunAgain = False
			for sKey in lDsdfKeys:
				lVars = ptrn.findall(self.d[sKey])
				for sVar in lVars:
					if len(sVar) == 3:
						raise errors.ServerError(
							"Error in DSDF file %s. The value for"%sDsdf+\
							" keyword %s contains an invalid"%sKey+\
							" substitution, '%s'"%sVar
						)

					sVarName = sVar[2:-1]
					sDefVal = None

					if sVarName.find(',') != -1:
						lTmp = sVarName.split(',')
						sVarName = lTmp[0]
						sDefVal = ','.join(lTmp[1:])

					if sVarName == 'THIS_FILE':
						self.d[sKey] = self.d[sKey].replace(sVar, self.sPath)

					elif sVarName in lDsdfKeys:
						self.d[sKey] = self.d[sKey].replace(sVar, self.d[sVarName])

					elif form != None and sVarName.lower() in form.keys():
						self.d[sKey] = self.d[sKey].replace(sVar, form.getfirst(sVarName.lower(), ''))

					elif sVarName in dConf.keys():
						self.d[sKey] = self.d[sKey].replace(sVar, dConf[sVarName])

					elif sDefVal != None:
						self.d[sKey] = self.d[sKey].replace(sVar, sDefVal)

					else:
						raise errors.ServerError(
							"Error in DSDF file %s, can't determine the"%sDsdf+\
							" value for variable %s in the string for"%sVar+\
							" keyword %s"%sKey
						)

				# Now that all the subtitutions have been run, see if secondary
				# replacements are needed.
				lVars = ptrn.findall(self.d[sKey])
				if len(lVars) > 0:
					bRunAgain = True

			nPass += 1

		if nPass >= 50:
			raise errors.ServerError(
				"Error in DSDF file %s, un-resolved subtitution "+sDsdf+\
				"variables remain after 50 passes"
			)

		# Add in the local ID
		self.d['name'] = self.sName


	##############################################################################

	def isTrue(self, sStr):
		"""Find out if an entry in a dsdf dictionary has the value 'true',
		Missing entries are automatically assigned the value 'false'
		"""
		if sStr not in self.d:
			return False

		#sys.stderr.write("True check: %s = %s"%(sStr, self.d[sStr]))
		if isinstance(self.d[sStr], str):
			return self.d[sStr].lower() in self.lTrue
		else:
			return self.d[sStr]


	##############################################################################
	def getCacheLevels(self):
		"""Parse the cache levels tags, and return a dictonary of 4-tuples:

		The dictionary keys are the cache level (0, 1, 4, ...)

		and the keys are:

		 (resolution (float seconds), units(string), store_method(string), params(string))

		For instrinsic resolution caches, the resolution will be 0 and the units
		will be  NONE.  If no parameters are given in the DSDF then params will
		be the None object.

		Note that the params string is *NOT* normalized.  If a normalized params
		string is needed used the normalizeParams function below.
		"""

		lKeys = list(self.d.keys())
		lKeys.sort()

		dOut = {}

		for sKey in lKeys:

			lKeyWord = sKey.split('_')

			if lKeyWord[0] != 'cacheLevel':
				continue

			if len(lKeyWord) == 1:
				nLevel = 0
			elif len(lKeyWord) == 2:
				try:
					nLevel = int(lKeyWord[1], 10)
				except ValueError as e:
					raise errors.ServerError(str(e))
			else:
				raise errors.ServerError("Invalid Keyword: %s"%sKey)

			sVal = self.d[sKey]

			lItems = [s.strip() for s in sVal.split('|') ]

			if len(lItems) < 2:
				raise errors.ServerError("Missing information in DSDF keyword %s"%sKey)
			if len(lItems) > 3:
				raise errors.ServerError("Extra information in DSDF keyword %s"%sKey)

			if lItems[0] == 'intrinsic':
				rRes = 0
				sUnits = None
			else:
				lDatum = lItems[0].split()
				if len(lDatum) != 2:
					raise errors.ServerError(
						"Poorly formed datum, '%s', "%lItems[0] +\
						" in value for DSDF keyword %s"%sKey
					)
				try:
					rRes = float(lDatum[0])
				except ValueError as e:
					raise errors.ServerError(
						"Can't convert resolution %s to an integer"%lDatum[0]
					)
				sUnits = lDatum[1]

				# Normalize seconds and milliseconds units
				if sUnits in ('sec','seconds','second'):
					sUnits = 's'
				elif sUnits in ('millisec', 'millsecond','milliseconds'):
					sUnits = 'ms'

			sStore = lItems[1]

			sParam = None
			if len(lItems) > 2 and len(lItems[2]) > 0:
				sParam = lItems[2]

			dOut[nLevel] = (rRes, sUnits, sStore, sParam)

		return dOut

	###########################################################################
	def fillDefaults(self, dConf):
		"""Check a raw DSDF file, fill Default values and store some entries
		as python types.

		The following DSDF key values are converted:

		das2Stream  -> boolean
		qstream     -> boolean
		requiresInterval -> boolean
		reducer -> None, or a program name
		cacheLevel -> A dictionary object with integer keys, may be empty
		subSource -> A dictionary object with string keys, may be empty

		Items which have no entry in the dsdf are assigned a default.

		Required Items are checked, an improper DSDF file can cause a
		ServerError exception to be thrown.

		The following legacy items are handled:

		   1. If the DSDF represents a Das 1 data set, the reader entry is
			   replaced with a command to up-convert to Das2.

			2. If the old 'groupAccess' keyword is present it is replaced
			   with the 'readAccess' entry.
		"""

		# The reader argument is ALWAYS required
		if u'reader' not in self.d:
			raise errors.ServerError(
				u"'reader' keyword is not present in %s"%self.sName
			)

		# Make sure the stream-type keys are specified
		if u'das2Stream' not in self.d:
			self.d[u'das2Stream'] = False

		if u'qstream' not in  self.d:
			self.d[u'qstream'] = False

		# Re-write the reader value for das1 streams to make them das2 streams
		# and set the interval required parameter if 'items' is present
		if not self.d[u'das2Stream'] and not self.d[u'qstream']:
			if 'DAS1_TO_DAS2' in dConf:
				sDas1ToDas2 = dConf['DAS1_TO_DAS2']
			else:
				sDas1ToDas2 = 'das2_from_das1'
			self.d[u'reader'] = u'%s %s%s%s.dsdf'%(sDas1ToDas2, dConf['DSDF_ROOT'],
			                                      os.sep, self.sName)
			self.d[u'das2Stream'] == True

			# Trigger off of the items tag to set a flag saying the reader resolution
			# is a required parameter
			if u'items' in self.d:
				self.d[u'requiresInterval'] = True
		else:
			self.d[u'requiresInterval'] = self.isTrue(u'requiresInterval')

		# Re-write the groupAccess key to the current form, if no entry in the
		# current form is present
		if u'groupAccess' in self.d and u'readAccess' not in self.d:
			self.d[u'readAccess'] = u'GROUP:%s'%self.d[u'groupAccess']

		# Make sure that a default security realm is always included
		if u'securityRealm' not in self.d and 'SECURITY_REALM' not in dConf:
			self.d[u'securityRealm'] = '%s/%s'%(os.getenv('SCRIPT_NAME'), self.sName)

		# If no reducer has been specified, fill in a default
		if u'reducer' not in self.d:

			sDefQreduce = None
			if 'QDS_REDUCER' in dConf:
				sDefQreduce = dConf['QDS_REDUCER']

			sDefReduce = 'das2_bin_avgsec'
			if 'D2S_REDUCER' in dConf:
				sDefReduce = dConf['D2S_REDUCER']

			if self.d[u'qstream']:
				self.d[u'reducer'] = sDefQreduce
			else:
				self.d[u'reducer'] = sDefReduce

		if u'requiresInterval' not in self.d:
			self.d[u'requiresInterval'] = True

		# Set the cache levels
		try:
			self.d['cacheLevel'] = self.getCacheLevels()
		except ValueError as e:
			raise errors.ServerError(
				u"Misconfigured Data Source %s: %s"%(self.sName, str(e))
			)

		# Set a default cache reader if none was provided
		if u'cacheReader' not in self.d:
			sDefCacheRdr = 'das2_cache_rdr'

			if self.d[u'qstream']:
				if 'QDS_CACHE_RDR' in dConf:
					sDefCacheRdr = dConf['QDS_CACHE_RDR']
			else:
				if 'D2S_CACHE_RDR' in dConf:
					sDefCacheRdr = dConf['D2S_CACHE_RDR']

			self.d[u'cacheReader'] = sDefCacheRdr

	###########################################################################
	def getExamples(self, fLog, sBaseUrl=None, bDas23=False):
		"""Returns a list of examples.  Each one has a set of all the get
		parameters that need to be specifed for the example

		If bDas23 is True then it means this interface uses command translation
		and that exampleOpts_00 should be used instead of example params

		Note! sBaseURL must end with the separator, since this can be '/' or '&'


		"""

		# We are still working off the old DSDF inputs, so for now just
		# assume that examples are specified for time only.  This will get
		# fixed when we go to toml files
		if self.lExamples != None:
			return self.lExamples

		self.lExamples = []
		# This model is extreamly broken, but support it since that's what
		# many DSDFs have in them right now
		lKeys = []
		for sKey in self.d:
			if not sKey.startswith('exampleRange'):
				continue
			else:
				lKeys.append(sKey)
		lKeys.sort()

		for sKey in lKeys:
			dParams = {}
			dExample = {'http_params':dParams}
			lVal = escSplitStr(self.d[sKey], '|', '\\')
			sRng = lVal[0]
			if len(lVal) > 1:
				dExample['title'] = lVal[1].strip()
			sRng = sRng.replace('UTC','')
			lRng = [x.strip() for x in sRng.split('to')]
			if len(lRng) != 2:
				raise errors.ServerError(
					u"Datasource %s, key %s has an invalid value"%(
					self.sName, key
				))

			if bDas23:
				dParams['time.min'] = lRng[0]
				dParams['time.max'] = lRng[1]
			else:
				dParams['start_time'] = lRng[0]
				dParams['end_time'] = lRng[1]

			if bDas23:
				sInfoKey = sKey.replace('exampleRange','exampleInfo')
				if sInfoKey in self.d:
					dExample['title'] = self.d[sInfoKey]
			
			sIntKey = sKey.replace('exampleRange','exampleInterval')

			if sIntKey in self.d:
				if bDas23:
					dParams['time.int'] = self.d[sIntKey]
				else:
					dParams['interval'] = self.d[sIntKey]

			if not bDas23:
				sParamKey = sKey.replace('exampleRange','exampleParams')
				if sParamKey in self.d:
					dParams['params'] = self.d[sParamKey]
			else:
				# For das 2.3 prefer exampleQuery_, but fall back to example params
				sParamKey = sKey.replace('exampleRange','exampleQuery')
				if sParamKey in self.d:
					lPairs = [x.strip() for x in self.d[sParamKey].split('|')]
					for pair in lPairs:
						l = [x.strip() for x in pair.split('=')]
						if len(l) != 2:
							raise errors.ServerError(
								"Datasource %s, key %s malformed GET query pair"%(
								self.sName, key
							))
						dParams[l[0]] = l[1]
				else:
					sParamKey = sKey.replace('exampleRange','exampleParams')
					if sParamKey in self.d:
						dParams['params'] = self.d[sParamKey]


			# Resolution is handled a bit diferently  First if a key is
			# set just use it, though this is rare
			sResKey = sKey.replace('exampleRange','exampleResolution')
			if sResKey in self.d:
				if bDas23:
					dParams['time.res'] = self.d[sResKey]
				else:
					dParams['resolution'] = self.d[sResKey]

			elif ('time.int' not in dParams) and ('interval' not in dParams):
				fLog.write("%s\n"%dParams.keys())
				rSec = das2.DasTime(lRng[1].encode('ascii')) - \
			   	    das2.DasTime(lRng[0].encode('ascii'))
				if bDas23:
					dParams['time.res'] = (rSec / 2000)
				else:
					dParams['resolution'] = (rSec / 2000)

			# If the base URL is set, then provide a complete url for the example
			if sBaseUrl:
				if sBaseUrl.find('?') == -1:
					sFmt = "%s%s?%s"
				else:
					sFmt = "%s%s&%s"
				dExample['URL'] = sFmt%(
					   sBaseUrl, self.sName, urlencode(dParams)
				)
			self.lExamples.append(dExample)

		return self.lExamples

	###########################################################################
	def getValidTimeRange(self, fLog):
		"""Returns the valid time range if present in the DSDF, or 1977 to
		now otherwise
		"""

		if 'validRange' in self.d:
			sVal = self.d['validRange']
			sVal = sVal.replace('UTC','')
			lTmp = [x.strip() for x in sVal.split('to') ]

			if len(lTmp) > 1:
				if lTmp[1].strip().lower() == 'now':
					nTomorrow = time.time() + 60*60*24
					lTmp[1] = "%04d-%02d-%02d"%tuple(time.gmtime(nTomorrow)[:3])

				return lTmp

		nTomorrow = time.time() + 60*60*24
		tTomorrow = time.gmtime(nTomorrow)[:3]
		return ('1977-01-01', '%04d-%02d-%02d'%tuple(tTomorrow))

	###########################################################################
	def trimToValidRange(self, fLog, sBeg, sEnd):
		"""Returns altered sBeg and sEnd if these are outside the valid range for
		this dsdf
		"""
		if 'validRange' not in self.d:
			return (sBeg, sEnd)

		dtBeg = das2.DasTime(sBeg)
		dtEnd = das2.DasTime(sEnd)

		lVal = [das2.DasTime(s) for s in self.getValidTimeRange(fLog) ]

		# You can move the start later, but you can't move it earlier
		sRetBeg = sBeg
		if dtBeg < lVal[0]:
			dtBeg = lVal[0]
			sRetBeg = str(dtBeg)

		# You can move the end earlier, but you can't move it later
		sRetEnd = sEnd
		if dtEnd > lVal[1]:
			dtEnd = lVal[1]
			sRetEnd = str(dtEnd)

		if dtEnd <= dtBeg:
			return (None, None)
		else:
			return (sRetBeg, sRetEnd)

	###########################################################################
	# Get Sub-data source by name
	def subSource(self, sKey):
		"""Return a 3-item list containing the following items:


		  [ Description of this Sub-Source | Resolution or Interval | Extra parameters ]

		The description is always present.  For interval based data sourcs the
		interval must be defined, for resolution based sources it defaults to 0.0.
		The extra parameters are always optional

		  [ Always Present | Default 0.0 | Optional ]

		For readers with intervalRequired specified then the 2nd item (index 1)
		is an interval, otherwise it is a resolution.  For non-model output
		the second item is the resolutions, 0.0 is taken to be intrinsic resolution.

		If no sub-source with key sKey has been defined, None is returned
		"""

		if self.dSubSource is None:
			self.dSubSource = {}
			for key in self.d:
				if key.startswith('subSource'):
					l = [s.strip() for s in self.d[key].split('|')]
					if len(l) <2:
						raise errors.ServerError(
							u"At least a key and description need to be provided for %s"%key
						)

					if len(l) == 2:
						self.dSubSource[l[0]] = [ l[1].strip(), '', '']
					elif len(l) == 3:
						self.dSubSource[l[0]] = [ l[1].strip(), l[2].strip(), '']
					elif len(l) > 3:
						self.dSubSource[l[0]] = [ s.strip() for s in l[1:4] ]

					lSrc = self.dSubSource[l[0]]

					# Set interval to 0.0 if empty and we don't require an interval
					if len(lSrc) == 0:
						if self.isTrue(u'requiresInterval'):
							raise errors.ServerError(
								u"Error in key %s, resolution cannot be"%key+\
								u" 0 for interval based readers"
							)
						lSrc[1] = 0.0
					else:
						try:
							lSrc[1] = float(lSrc[1])
						except ValueError:
							raise errors.ServerError(
								u"Float conversion error for the resolution "
								"value %s in DSDF key %s"%(lSrc[1], key)
							)
						if lSrc[1] < 0.0:
							raise errors.ServerError(
								u"Resolution value <= 0.0 for DSDF key %s"%key
							)

						if (lSrc[1] == 0.0) and self.isTrue(u'requiresInterval'):
							raise errors.ServerError(
								u"Interval can not be 0.0 for DSDF key %s"%key
							)

		if sKey in self.dSubSource:
			return self.dSubSource[sKey]
		else:
			return None

	###########################################################################
	def canReduceInTime(self, dConf):
		if 'requiresInterval' in self.d:
			return False

		if 'reducer' in self.d:
			if self.d['reducer'] in ('not_reducable','not_reducible'):
				return False
			else:
				return True

		if 'reducerCmd' in self.d:
			return True

		if 'qstream' in self.d:
			if 'QDS_REDUCER' in dConf:
				return True
		else:
			if 'D2S_REDUCER' in dConf:
				return True

		return False

	###########################################################################
	# Reflect some dictonary functions to the internal dictionary

	def __getitem__(self, key):
		return dict.__getitem__(self.d, key)

	def __contains__(self, key):
		return dict.__contains__(self.d, key)

	def keys(self):
		return self.d.keys()

##############################################################################

def _sourceGetParamDictHelper(dParams, dRet, sPrefix=None):
	"""Walk the parameters tree and return a dictionary of:

	   full.key.name : definition

	This should be a function member of a DataSource object

	The param dictionary is returned in dRet since this function call is
	recursive
	"""
	for sParam in dParams:
		sTmp = sParam
		if sPrefix:
			sTmp = "%s.%s"%(sPrefix, sParam)

		if 'TYPE' in dParams[sParam]:
			dRet[sTmp] = dParams[sParam]
		else:
			#U.webio.serverError(fLog, u"DEBUG: sub params are %s"%dParams[sParam].keys())
			#return None
			_sourceGetParamDictHelper(dParams[sParam], dRet, sParam)

	return


def sourceGetParamDict(dSrc):
	"""TODO: Make part of source class

	Given a source get a flattened dictionary of all query parameters
	"""
	if 'QUERY_PARAMS' not in dSrc:
		raise errors.ServerError(
			"Required section QUERY_PARAMS missing in data source object"
		)

	dQuerySection = dSrc['QUERY_PARAMS']

	dParams = {}
	for sBlock in dQuerySection:
		_sourceGetParamDictHelper(dQuerySection[sBlock], dParams)

	return dParams


##############################################################################
def normalizeParams(sParams):
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
def checkParam(fLog, sKey, sValue):
	"""Check the parameter values for obvious shell injection stuff such as
	pipes, redirects, ../ directories, etc"""

	for sTest in [';', '|','../','..\\', ':\\', '>', '&']:
		if sValue.find(sTest) != -1:
			webio.queryError(
				fLog,
				"Illegal character(s): '%s', in value: '%s' for query parmeter: %s"%(
			   sTest, sValue, sKey)
			)
			return False

	return True

##############################################################################
def handleRedirect(fLog, sOldName, dsdf):

	bRedir = False

	# 1: Potentially get a new server path...
	sServer = webio.getScriptUrl()
	if sServer.endswith('/'):
		sServer = sServer[:-1]

	if u'server' in dsdf:
		sNewServer = dsdf[u'server']
		if sNewServer.endswith('/'):
			sNewServer = sNewServer[:-1]

		if sServer != sNewServer:
			fLog.write("   Data source moved to server %s"%sNewServer)
			sServer = sNewServer
			bRedir = True


	# 2: Potentially get a new query string
	sQuery = unquote_plus(os.getenv('QUERY_STRING'))
	if sQuery != None and u'rename' in dsdf:

		sNewQuery = sQuery.replace(sOldName, dsdf[u'rename'], 1)
		if sNewQuery != sQuery:
			fLog.write("   Data source moved to new query id %s"%sNewQuery)
			sQuery = sNewQuery
			bRedir = True


	# 3: Potentially get a new path
	sPath = os.getenv('PATH_INFO')
	if sPath != None and u'rename' in dsdf:

		sNewPath = sPath.replace(sOldName, dsdf[u'rename'], 1)
		if sPath != sNewPath:
			fLog.write("   Data source moved to a new path %s"%sNewPath)
			sPath = sNewPath
			bRedir = True

	if bRedir:
		if sPath:
			sRefer = "%s%s"%(sServer, sPath)
		else:
			sRefer = sServer
		if sQuery:
			sRefer = "%s?%s"%(sRefer, sQuery)

		fLog.write("   Redirecting client to: %s"%sRefer)

		pout("Status: 301 Permanently moved")
		pout("Location: %s\r\n"%sRefer)
	else:

		webio.serverError(fLog, "Dataset %s does not require redirection"%sOldName)
		return 17

	return 0
