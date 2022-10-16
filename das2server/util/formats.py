"""Helpers related to output formatting"""

# This is just a convetion used by this server, federated catalog items
# advertise thier keys in an API file.
g_tKeyConvention = (
	"read.time.min", "read.time.max", "bin.time.max", "read.time.intr",
	"read.opts"
)

g_sDas1File = 'das1.pro'
g_sParamSecFrac = "format.secfrac"
g_sParamSigDigit = "format.sigdigit"
g_sParamDelim = "format.delim"

# ######################################################################### #
def getMime(sType, sVersion, sSerial):
	"""Given info on an output type, define the mime string

	Args:
		sType - The basic type, one of 'das', 'csv', 'png', 'qstream', etc.
		sVersion - A type version some of the early das versions are just
		   octet-streams
		sSerial - Sometimes the same information can be represented multiple
		   ways (binary, text, xml)

	Returns a (mime type, extension, title) tuple
	"""

	sMime = None
	sExt = None
	sTitle = None

	if sType == 'das':
		if sVersion.startswith('3'):
			if sSerial == 'text':
				sExt = 'tdas'
				sTitle = 'das text packet stream'
				#sMime = 'text/vnd.das.stream; charset=utf-8'
				sMime = 'text/vnd.das.stream'

			elif sSerial == 'xml':
				sExt = 'xdas'
				sTitle = 'das XML stream'
				sMime = 'application/vnd.das.doc+xml'

			else:
				sExt = 'das'
				sTitle = 'das binary packet stream'
				sMime = 'application/vnd.das.stream'

		elif sVersion.startswith('2'):
			if sSerial == 'text':
				sExt = 'd2t'
				sTitle = 'das2 text packet stream'
				#sMime = 'text/vnd.das2.das2stream; charset=utf-8'
				sMime = 'text/vnd.das2.das2stream'

			else:
				sExt = 'd2s'
				sTitle = 'das2 binary packet stream'
				sMime = 'application/vnd.das2.das2stream'
			
		elif sVersion.startswith('1.1'):
			if sSerial == 'text':
				sExt = 'd2t'
				sTitle = 'das1 text packet stream'
				#sMime = 'text/vnd.das2.das1stream; charset=utf-8'
				sMime = 'text/vnd.das2.das1stream'

			else:
				sExt = 'd1s'
				sTitle = 'das1 binary packet stream'
				sMime = 'application/vnd.das2.das1stream'

		elif sVersion.startswith('1.0'):
			if sSerial == 'text':
				sExt = 'tab'
				sTitle = 'Tabular listing'
				#sMime = 'text/plain; charset=utf-8'
				sMime = 'text/plain'

			else:
				sExt = 'bin'
				sTitle = 'IEEE big-endian floats'
				sMime = 'application/octet-stream'

	elif sType == 'csv':
		sExt = '.csv'
		sTitle = 'Delimited text'
		sMime = 'text/csv'

	elif sType == 'png':
		sExt = '.png'
		sTitle = 'Portable Network Graphics'
		sMime = 'image/png'

	elif sType == 'qstream':
		if sSerial == 'text':
			sTitle = 'Autoplot intrinsic stream'
			#sMime = 'text/vnd.das2.qstream; charset=utf-8'
			sMime = 'text/vnd.das2.qstream'
			sExt = 'qdt'
		else:
			sTitle = 'Autoplot intrinsic stream'
			sMime = 'application/vnd.das2.qstream'
			sExt = 'qds'


	return (sMime, sExt, sTitle)

#############################################################################

def getFormatSelection(dConf, lRdrOut, bWebSockConn=False):
	"""
	Args:
		dConf (dict) - The server configuration information
		lRdrOut (tuple) - The default output type and version (sType, sVersion, sVariant)

	Return (dict):
	   A format controls interface suitable for conversion to a json description

	Notes:
	Here we solve for the formats that can be supported and return them as
	output options.  Since the rule in das2 is that everything is a stream,
	so long as A -transforms-> B and B -transforms-> C, then A -> C.
	
	Unrolled List of all outputs and mimes:

	Type    Ver  Variant MIME                             Ext  Note
	----    ---  ------- ------------------------        ----  ------------------
	das     1.0  binary  application/octet-stream         .bin  Pile of big-endian floats
	das     1.0  text    text/plain                       .tab  A pile of numbers
	
	das     1.1  binary  application/vnd.das2.das1stream  .d1s  Tagged das1
	das     1.1  text    text/vnd.das2.das1stream         .d1t

	das     2.2  binary  application/vnd.das2.das2stream  .d2s
	das     2.2  text    text/vnd.das2.das2stream         .d2t
	
	das     3.0  binary  application/vnd.das.stream       .das   Can contain verson 3
	
	das     3.0  text    text/vnd.das.stream              .tdas  files, but usable for
	das     3.0  xml     application/vnd.das.doc+xml      .xdas  others as well.
	das     3.0  json    application/vnd.das.doc+json     .jdas  

	h-api        text    text/csv                         .csv

	qstream      binary  application/vnd.das2.qstream     .qds

	png                  image/png                        .png

	csv                  text/csv                         .csv

	votable      header  application/x-votable+xml        .xml
	votable      data    application/octet-stream         .bin
	

	Some transforms are missing, currently only the following work:

	  das1 [all variants] -> das1 [text] 

	  das2 [all variants] -> das2 [text]
	                      -> h-api
	                      -> png [maybe]
                         -> csv
     
     das3 [all variants] -> [none]

	  qstream -> png [maybe] 

	What we want is:

	  das1 [all variants] -> das2 [binary]
     
     das2 [binary]       -> das2 [text]
	  das2 [all variants] -> das3 [binary]

	  das3 [all variants] -> das3 [text,xml]
	  das3 [all variants] -> csv
	                      -> png
	                      -> votable
	                      -> h-api
	"""

	#####
	#   TODO: Replace with a list of atomic transitions and a solver
	#

	dFmts = {}

	sRdr = lRdrOut[0]
	sVer = lRdrOut[1]
	sVar = lRdrOut[2]


	# General properties to add in for many text formats
	dTextOpts = {
		"fracSecs":{
			"label":  "Factional Seconds",
			"title": "How many digits to include for fractional seconds, minimum is 0",
			"value": 3,
			"set":{"param":g_sParamSecFrac}
		},
		"sigDigits":{
			"label":"Significant Digits",
			"title":"Number of significant digits for general values (not time strings)",
			"value":5,					
			"set":{"param":g_sParamSigDigit}
		}
	}

	# Stream formats.....

	# Handle qstream
	if sRdr == 'qstream':
		dSettings = {
			"enabled":{"value":True,
				"set":{"param":"format.type", "value":"qstream"},
			}
		}
		dFmts['qstream'] = {
			"label":"QStream",
			"title":"Native Autoplot data format",
			"mimeTypes":[getMime('qstream', None, 'binary')[0]],
			'properties':dSettings
		}

		if 'QDS_TO_UTF8' in dConf:
			dSettings['serial'] = {
				"label":"Serialization",
				"value":"binary",
				"set":{
					"param":"format.serial",
					"enum": [{"value":"text"},{"value":"binary"}]
				}
			}
			dFmts['qstream']['mimeTypes'].append(getMime('qstream',None,'text')[0])

			# Don't know if qds transformer has sig-digit options don't add them
			# in for now.
	
	elif sRdr == 'das':
		lMimes = []
		dFmts['das'] = {
			"label":"Das Stream",
			"title":"Streaming format for plots",
			"mimeTypes":lMimes,
			'properties':{
				"enabled":{"radioGroup":"format", "value":True, "set":{
					"value":True, "param":"format.type", 'pval':'das'
				}}
			}
		}

		# Set the output versions, with regard to supported transforms, since
		# we don't down-convert only the supported version and higher are allowed

		# Uncomment when das-2.2 to das-3.0 converter exists
		#if sVer in ("1.0", "1.1"): lVals = [sVer, "2.2", "3.0"]
		#elif sVer == "2.2":        lVals = [sVer, "3.0"]
		#elif sVer == "3.0":        lVals = [sVer]

		if sVer in ("1.0", "1.1"):
			lVers = [sVer, "2.2"]
			lMimes = [getMime('das', sVer, "binary")[0]]
		elif sVer == "2.2":
			lVers = [sVer]
			lMimes = []
		elif sVer == "3.0":
			lVers = [sVer]
			lMimes = [getMime('das', sVer, "binary")[0]]

		# We always have das2_ascii
		if "2.2" in lVers:
			lMimes.append( getMime(sRdr, "2.2", "binary")[0] )
			lMimes.append( getMime(sRdr, "2.2", "text")[0] )

		dFmts['das']['mimeTypes'] = lMimes

		dFmts['das']['properties']['version'] = { "label":"Stream Version", "value": sVer}

		if len(lVers) > 1:
			lVers = [ {"value":s} for s in lVers ]
			dFmts['das']['properties']['version']['set'] = { 
				"param":"format.version", "enum":lVers 
			}

		# Can always convert das streams to text, sometimes to XML!
		
		lSerials = [ {"value":s} for s in ("text","binary")]

		# This is a vapor-ware, disable it until the XML converter is online
		# if "3.0" in lVers:
		#	lSerials.append( {"value":"xml"} )
		
		if sVer == '2.2':
			dFmts['das']['properties']['serial'] = {
				"label":"Serialization",
				"value":"binary",
			"set":{"param":"format.serial", "enum":lSerials }
			}	
		
			# Add in general purpose text formating information:
			for sOpt in dTextOpts:
				dFmts['das']['properties'][sOpt] = dTextOpts[sOpt]


	# Generic translation formats, depending on installed converters
	if ('D2S_CSV_CONVERTER' in dConf) and (sRdr == 'das') and (sVer != '3.0'):
		dFmts['csv'] = {
			"label":"Delimited Text",
			"title":"Delimited Text (CSV, TSV, etc.)",
			"mimeTypes":["text/csv"],
			#"extension":".csv",
			'properties':{
				"enabled":{"radioGroup":"format", "value":False,
					"set":{"value":True, "param":"format.type", "pval":"csv"},
				},
				"delim":{
					"label":"Field Deliminator",
					#"title":"Field Deliminator",
					"value":"semicolon",
					"set":{
						"param":g_sParamDelim,
						"enum":[{"value":"comma"},{"value":"semicolon"},{"value":"tab"}]
					}
				}	
			}
		}
		
		# Add in general purpose text formating information:
		for sOpt in dTextOpts:
			dFmts['csv']['properties'][sOpt] = dTextOpts[sOpt]


	if ('DAS_TO_PNG' in dConf) and (sRdr == 'das') and (sVer != '3.0'):
		dFmts['png'] = {
			"label":"PNG Image",
			"title":"Output a plot image instead of data",
			#"mime":"image/png",
			#"extension":".png",
			'properties':{
				"enabled":{"value":False,
					"set":{"param":"format.mime","value":"image/png"}
				},
				"width":{
					"label":"Image Width",
					"title":"The width of the plot image in pixels",
					"value":800,
					"set":{"param":"format.width"}
				},
				"height":{
					"label":"Image Height",
					"title":"The height of the plot image in pixels",
					"value":640,
					"set":{"param":"format.height"}
				}
			}
		}

	if ('DAS_TO_VOTABLE' in dConf):
		dFmts["votable"] = {
			"label":"VOTable",
			"title":"Output a VOTable for use with TOPCAT, application/x-votable+xml (*.xml)",
			#"mime":"application/x-votable+xml",
			#"extension":".xml",
			"enabled":{"value":False,
				"set":{"param":"format.mime","value":"application/x-votable+xml"}
			},
			"serial":{
				"label":"Serialization",
				"title":"VOTable data can be included within the file, or as an external stream",
				"value":"tabledata",
				"set":{"param":"format.serial",
					"enum":[{"value":"tabledata"},{"value":"binary"}]
				}
			}
		}

	return dFmts

##############################################################################
def addFormatHttpParams(dConf, dParams, lRdrOut, bWebSockConn=False):
	"""Add our output formatting parameters to the protocol/http_params section
	Should check dConf to see if:
		Image server is set

	Here we say what the server will accept and don't really care if any of these
	are enabled in the inteface section or not.
	"""
	sRdr = lRdrOut[0]
	sVer = lRdrOut[1]
	sVar = lRdrOut[2]

	dParams["format.type"]     = {
		"required":False, "name":"Format",
		"enum":["das","csv","png","votable","qstream"]
	}
	dParams["format.secfrac"]  = {"required":False, "type":"integer", "range":[0,9]}
	dParams["format.sigdigit"] = {"required":False, "type":"integer", "range":[2,17]}
	
	if ('D2S_CSV_CONVERTER' in dConf) and (sRdr == 'das') and (sVer != '3.0'):
		dParams["format.delim"]    = {"required":False, "type":"string"}

	if (not bWebSockConn) and  ('DAS_TO_PNG' in dConf) \
	   and (sRdr == 'das') and (sVer != '3.0'):
		dParams["format.width"]    = {"required":False, "type":"integer"}
		dParams["format.height"]   = {"required":False, "type":"integer"}

	dParams["format.serial"]   = {
		"name":"Serialization",
		"required":False,
		"type":"enum",
		"enum":["text","xml","binary"]
	}
	dParams['format.version']  = {"required":False, "type":"string"}
	
##############################################################################
def addFormatCommands(dConf, dFmts, lRdrOut):
	"""Add command templates for formatting output."""

	(sKeyBeg, sKeyEnd, sKeyRes, sKeyIntr, sKeyParams) = g_tKeyConvention

	sRdr = lRdrOut[0]
	sVer = lRdrOut[1]
	sVar = lRdrOut[2]

	nFmt = 0

	if sRdr == 'qstream' and ('QDS_TO_UTF8' in dConf):
		dFmts[nFmt] = {
			'label':'.qds to .qdt converter',
			'triggers':[{'key':'format.serial','value':'text'}],
			'template': dConf['QDS_TO_UTF8'],
			'input':{'type':'qstream'},
			'output':{'type':'qstream','variant':'text'}
		}
		nFmt += 1
		return   # Don't know of anything else I can do with QStream

	if sRdr == 'das':
		
		# If this is a das1 stream, add in the converter for to get to das2
		if sVer == '1.0': # Raw big-endian floats
			sCmd = 'das2_from_das1'
			if 'DAS1_TO_DAS2' in dConf: sCmd = dConf['DAS1_TO_DAS2']

			dFmts[nFmt] = {
				'label':'das v1.0 to v2.2 converter',
				'template':[
					"%s #[_THIS_DIRECTORY_]/%s #%s #%s #[%s#@#]"%(
						sCmd, g_sDas1File, sKeyBeg, sKeyEnd, sKeyIntr
					)
				],
				'triggers':[{'key':'format.version','value':"2.2", 'compare':'ge'}],
				'input':{'type':'das','version':'1.0'},
				'output':{'type':'das','version':'2.2'}
			}
			nFmt += 1

			# Now act as if my version was v2 :)
			sVer = '2.2'

		elif sVer == '1.1': # Tagged stream (B0, etc.)
			sCmd = 'das2_from_tagged_das1'
			dFmts[nFmt] = {
				'label':'das v1.1 (tagged) to v2.2 converter',
				'template':'%s -s -tBeg #%s'%(sCmd, sKeyBeg),
				'triggers':[{'key':'format.version','value':"2.2", 'compare':'ge'}],
				'input':{'type':'das','version':'1.1'},
				'output':{'type':'das','version':'2.2'}
			}
			nFmt += 1
			sVer = '2.2'

		if sVer == '2.2':
			sCmd = 'das2_ascii'
			if 'D2S_TO_UTF8' in dConf: sCmd = dConf['D2S_TO_UTF8']
			dFmts[nFmt] = {
				'label':'das 2.2 binary to text',
				'template':'%s -c #[%s#-s @#] #[%s#-r @#]'%(
					sCmd, g_sParamSecFrac, g_sParamSigDigit
				),
				'triggers':[{'key':'format.serial','value':'text'}],
				'input':{'type':'das','version':'2.2'},
				'output':{'type':'das','version':'2.2','variant':'text'}
			}
			nFmt += 1	
			sCmd = 'das2_csv'
			if 'D2S_CSV_CONVERTER' in dConf: sCmd = dConf['D2S_CSV_CONVERTER']
			dFmts[nFmt] = {
				'label':'das 2.2 to CSV converter',
				'template':'%s #[%s#-s @#] #[%s#-r @#] #[%s#-d @#]'%(
					sCmd, g_sParamSecFrac, g_sParamSigDigit, g_sParamDelim
				),
				'triggers':[{'key':'format.type','value':'csv'}],
				'input':{'type':'das','version':'2.2'},
				'output':{'type':'csv'}
			}
			nFmt += 1	
			if 'DAS_TO_PNG' in dConf:
				sCmd = dConf['DAS_TO_PNG']
				dFmts[nFmt] = {
					'label':'das v2.2 plot image generator',
					'template':'%s #[%s#-w @#] #[%s#-h @#]'%(
						sCmd, 'format.width', 'format.height'
					),
					'triggers':[{'key':'format.type','value':'png'}],
					'input':{'type':'das','version':'2.2'},
					'output':{'type':'png'},
					'streaming':False
				}
				nFmt += 1
			