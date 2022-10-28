"""Producing HttpStreamSrc information, this is a standalone module and
   doesn't need the (overloaded) dsdf module.
"""
import os
import sys
import os.path
from os.path import join as pjoin
from os.path import basename as bname
from os.path import dirname as dname
import json
from copy import deepcopy


import das2

"""Automatic source definition section generation based on server configuration

All source generating functions have the same signiture:

fLog  - A logger object, aka something with a .write method.

dConf - The server configuration data

dSrc  - The top level dictionary representing the entire source file *without*
        generated sections.

lArgs - A list of arguments defined by the caller in the data source definition
"""

# ########################################################################### #
def extProtoGetStream(fLog, dConf, dSrc, lArgs):
	"""Emits the following:

		"authentication":{"required":False},
		"baseUrls":[ a list ],
		"convention":"das",
		"method":"get_stream",
	"""

	sServer = webio.getScriptUrl(dConf).strip('/')
	sId = dSrc['__path__'].replace(dConf['DATASRC_ROOT'], '')
	if sId.startswith('/'):
		sId = sId[1:]
	sId = sId.replace('.json','').replace('.dsdf','').lower()

	fLog.write('Source path: %s, DATASRC_ROOT: %s, sID %s'%(
		dSrc['__path__'], dConf['DATASRC_ROOT'], sId
	))

	dProto = {
		"authentication":False,
		"convention":"das/3.0",
		"method":"GET",
		"return":"stream",
		"baseUrls":['%s/source/%s/data'%(sServer, sId)]
	}

	if ('WEBSOCKET_URI' in dConf) and (len(dConf['WEBSOCKET_URI']) > 6):
		dProto['baseUrls'].append(
			"%s/%s/data"%(dConf['WEBSOCKET_URI'], sId)
		)

	return dProto

# ########################################################################### #

def extIface_Fmt(fLog, dConf, dSrc, lArgs):
	"""Using the format of the command output, determine the possible output
	formatting commands.
	"""

	

	return {"derp":"doggy_format_section"}


# ########################################################################### #

def extProtoParams_Fmt(fLog, dConf, dSrc, lArgs):
	"""Using the format of the command output, determine the possible output
	formatting commands.
	"""

	return {"derp":"doggy_protocol_params"}


# ########################################################################### #

def intCmds_Fmt(fLog, dConf, dSrc, lArgs):
	"""Using the format of the command output, determine the possible output
	formatting commands.
	"""

	return {"derp":"doggy_format_stuff"}


# ########################################################################### #
# Simple registry, just have the functions named the same as thier name in 
# the data source definitions #

g_dRegistry = {
	'extIface_Fmt':       extIface_Fmt,
	'extProtoGetStream':  extProtoGetStream,
	'extProtoParams_Fmt': extProtoParams_Fmt,
	'intCmds_Fmt':        intCmds_Fmt,
}

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


tDrop = (
	'reader', 'reducer', 'compressor', 'readAccess', 'groupAccess',
	'hapi', 'subSource', 'hapi', 'readerCmd', 'reducerCmd', 'exampleQuery',
	'readerTrans'
	
	# Autoplot developers built a hard limit buffer into their das2 info
	# parser.  Try to route around the problem by dropping extra stuff
	,'paramValInfo'
) 

def _das22Iface(U, dSrc):
	"""Write a utf-8 string that contains the stream"""

	(sBeg, sEnd, sRes, sInt, Opts) = U.source.stdFormKeys('v3')

	if ('protocol' not in dSrc) or ('http_params' not in dSrc['protocol']):
		raise U.errors.ServerError("'http_params' missing from source definition")

	dParams = dSrc['protocol']['http_params']
	
	# Have to have at least a begin time and end time to support a das2.2 query
	if (sBeg not in dParams) or (sEnd not in dParams):
		raise U.errors.notFoundError("Data source does not support the das2/v2.2 query interface.")

	dDsdf = {}
	if 'title' in dSrc:  dDsdf['description'] = dSrc['title']
	#if 'contacts' in dSrc:
	#	for dContact in dSrc['contacts']:
	#		if dContact['type'] == 'scientific':
							


	fOut = StringIO()
	
	fOut.write(u"<stream version=\"2.2\">\r\n")
	fOut.write(u"  <properties\r\n")

	lKeys = list(dsdf.keys())
	lKeys.sort()
	sLastPre = ''
	for sKey in lKeys:
	
		bCont = False
		for sTmp in tDrop:
			if sKey.startswith(sTmp):
				bCont = True
				break
		
		if bCont:
			continue

		# Replace special characters
		lValue = list( dsdf[sKey])
		dReplace = {u'&':u'&amp;', u'"':u'&quot;', u"'":u'&apos;', u"<":u"&lt;",
		            u'>':u'&gt;', u'(':'', u')':''}
		lRepKeys = dReplace.keys()
		
		lNewValue = [None]*len(lValue)
		for i in range(0, len(lValue)):
			if lValue[i] in lRepKeys:
				lNewValue[i] = dReplace[ lValue[i] ]
			else:
				lNewValue[i] = lValue[i]
				
		uValue = u"".join(lNewValue)
		
		# See if we want to space this out
		lKey = sKey.split('_')
		if (len(sLastPre) > 0) and (not sKey.startswith(sLastPre)):
			fOut.write( u'\r\n    %s="%s"\r\n'%(sKey, uValue.strip("'")))
		else:
			fOut.write( u'    %s="%s"\r\n'%(sKey, uValue.strip("'")))
		sLastPre = lKey[0]
	
	fOut.write(u" />\r\n")
	fOut.write(u"</stream>")
	
	return fOut.getvalue()
