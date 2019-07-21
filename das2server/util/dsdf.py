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

# Module moved in python3
try:
	from urllib import quote_plus
	from urllib import unquote_plus
except ImportError:
	from urllib.parse import quote_plus
	from urllib.parse import unquote_plus

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

		self.sName = sDsdf
		#self.lExTimes = None
		#self.lExIntervals = None
		self.lExamples = None
		self.lValidTimes = None
		self.dSubSource = None
		self.sPath = pjoin(dConf['DSDF_ROOT'], sDsdf)

		ptrn = re.compile('\$\(.*\)')

		# When looking up dsdf's, allow .dsdf to be missing
		if not os.path.isfile(self.sPath):
			self.sPath = self.sPath + '.dsdf'

		if not os.path.isfile(self.sPath):
			raise errors.QueryError(u"Data source %s doesn't exist on this server"%sDsdf)

		fLog.write("   Reading: %s"%self.sPath)

		fIn = codecs.open(self.sPath, 'rb', 'utf-8')

		try:
			self.d = readDsdf(fIn, fLog)
		except ValueError as e:
			raise errors.ServerError(str(e))

		fIn.close()

		if len(self.d) == 0:
			raise ServerError(u"Data source file is empty")

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
							" keyword"%sKey
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
			dExample = {'SETTINGS':dParams}
			lVal = escSplitStr(self.d[sKey], '|', '\\')
			sRng = lVal[0]
			if len(lVal) > 1:
				dExample['TITLE'] = lVal[1].strip()
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
					dExample['TITLE'] = self.d[sInfoKey]
			
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
					   sBaseUrl, self.sName, urllib.urlencode(dParams)
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
	def _getLinks(self, dConf, fLog):
		"""Return a dictionary of reference objects.  This walks the DSDF
		path up to top of the datasets and includes any upper level references
		as well.
		"""
		return []




	###########################################################################
	def _getDefTimeParams(self, fLog, sBaseUrl):
		"""Just returns an empty dictionary if this DSDF doesn't use default time
		parameters
		"""

		lExamples = self.getExamples(fLog, sBaseUrl)
		if len(lExamples) > 1:
			dEx = lExamples[-1]
		else:
			dEx = {'SETTINGS':{}}

		dParams = {}
		dMin = {
			'TITLE':'Minimum time value',
			'VAL_TYPE':'isotime',
			'REQUIRED':True
		}

		if 'time.min' in dEx['SETTINGS']:
			dMin['DEFAULT'] = dEx['SETTINGS']['time.min']

		dParams['min'] = dMin


		dMax = {
			'TITLE':'Maximum time value',
			'VAL_TYPE':'isotime',
			'REQUIRED':True
		}

		if 'time.max' in dEx['SETTINGS']:
			dMax['DEFAULT'] = dEx['SETTINGS']['time.max']

		dParams['max'] = dMax

		if 'requiresInterval' in self.d and \
		   self.d['requiresInterval'] in self.lTrue:

			dInt = {
				'TITLE':'Time Interval between points',
				'VAL_TYPE':'real',
				'UNITS':'s',
				'REQUIRED':True
			}
			if 'time.int' in dEx['SETTINGS']:
				dInt['DEFAULT'] = dEx['SETTINGS']['time.int']

			dParams['int'] = dInt

		elif ('reducer' in self.d and \
			   (self.d['reducer'] not in ('not_reducable','not_reducible'))) or \
			  ('reducer' not in self.d):

			dRes = {
				'TITLE':'Time Average Seconds',
				'VAL_TYPE':'real',
				'UNITS':'s',
				'REQUIRED':False
			}

			if 'time.res' in dEx['SETTINGS']:
				dRes['DEFAULT'] = dEx['SETTINGS']['time.res']

			dParams['res'] = dRes

		return dParams

	###########################################################################
	def _getContacts(self):
		"""Returns a list of contact dictionaries"""

		dContacts = {}
		for uKey in self.d:
			uVal = self.d[uKey]

			if not uKey.endswith(u'Contact'):
				continue

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
					uType = u'scientific'
				elif uKey == u'techContact':
					uType = u'technical'
				else:
					uType = u'other'

				dContact = {'PURPOSE':uType}
				if uEmail:
					dContact['EMAIL'] = uEmail
				dContacts[uWho] = dContact

		return dContacts


	###########################################################################
	def _getValInfo(self, fLog, nParam):
		"""Used by both Enum options and FlagSet options"""

		dInfo = {}

		sKey = 'paramValInfo_%s'%nParam
		if not (sKey in self.d):
			return dInfo

		lInfo = [s.strip() for s in escSplitStr(self.d[sKey], '|', '\\')]
		for sEntry in lInfo:
			n = sEntry.find(':')
			if n == -1:
				raise errors.ServerError(
					"Missing ':' in value description in paramValInfo_%s"%nParam
				)

			sValKey = sEntry[:n].strip()
			sValDesc = sEntry[n+1:].strip()
			if len(sValKey) == 0 or len(sValDesc) == 0:
				raise errors.ServerError(
					"Miss formed entry in paramValInfo_%s, %s"%(nParam, sEntry)
				)

			dInfo[sValKey] = sValDesc

		return dInfo

	###########################################################################
	def _getHttpGetOpts(self, fLog):
		"""Return the HTTP GET options for this data source, returns an empty
		dictionary if no options are present.  If bInternal is true extra
		options are returned that are useful when calling readers
		"""

		lKeys = list(self.d.keys())
		lKeys.sort()
		dOpts = {}
		for key in lKeys:
			if not key.startswith('param_'):
				continue

			nParam = key[-2:]

			lParam = [ s.strip() for s in escSplitStr(self.d[key], '|', '\\')]
			if len(lParam) < 4:
				fLog.write("Malformed value for keyword %s, "%key+\
				           "expected 4 sections minimum, found %d"%len(lParam))
				continue

			# Handle the first 4 items which are common to all query options
			dParamDef = {}
			sParamName = lParam[0]
			sType = lParam[3].upper()

			dParamDef = {'TITLE':lParam[1], 'VAL_TYPE':sType }

			if lParam[2].lower().startswith('req'):
				dParamDef['REQUIRED'] = True
			else:
				dParamDef['REQUIRED'] = False

			sKey = 'paramInfo_%s'%nParam
			if sKey in self.d:
				dParamDef['SUMMARY'] = self.d[sKey]

			# Extra handling by parameter type

			# Pattern:    key | Title | Opt/Req | Type | [default]
			if (sType == 'TEXT') or (sType == 'BOOLEAN'):
				if len(lParam) > 4:
					dParamDef['DEFAULT'] = lParam[4]


			# Pattern:   key | title | opt/req | REAL | [units] | [range] | [default]
			elif sType == 'REAL':

				# Units may be empty
				if (len(lParam) > 4) and (len(lParam[4]) > 0):
					dParamDef['UNITS'] = lParam[4]

				# range may be empty
				if (len(lParam) > 5) and (len(lParam[5]) > 0):
					lRng = [v.strip() for v in lParam[5].split('to')]
					if len(lRng) > 0:
						dParamDef['MIN'] = lRng[0]
					if len(lRng) > 1:
						dParamDef['MAX'] = lRng[1]

				# The default may be empty
				if (len(lParam) > 6) and (len(lParam[6]) > 0):
					dParamDef['DEFAULT'] = lParam[4]


			# Pattern: key | title | opt/req | ENUM | values_list | [default]
			# Pattern: key | title | opt/req | FLAGSET | values_list | [default_set]
			elif (sType == 'ENUM') or (sType == 'FLAG_SET'):

				if len(lParam) > 5:
					if sType == 'ENUM':
						dParamDef['DEFAULT'] = lParam[5]
					else:
						lDefSet = [s.strip() for s in lParam[5].split(',')]
						dParamDef['DEFAULT_SET'] = lDefSet

				lVals = [s.strip() for s in lParam[4].split(',')]

				# Each enum/flag value can have expository text
				dValInfo = self._getValInfo(fLog, nParam)

				lEnum = []
				for sVal in lVals:
					if sVal in dValInfo:
						lEnum.append({'VALUE':sVal, 'TITLE':dValInfo[sVal]})
					else:
						lEnum.append({'VALUE':sVal})

				if len(lEnum) > 0:
					dParamDef['VALUES'] = lEnum


			else:
				fLog.write("Unknown option type %s for key %s"%(sType, key))
				continue

			if dParamDef == None:
				return None

			if dParamDef != None and len(dParamDef) > 0:
				dOpts[sParamName] = dParamDef

		return dOpts


	###########################################################################
	def _getArgTrans(self, fLog, sCategory, dSource):
		"""Query values can be transformed before affecting a program's
		command line.  Get all the query value transformations for a program.

		There are three basic transformation types:

		  pass through - i.e. just put the value as is on the command line

		  map  - Map each possible input value to an output value.  The
		         output value can be none.  These look as follows:

					'key | input list | output list'

		  pattern - put the value into another string.  Note that there are
		         two types of patterns, "suff %{VALUE} more stuff"
					and "stuff %{FLAG,"sep"} more stuff"

					'key | pattern'

		"""
		sPre = "%sTrans"%sCategory

		lKeys = list(self.d.keys())
		lKeys.sort()
		dTrans = {}
		dParams = sourceGetParamDict(dSource)
		for sDsdfKey in lKeys:
			if not sDsdfKey.startswith(sPre):
				continue

			lTrans = escSplitStr(self.d[sDsdfKey], '|', '\\')

			if len(lTrans) < 2:
				raise errors.ServerError(
					"Key %s, expected at least a 2-element list"%sDsdfKey
				)

			sParam = lTrans[0]

			if sParam not in dParams:
				raise errors.ServerError(
					"Key %s, invalid translation, parameter %s not defined"%(
					sDsdfKey, sParam
				))

			dParam = dParams[sParam]  # This param

			# Only substitutions are allowed for real value items
			if (len(lTrans) > 2) and dParam['VAL_TYPE'] == 'real':
				raise errors.ServerError(
					"Key %s looks like a value map, but"%sDsdfKey+\
					"only substituion patterns allowed for real value parameters"
				)

			# Patterns...
			if len(lTrans) == 2:
				dTrans[sParam] = {'_pattern':lTrans[1]}

			# Maps...
			elif len(lTrans) > 2:
				lIn = [ s.strip() for s in lTrans[1].split(',') ]
				lOut = [ s.strip() for s in lTrans[2].split(',') ]

				if len(lIn) != len(lOut):
					raise errors.ServerError(
						"key %s, number of input states"%sDsdfKey +\
						"is %d but there are %d command line output states"%(
						len(lIn), len(lOut)
					))
				dMap = {}
				# Booleans maps are special, values can only be true or false
				if dParam['VAL_TYPE'] == 'boolean':
					nChk = 0
					for i in range(0, 2):
						if lIn[i] in self.lTrue:
							dMap['true'] = lOut[i]
							nChk |= 1
						elif lIn[i] in self.lFalse:
							dMap['false'] = lOut[i]
							nChk |= 2

					if nChk != 3:
						raise errors.ServerError(
							"Key %s, expected both a true and false "+\
							"flag in item 2 of the value, ex: 'true,false'"%sDsdfKey
						)

				else:
					for i in range(0, len(lIn)):
						dMap[lIn[i]] = lOut[i]


				dTrans[sParam] = {'_map':dMap} # Save the map

		return dTrans

	###########################################################################
	def _getInternalInterface(self, fLog, dConf, dSrc):
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

	###########################################################################
	def getInterfaceDef(
		self, dConf, fLog, sRootPathUri, sRootDataUrl, bInternal=False,
		b23Iface=False
	):
		"""returns a dictionary suitable for transmission as a JSON object
		which defines how to talk to this dataset

		# If bInternal is specified, certian extra parameters are
		# added to the definition that shouldn't be sent to client programs

		# Note that there are two very different separators in use for finding
		# das2 datasets.  one is:
		#
		#  server_base_url?server=dataset&dataset=ME
		#  server_base_url/data/ME
		#
		# So the trailing '/' or '&' MUST be included in sRootDataUrl !

		"""

		# Global parameters
		sURI = "%s/%s"%(sRootPathUri, self.sName.lower())
		sTokName = bname(self.sName).replace('.dsdf','').replace(" ","_")
		dSrc = {}
		dDef = {'TYPE':'Das2Source', 
		        'NAME': sTokName,
		        'TITLE':self.d['description'],
		        'PATH_URI': sURI, 'SOURCE':dSrc}

		# Cascade references
		dDef['LINKS'] = self._getLinks(dConf, fLog)

		dSrc['CONTACTS'] = self._getContacts()

		if 'summary' in self.d:
			dSrc['DESC'] = self.d['summary']


		if 'das2Stream' in self.d:
			dSrc['FORMATS'] = {'DEFAULT': {'MIME':'application/vnd.das2.das2stream',
			                  'VERSION':'2.2'}}
		else:
			dSrc['FORMATS'] = {'DEFAULT':{'MIME':'application/vnd.das2.qstream'}}

		dLocInfo = {
			'BASE_URL':"%s%s"%(sRootDataUrl, self.sName),
			'METHOD':'http_get_query'
		}
		if 'readAccess' in self.d:
			if 'age' in self.d['readAccess'].lower():
				dLocInfo['AUTH_REQUIRED'] = "new_data_only"
			else:
				dLocInfo['AUTH_REQUIRED'] = "yes"
		else:
			dLocInfo['AUTH_REQUIRED'] = "no"


		dSrc['ACCESS'] = [dLocInfo]

		# Get all the coordinate items
		# Do a default time item unless implicitTimeItem is false
		dCoords = {}
		if not 'implicitTimeItem' in self.d or \
			self.d['implicitTimeItem'] in self.lTrue:

			dCoords['time'] = {
				'TITLE':'Spacecraft Event Time (UTC)',
				'UNITS':'UTC'
			}

			# Attach old validRange to any time coordinates that are present
			lRng = self.getValidTimeRange(fLog)
			if lRng and len(lRng) > 1:
				dCoords['time']['RANGE'] = {"MIN":lRng[0], "MAX":lRng[1]}

			dCoords['time']['SELECT'] = {"MIN":"time.min", "MAX":"time.max"}

			if self.canReduceInTime(dConf):
				dCoords['time']['SELECT']['RES'] = "time.res"
			elif self.isTrue(u'requiresInterval'):
				dCoords['time']['SELECT']['INT'] = "time.int"


		lKeys = list(self.d.keys())
		lKeys.sort()
		for key in lKeys:
			if not key.startswith('coord_'):
				continue

			lCoord = [ s.strip() for s in  escSplitStr(self.d[key], '|', '\\') ]
			dCoord = {}
			if len(lCoord) > 1:
				dCoord['UNITS'] = lCoord[1]
			if len(lCoord) > 2:
				dCoord['TITLE'] = lCoord[2]
			dCoords[lCoord[0]] = dCoord

			sRngKey = key.replace('coord_','cordRange_')
			if sRngKey in self.d:
				lRng = [s.strip() for s in self.d[sRngKey].split(' to ')]
				dCoord['RANGE'] = {"MIN":lRng[0], "MAX":lRng[1]}

			sSelKey = key.replace('coord_','coordSelect_')
			if sSelKey in self.d:
				lSels = [ s.strip() for s in  escSplitStr(self.d[sSelKey], '|', '\\') ]
				for sSel in lSels:
					lPair = [s.strip() for s in sSel.split(':')]
					if (len(lPair) != 2) or (lPair[0] not in ('MIN','MAX','RES','INT')) \
					   or (len(lPair[1]) == 0):
						raise errors.ServerError("Malformed value for key %s"%sSelKey)
					if 'SELECT' not in dCoord:
						dCoord['SELECT'] = {lPair[0] : lPair[1]}
					else:
						dCoord['SELECT'][lPair[0]] = lPair[1]


		dSrc['COORDINATES'] = dCoords

		i = 0
		dData = {}
		for key in lKeys:
			if key.startswith('item_') or key.startswith('data_'):
				lItem = [ s.strip() for s in  escSplitStr(self.d[key], '|', '\\') ]
				dItem = {}
				dData[lItem[0]] = dItem
				#dItem['ENABLED'] = True
				if len(lItem) > 1 and len(lItem[1]) > 0:
					dItem['AXIS'] = lItem[1]
				if len(lItem) > 2 and len(lItem[2]) > 0:
					dItem['UNITS'] = lItem[2]
				if len(lItem) > 3 and len(lItem[3]) > 0:
					dItem['TITLE'] = lItem[3]

		dSrc['DATA'] = dData

		# Coordinate Browse Parameters, since default values are set by the
		# example time, get that first
		dGetQuery = {}
		dSrc['QUERY_PARAMS'] = dGetQuery
		dSubSets = {}
		dGetQuery['COORD_SUBSET'] = dSubSets

		# Providing examples, True at the ends means use das 2.3 interpretation
		# We
		dSrc['QUERY_EXAMPLES'] = self.getExamples(fLog, sRootDataUrl, b23Iface)

		if not 'implicitTimeItem' in self.d or \
			self.d['implicitTimeItem'] in self.lTrue:
			dSubSets['time'] = self._getDefTimeParams(fLog, sRootDataUrl)


		# Get data source options, these are extra command line parameters
		# that do not sub-select data by coordinate ranges
		dOpts = self._getHttpGetOpts(fLog)

		if len(dOpts) > 0:
			dGetQuery['OPTIONS'] = dOpts
		else:
			# For das 2.2 all options were crammed into params, make a 
			# generic entry for that if no specific options were seen
			dGetQuery['OPTIONS'] = {'params':{
			   'REQUIRED':False, 'TYPE':'text', 'TITLE':'Reader Parameters',
				'SUMMARY':'Generic reader command pass through'
			}}


		# If requested, add in the internal server definitons
		if bInternal:
			dImpl = self._getInternalInterface(fLog, dConf, dSrc)
			if dImpl == None:
				return None

			dSrc['_implementation'] = dImpl

		return dDef

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
			io.queryError(
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
	sServer = io.getScriptUrl()
	if sServer.endswith('/'):
		sServer = sServer[:-1]

	if u'server' in dsdf:
		sNewServer = dsdf[u'server'].encode('ascii', 'replace')
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

		io.serverError(fLog, "Dataset %s does not require redirection"%sOldName)
		return 17

	return 0
