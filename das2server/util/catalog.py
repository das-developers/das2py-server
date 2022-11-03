"""Non-realtime catalog utilities"""

import sys
import os
import json
from os.path import join as pjoin
from os.path import basename as bname
from os.path import dirname as dname

from . import formats

# NOTE: If these change, update class MyOptParse in das_srv_sdef
g_sStdDas1 = 'das1.pro'
g_sStdDas2 = 'das2.d2t'
g_sStdDas3 = 'flex.json'
g_sStdRt   = 'flexRT.json'
g_sStdHapi2 = 'hapi2.json'
g_sStdVo  = 'voservice.xml'
g_sStdIntern = 'internal.json'

# ########################################################################## #

def _loadJson(sInPath):
	"""The missing 1-liner from the json module"""
	with open(sInPath) as fIn:
		dQuery = json.load(fIn)
	return dQuery

def _loadText(sInPath):
	with open(sInPath) as fIn:
		sData = fIn.read()
	return sData

def _writeFile(sPath, sOutput):
	#perr("Writing: %s"%sPath)
	sDir = dname(sPath)

	if not os.path.isdir(sDir):
		os.makedirs(sDir)

	with open(sPath, 'w') as f:
		f.write(sOutput)

def _writeJsonFile(sPath, dOutput):
	sOutput = json.dumps(dOutput, indent="  ");
	_writeFile(sPath, sOutput)

# ########################################################################## #
def topCat(sRoot):
	"""Given the name of some root catalog directory, return the filesystem
	path to the expected top catalog node and the top catalog's child directory.

	Args:
		sRoot (str) - Some filesytem directory

	Returns (str,str) - The top catalog filename and it's contents directory
	"""

	return (pjoin(sRoot, 'root.json'), pjoin(sRoot, 'root'))

# ########################################################################## #
def sourceFiles(sRoot, sLocalId):
	"""Given a root catalog directory and a source local-id, return the 
	filesystem path to standard source and source-set catalog objects.

	Args:
		sRoot (str) - Some filesystem directory

		sLocalId (str) - The local ID for the data source.  Hierachies are denoted
		   by the '/' character.  Use of hierarchies is encouraged.

	Returns (dict): A dictionary containing known standard paths for the given
		local id.  The dictionary will have at least the following keys:

		  d['set'] - Standard location of the SourceSet catalog
		  d['flex'] - Standard location of the das federated catalog entry
		  d['flexRT'] - Standard location of the fed cat realtime source def
		  d['das2'] - Standard location of the das2 source descriptor
		  d['das1'] - Standard location of the das1 source descriptor
		  d['intern']  - Standard location of the internal processing instructions

	Note: All the returned paths are just the standard locations.  This does
	      not mean that there actually is a file at that location
	"""

	(sTopCat, sTopCatDir) = topCat(sRoot)

	sSubPath = sLocalId.lower().replace('/',os.sep)

	d = {
		'set': pjoin(sTopCatDir, sSubPath+'.json'),
      'flex'  : pjoin(sTopCatDir, sSubPath, g_sStdDas3),
      'flexRT': pjoin(sTopCatDir, sSubPath, g_sStdRt),
      'das2'  : pjoin(sTopCatDir, sSubPath, g_sStdDas2),
      'das1'  : pjoin(sTopCatDir, sSubPath, g_sStdDas1),
      'intern'   : pjoin(sTopCatDir, sSubPath, g_sStdIntern),
	}

	return d


# ########################################################################## #
# Update a data source collection #

def _getDas3Fmts(dSource):
	dFmts = dSource['interface']['formats']

	lProvides = []
	for sFmt in dFmts:
		dFmt = dFmts[sFmt]
		for sMime in dFmt['mimeTypes']:
			if sMime not in lProvides:
				lProvides.append(sMime)

	return lProvides

def _getDas2Fmts(dMime, sSource):
	lLines = [sLine.strip() for sLine in sSource.split('\n')]
	for sLine in lLines:
		if sLine.startswith('das2Stream'):
			lSub = [s.strip('"\'').strip() for s in sLine.split('=')]
			if (len(lSub) > 1) and (lSub[1].lower() in ('1','t','true')):
				return [ formats.getMime(dMime, 'das','2','binary')[0] ]

		if sLine.startswith('qstream'):
			lSub = [s.strip('"\'').strip() for s in sLine.split('=')]
			if (len(lSub) > 1) and (lSub[1].lower() in ('1','t','true')):
				return [ formats.getMime(dMime, 'qstream','2','binary')[0] ]

	return [ formats.getMime(dMime, 'das','1','binary')[0]]

def makeCollection(dConf, sSet, lInput, sOutPath):
	"""Create or update the source collection file at sPath.  Source collections
	define a list of sources that basically return the same data but do so
	via different methods.  They are typed by the convention, the following
	conventions are known:

		das/2.2 ---> dsdf.d2t
	   das/3.0 ---> The federated catalog httpstreamsrc object (required)
	   das-websock/1.0 --> The federted catalog websocksrc object
	   hapi/2.0 ---> Output of das2_hapi -d source.dsdf -i -n

	Returns (bool) True if the catalog was updated
	"""

	# First read the stream source to get basic coordinate and data info
	dDas3Src = None
	for sInPath in lInput:
		if bname(sInPath) == g_sStdDas3:
			dDas3Src = _loadJson(sInPath)
			break

	if not dDas3Src:
		perr("Can't update source catalog at %s, couldn't find input '%s'"%(
			sOutPath, g_sStdDas3))
		return False

	dCat = {
		'type':'SourceSet', 'version':'0.1','coords':{},'data':{},'contacts':[],
		'catalog':{}
	}
	
	for s in ('label','title'): 
		if s in dDas3Src: dCat[s] = dDas3Src[s]

	# There are many ways to advertise the coordinates and data for this source
	# but the only one I care about are the ones in flex.json
	
	# Pull up the coordinates and data from the interface description
	dIFace = dDas3Src['interface']
	for sCategory in ('coords','data'):
		if sCategory in dIFace:
			for sDim in dIFace[sCategory]:
				dCat[sCategory][sDim] = {}
				for sProp in ('label','validRange'):
					if sProp in dIFace[sCategory][sDim]: 
						dCat[sCategory][sDim][sProp] = dIFace[sCategory][sDim][sProp]

	
	# Pull up any science contacts
	for d in dDas3Src['contacts']: 
		if d['type'] == 'scientific': dCat['contacts'].append(d)

	dSources = dCat['catalog']

	if sSet.startswith('/'): sSet = sSet[1:]
	sSetUrl = "%s/source/%s"%(dConf['SERVER_URL'], sSet.lower())

	# Load our mime dictionary
	# Load the mime dictionary
	if 'MIME_FILE' not in dConf:
		raise EnvironmentError("MIME_FILE is not defined in your das2server.conf file.")

	if not os.path.isfile(dConf['MIME_FILE']):
		raise EnvironmentError("Move %s.example to %s to finish server configuration"%(
			dConf['MIME_FILE'],dConf['MIME_FILE']
		))

	dMime = formats.loadCommentedJson(dConf['MIME_FILE'])

	# Examine the inputs
	for sInPath in lInput:
		if bname(sInPath) == g_sStdDas3:

			# Re-use the source file already loaded
			dSources['flex'] = {
				'type':'HttpStreamSrc', 'purpose':'primary-stream',
				'label':'Primary Source',
				'description':'A semantic interface definition as '+\
				   'well as a server protocol API definition for an HTTP GET '+\
				   'based, variable resolution, fixed coverage period, data source.',
				'mime':'application/json',
				'provides':_getDas3Fmts(dDas3Src),
				'urls':[ "%s/%s"%(sSetUrl,g_sStdDas3) ]
			}

		elif bname(sInPath) == g_sStdRt:
			dSource = _loadJson(sInPath)
			
			dSources['flexRT'] = {
				'type':'WebSocSrc', 'purpose':'primary-stream',
				'label':'Real-time Source',
				'description':'Similar to regular Das3 sources but also supports real-time '+\
				    'data via a web socket.',
				'mime':'application/json',
				'provides':_getDas3Fmts(dSource),
				'urls':[ "%s/%s"%(sSetUrl,g_sStdRt) ]
			}

		if bname(sInPath) == g_sStdDas2:
			sSource = _loadText(sInPath)
			dSources['das2'] = {
				'type':'Das2DSDF', 'purpose':'primary-stream','label':'Das2 Source',
				'description':'A variable resolution data source description '+\
				   'accessed via a static API',
				'mime':'text/vnd.das2.das2stream',
				'provides':_getDas2Fmts(dMime, sSource),
				'urls':[ "%s/%s"%(sSetUrl,g_sStdDas2)]
			}

		elif bname(sInPath) == g_sStdHapi2:
			dSources['hapi2'] = {
				'type':'HAPIInfo', 'purpose':'primary-stream','label':'HAPI2 Source',
				'description':'A fixed resolution data source description '+\
				    'with selectable output parameters accesed via a static API.',
				'format':'application/json',
				'provides':['text/csv'],
				'urls':[ "%s/%S"%(sSetUrl,g_sStdHapi2) ]
			}

		elif bname(sInPath) == g_sStdDas1:
			dSources['das1'] = {
				'type':'Das1DSDF', 'purpose':'primary-stream','label':'Das1 Source',
				'description':'Legacy local source definition used by Gifferator.pro',
				'provides':'application/octet-stream',
				'mime':'text/plain',
				'urls':[ "%s/%s"%(SetUrl,g_sStdDas1) ]
			}

		elif bname(sInPath) == g_sStdVo:
			dSources['ivoa'] = {
				'type':'VOService', 'purpose':'primary-stream','label':'VO-DataLink',
				'description':'A fixed resolution data source definition compatable '+\
				'with the IVOA datalink protocol',
				'mime':'application/x-votable+xml;content=datalink',
				'provides':['application/x-votable+xml'],
				'urls':[ "%s/%s"%(sSetUrl,g_sStdVo) ]
			}

		# Ignore anything else

	_writeJsonFile(sOutPath, dCat)
	return True

# ########################################################################## #
def addCatTitle(dConf, sRoot, sLocalId, sTitle):
	"""
	Given a local root, add a description for a generic 'Catalog' object from
	an old *.dsdf file
	"""

	(sTopCat, sTopCatDir) = topCat(sRoot)

	sPath = pjoin( sTopCatDir, sLocalId.lower().replace('/',os.sep) + ".json" )

	if len(sLocalId) > 0: sLabel = bname(sLocalId)
	else: sLabel = ""

	if os.path.isfile(sPath):
		dCat = _loadJson(sPath)
	else:
		dCat = {
			'version':'0.5', 'type':'Catalog', 'label':sLabel, 'catalog':{}
		}

	dCat['title'] = sTitle

	_writeJsonFile(sPath, dCat)
	#sys.exit(117)


# ########################################################################## #

def updateFromSrc(dConf, sRootDir, sLocalId):

	"""Starting with the target file walk backwards up the directory tree
	updating catalog files

	args:
		dConf - The server configuration

		sRootDir - A root catalog directory, typically: $PREFIX/catalog
		   but can be ./ if desired.
		   
		sLocalId - The logical ID of the Data Source Set, this is assumed to
		   Relate to the actual data source set file in the following manner:

		   Dir = Root + "/" + sLocalId.lower() + ".json"

	returns (list,None): The list of all catalogs checked and possibly updated
		None otherwise
	"""

	# Given:  Root = "."  sLocalId = ./juno/wav/survey.json
	# 
	# Output or update:
	#   ./juno/wav.json
	#   ./juno.json
	#
	# Given:  Root = /var/www/das2srv/catalog/
	#         Set  = /var/www/das2srv/catalog/root/juno/wav/survey.json
	# 
	# Produce:                                             wav.json
	#                                                 juno.json
	#                                        root.json

	(sTopSrc, sTopSrcDir) = topCat(sRootDir)

	dPaths = sourceFiles(sRootDir, sLocalId)
	#print(dPaths)

	sSetFile = dPaths['set']

	# Get individual directories
	lDirs = [sTopSrcDir] + sLocalId.lower().split('/')
	
	# Not add all previous directories to the current one
	for i in range(len(lDirs) - 1):
		lDirs[i+1] = pjoin(lDirs[i], lDirs[i+1])

	lDirs.reverse() # Start with leaf directory and propogate towards root

	lLbls = sLocalId.split('/')
	lLbls.reverse()
	lLbls += ['Sources']

	sSrvUrl = "%s/source"%dConf['SERVER_URL']
	lUrls = [s.replace(sTopSrcDir, sSrvUrl).replace(os.sep, '/') for s in lDirs]

	#lUrls[-1] = "%s/%s"%(dConf['SERVER_URL'], bname(sTopSrc))
	
	lTitles = [None]*(len(lLbls)-1) + ['Local Root Catalog']
	lSep    = [None]*(len(lLbls)-1) + [':/']
	
	#print("lLbls:", lLbls)
	#print("lDirs:", lDirs)
	#print("lUrls:", lUrls)
	#print("lTitles:", lTitles)
	#sys.exit(117)

	lUpdates = []
	for i in range(1, len(lDirs)):  # Do not alter item 0, just know about it

		sCatPath = lDirs[i]+'.json'

		if os.path.isfile(sCatPath):
			dObject = _loadJson(sCatPath)
			dCat = dObject['catalog']
		else:
			dCat = {}
			dObject = {
				'version':'0.5', 'type':'Catalog', 'label':lLbls[i], 'catalog':dCat
			}
			if lTitles[i]: dObject['title'] = lTitles[i]
			if lSep[i]:    dObject['separator'] = lSep[i]

		# List all the objects in this directory and add them to the catalog
		# you will need to make URLs for them
		lItems = os.listdir(lDirs[i])
		lItems.sort()
		for sItem in lItems:
			if not sItem.endswith('.json'): continue

			dItem = _loadJson(pjoin(lDirs[i], sItem))

			dEntry = {'urls':[ "%s/%s"%(lUrls[i], sItem) ]}
			for s in 'label','title','type':
				if s in dItem:
					dEntry[s] = dItem[s]
			
			dCat[sItem.lower().replace('.json','')] = dEntry

		_writeJsonFile(sCatPath, dObject)
		lUpdates.append(sCatPath)

	return lUpdates

# ########################################################################## #

def _gatherDas2List(dCatalog, sCatPath, sId):
	"""Starting with a given catalog point, at a given path and it's localID
	create the das2 server=list response entries.

	Args:
		dCatalog - The catalog to parse
		sCatPath - The filesystem path to this catalog
		sId - The Local ID by which this catalog is known

	Returns:
		A list of all souces and directorise below this point.  Empty catalogs
		are ignored.
	"""

	if 'catalog' not in dCatalog: return []

	lKeys = list(dCatalog['catalog'])
	lKeys.sort()

	lEntries = []

	# First pass: add all my sub-catalogs and ask them to define themselves
	for sSub in lKeys:
		dSubEntry = dCatalog['catalog'][sSub]
		if dSubEntry['type'] != 'Catalog': continue

		sSubPath = pjoin(sCatPath.replace('.json',''), sSub + '.json')
		dSubCat = _loadJson(sSubPath)

		sSubId = dSubCat['label']
		if len(sId) > 0: sSubId = "%s/%s"%(sId, sSubId)

		lSubEntries = _gatherDas2List(dSubCat, sSubPath, sSubId)

		if len(lSubEntries) > 0:
			lEntries += lSubEntries

	# Second pass: if I have any sources sets, pull up any das2 sources listed
	for sSub in lKeys:
		dSubEntry = dCatalog['catalog'][sSub]
		if dSubEntry['type'] != 'SourceSet': continue

		# Replace sub entry with the full version
		sSubPath = pjoin(sCatPath.replace('.json',''), sSub + '.json')
		dSubCat = _loadJson(sSubPath)

		# Now go looking for Das2 sources
		for sKey in dSubCat['catalog']:
			if dSubCat['catalog'][sKey]['type'] == 'Das2DSDF':
				sSubId = dSubCat['label']  # Name it after me!

				if len(sId) > 0: sSubId = "%s/%s"%(sId, sSubId)

				if 'title' in dSubCat:
					lEntries.append( "%s|%s"%(sSubId, dSubCat['title']))
				else:
					lEntries.append("%s|"%sSubId)

				break  # ... because Highlander (there can be only one)

	# Third job: Only add my name if I had some entries and I am not the empty ID
	if (len(sId) > 0) and (len(lEntries) > 0):
		sEnt = "%s/|"%sId
		if 'title' in dCatalog: sEnt = "%s%s"%(sEnt, dCatalog['title'])
		lEntries.insert(0, sEnt)

	return lEntries

# ########################################################################## #
def _gatherFullList(dCatalog, sCatPath, sId, sUrl):
	"""Starting with a given catalog point, at a given path and it's localID
	create the flattened CSV of all sources and catalogs.
	
	Args:
		dCatalog - The catalog to parse
		sCatPath - The filesystem path to this catalog
		sId - The Local ID by which this catalog is known

	Returns:
		A list of all souces and directorise below this point.  Empty catalogs
		are ignored.
	"""

	if 'catalog' not in dCatalog: return []

	lEntries = []

	lKeys = list(dCatalog['catalog'])
	lKeys.sort()

	# If I'm a catalog, ask all my sub items to define themselves
	if dCatalog['type'] == 'Catalog':
		for sSub in lKeys:
			dSubEntry = dCatalog['catalog'][sSub]
			if dSubEntry['type'] not in ('Catalog','SourceSet'): continue
	
			sSubPath = pjoin(sCatPath.replace('.json',''), sSub + '.json')
			sSubUrl =  dSubEntry['urls'][0]
			dSubCat = _loadJson(sSubPath)
	
			sSubId = dSubCat['label']
			if len(sId) > 0: sSubId = "%s/%s"%(sId, sSubId)
	
			lSubEntries = _gatherFullList(dSubCat, sSubPath, sSubId, sSubUrl)
	
			if len(lSubEntries) > 0:
				lEntries += lSubEntries

	# If I'm a source set, define entries directly.
	elif dCatalog['type'] == 'SourceSet':
		for sSub in lKeys:
			dSub = dCatalog['catalog'][sSub]

			if 'title' in dCatalog: sTitle = '%s, %s'%(dCatalog['title'], dSub['label'])
			else: sTitle = '%s, %s'%(dCatalog['label'], dSub['label'])

			# LocalID, Type, Title, Url, TargMime, Provides
			lEntry = [
				"%s/%s"%(sId, sSub), dSub['type'], sTitle, dSub['urls'][0], 
				dSub['mime']
			]
			if len(dSub['provides']) > 0: lEntry += dSub['provides']
			lEntries.append(lEntry)

	# Third job: If I have any entries, add my entry first
	if len(lEntries) > 0:
		lEntry = [sId, dCatalog['type'], "", sUrl, "application/json"]
		if 'title' in dCatalog: lEntry[2] = dCatalog['title']
		lEntries.insert(0, lEntry)

	return lEntries

# ########################################################################### #
def _expandToSource(dCat, sPath):
	"""Get a nested catalog by filling in all sub-items down to the source 
	level for a single catalog
	"""

	if 'catalog' not in dCat: return

	for sSub in dCat['catalog']:

		# If the sub is a catalog type, expand it 
		if dCat['catalog'][sSub]['type'] not in ('Catalog','SourceSet'):
			continue

		sSubPath = pjoin(sPath.replace('.json',''), "%s.json"%sSub)
		dSub = _loadJson(sSubPath)
		dCat['catalog'][sSub] = dSub

		_expandToSource(dSub, sSubPath)


# ########################################################################### #

def updateLists(dConf, sRoot=None):
	"""
	Walk the sources updating the three collapsed lists.  Will update at least
	the catalogs:
		$DATASRC_ROOT/node.csv      Flat listing
	   $DATASRC_ROOT/catalog.json  Hierarchical listing
	   $DATASRC_ROOT/das2list.txt  (das2 compat)
	   $DATASRC_ROOT/hcat.json     (hapi compat)
	   ???                         (IVOA compat)

	By reading root.json and assuming that collections of sub objects are
	always in an adjacent sub-directory with the same name of a catalog, but
	with *.json stripped off.  For example for the catalog object:

		   /some/path/collection.json

   all directly referenced items will be in:

         /some/path/collection/

   This is just an internal local convertion for das2py-servers and is not
   a property of federated das catalogs when accessed in the normal matter.
	"""

	lWrote = []

	if sRoot == None:
		sRoot = dConf['DATASRC_ROOT']

	(sTopPath, _ignore) = topCat(sRoot)

	dTopCat = _loadJson(sTopPath)

	# Das2 list
	lDas2Items = _gatherDas2List(dTopCat, sTopPath, "") 

	lWrote.append( pjoin(sRoot, 'das2list.txt') )
	fOut = open(lWrote[-1], 'w')
	fOut.write("\n".join(lDas2Items))
	fOut.close()

	# Flat all-sources list
	sTopUrl = "%s/%s"%(dConf['SERVER_URL'], bname(sTopPath))
	llCsvItems  = _gatherFullList(dTopCat, sTopPath, "", sTopUrl)

	# Get number of "provides" columns
	nMax = 0
	for lRow in llCsvItems:
		if len(lRow) > nMax: nMax = len(lRow)

	nProvides = nMax - 5

	lWrote.append( pjoin(sRoot, 'nodes.csv'))
	fOut = open(lWrote[-1], 'w')
	fOut.write('"LocalID","Type","Title","URL","Item-MIME"')
	for i in range(nProvides):
		fOut.write(',"Provides-MIME"')
	fOut.write('\r\n')

	for lItem in llCsvItems:
		# CSV Rule: Double quotes if " appears in an item
		lItem = [s.replace('"','""') for s in lItem]
		sRow = ','.join(['"%s"'%s if len(s) > 0 else "" for s in lItem])

		if len(lItem) < nMax:
			sRow += ","*(nMax - len(lItem))

		fOut.write(sRow)
		fOut.write('\r\n')
	fOut.close()

	# Nested catalogs
	_expandToSource(dTopCat, sTopPath)
	dTopCat['title'] = 'Combined %s Server Catalog'%dConf['SERVER_NAME']

	lWrote.append( pjoin(sRoot, 'catalog.json'))
	_writeJsonFile(lWrote[-1], dTopCat)

	return lWrote
	

