"""Helpers related to output formatting"""

# ######################################################################### #
def getConverters(dConf):

	# Binary, Type In, Type Out, Options
	tTxtOpts = ('format.frac_secs', 'format.sig_digits')
	tBinOpts = ('bin.time.max')

	lConv = [
		['das2_ascii', ('das','2.2','bin'), ('das','2.2','text'), tTxtOpts ]
		['das2_csv',   ('das','2.2','bin'), ('csv',None,None), tTxtOpts    ]
		['das2_csv',   ('das','2.2','bin'), ('csv',None,None), tTxtOpts    ]
		['das2_hapi',  ('das','2.2','bin'), ('hapi','1.0','text'), tTxtOpts]
		['das1_ascii', ('das','1.0','bin'), ('das','1.0','text'), tTxtOpts ]
	
		['das2_from_das1',('das','1.0','bin'), ('das','2.2','bin'), None]
		['das2_from_tagged_das1',('das','1.1','bin'), ('das','2.2','bin'), None]

		['das2_bin_avgsec',('das','2.2','bin'),('das','2.2','bin'), tBinOpts]
		['das2_bin_avg',   ('das','2.2','bin'),('das','2.2','bin'), tBinOpts]
		['das2_bin_peakavgsec', ('das','2.2','bin'),('das','2.2','bin'), tBinOpts]
		['das2_psd',   ('das','2.2','bin'),('das','2.2','bin'), tDftOpts]

	]


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
				sExt = 'dast'
				sTitle = 'das text packet stream'
				sMime = 'text/vnd.das.stream; charset=utf-8'

			elif sSerial == 'xml':
				sExt = 'dasx'
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
				sMime = 'text/vnd.das2.das2stream; charset=utf-8'

			else:
				sExt = 'd2s'
				sTitle = 'das2 binary packet stream'
				sMime = 'application/vnd.das2.das2stream'
			
		elif sVersion.startswith('1.1'):
			if sSerial == 'text':
				sExt = 'd2t'
				sTitle = 'das1 text packet stream'
				sMime = 'text/vnd.das2.das1stream; charset=utf-8'

			else:
				sExt = 'd1s'
				sTitle = 'das1 binary packet stream'
				sMime = 'application/vnd.das2.das1stream'

		elif sVersion.startswith('1.0'):
			if sSerial == 'text':
				sExt = 'tab'
				sTitle = 'Tabular listing'
				sMime = 'text/plain; charset=utf-8'

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
			sMime = 'text/vnd.das2.qstream; charset=utf-8'
			sExt = 'qdt'
		else:
			sTitle = 'Autoplot intrinsic stream'
			sMime = 'application/vnd.das2.qstream'
			sExt = 'qds'


	return (sMime, sExt, sTitle)

#############################################################################

def getFormatSelection(dConf, lRdrOut):
	"""
	Args:
		dConf (dict) - The server configuration information
		tRdrOut (tuple) - The default output type and version (sType, sVer)

	Return (dict):
	   A format controls interface suitable for conversion to a json description

	Notes:
	Here we olve for the formats that can be supported and return them as
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
		"frac_secs":{
			"name":  "Factional Seconds",
			"title": "How many digits to include for fractional seconds, minimum is 0",
			"value": 3,
			"set":{"param":"format.secfrac"}
		},
		"sig_digits":{
			"name":"Significant Digits",
			"title":"Number of significant digits for general values (not time strings)",
			"value":5,					
			"set":{"param":"format.sigdigit"}
		}
	}

	# Stream formats.....

	# Handle qstream
	if sRdr == 'qstream':
		dFmts['qstream'] = {
			"name":"QStream",
			"title":"Native Autoplot data format",
			"enabled":{"value":True,
				"set":{"param":"format.type", "value":"qstream"},
			}
		}

		if 'QDS_TO_UTF8' in dConf:
			dFmts['qstream']['variant'] = {
				"name":"Variant",
				"value":"binary",
				"set":{
					"param":"format.serial",
					"enum": [{"value":"text"},{"value":"binary"}]
				}
			}

			# Don't know if qds transformer has sig-digit options don't add them
			# in for now.
	
	else:
		dFmts['das'] = {
			"name":"Das Stream",
			"title":"Streaming format for plots",
			"enabled":{"value":True, "set":{"param":"format.type", "value":"das"} }
		}

		# Set the output versions, with regard to supported transforms, since
		# we don't down-convert only the supported version and higher are allowed

		# Uncomment when das-2.2 to das-3.0 converter exists
		#if sVer in ("1.0", "1.1"): lVals = [sVer, "2.2", "3.0"]
		#elif sVer == "2.2":        lVals = [sVer, "3.0"]
		#elif sVer == "3.0":        lVals = [sVer]

		if sVer in ("1.0", "1.1"): lVers = [sVer, "2.2"]
		elif sVer == "2.2":        lVers = [sVer]
		elif sVer == "3.0":        lVers = [sVer]

		dFmts['das']['version'] = { "name":"Stream Version", "value": sVer}

		if len(lVers) > 1:
			lVers = [ {"value":s} for s in lVers ]
			dFmts['das']['version']['set'] = { "param":"format.version", "enum":lVers }

		# Can always convert das streams to text, sometimes to XML!
		lSerials = [ {"value":s} for s in ("text","binary")]
		if "3.0" in lVers:
			lSerials.append( {"value":"xml"} )
		
		dFmts['das']['serial'] = {
			"name":"Serialization",
			"value":"binary",
			"set":{"param":"format.serial", "enum":lSerials }
		}
	
		# Add in general purpose text formating information:
		for sOpt in dTextOpts:
			dFmts['das'][sOpt] = dTextOpts[sOpt]


	# Generic translation formats, depending on installed converters
	if ('D2S_CSV_CONVERTER' in dConf) and (sRdr == 'das') and (sVer != '3.0'):
		dFmts['csv'] = {
			"name":"Delimited Text",
			"title":"Delimited Text (CSV, TSV, etc.)",
			#"mime":"text/csv",
			#"extension":".csv",
			"enabled":{"value":False,
				"set":{"param":"format.type", "value":"csv"},
			},
			"delim":{
				"name":"Field Deliminator",
				#"title":"Field Deliminator",
				"value":"comma",
				"set":{
					"param":"format.delim",
					"enum":[{"value":"comma"},{"value":"semicolon"},{"value":"tab"}]
				}
			}	
		}
		
		# Add in general purpose text formating information:
		for sOpt in dTextOpts:
			dFmts['csv'][sOpt] = dTextOpts[sOpt]			
		


	if ('DAS_TO_PNG' in dConf) and (sRdr == 'das') and (sVer != '3.0'):
		dFmts['png'] = {
			"name":"PNG Image",
			"title":"Output a plot image instead of data",
			#"mime":"image/png",
			#"extension":".png",
			"enabled":{"value":False,
				"set":{"param":"format.mime","value":"image/png"}
			},
			"width":{
				"name":"Image Width",
				"title":"The width of the plot image in pixels",
				"value":800,
				"set":{"param":"format.width"}
			},
			"height":{
				"name":"Image Height",
				"title":"The height of the plot image in pixels",
				"value":640,
				"set":{"param":"format.width"}
			}
		}

	if ('DAS_TO_VOTABLE' in dConf):
		dFmts["votable"] = {
			"name":"VOTable",
			"title":"Output a VOTable for use with TOPCAT, application/x-votable+xml (*.xml)",
			#"mime":"application/x-votable+xml",
			#"extension":".xml",
			"enabled":{"value":False,
				"set":{"param":"format.mime","value":"application/x-votable+xml"}
			},
			"serial":{
				"name":"Serialization",
				"title":"VOTable data can be included within the file, or as an external stream",
				"value":"tabledata",
				"set":{"param":"format.serial",
					"enum":[{"value":"tabledata"},{"value":"binary"}]
				}
			}
		}

	return dFmts
	

##############################################################################
def addFormatHttpParams(dConf, dParams):
	"""Add our output formatting parameters to the protocol/http_params section
	Should check dConf to see if:
		Image server is set

	Here we say what the server will accept and don't really care if any of these
	are enabled in the inteface section or not.
	"""

	dParams["format.type"]     = {
		"required":False, "name":"Format",
		"enum":["das","csv","png","votable","qstream"]
	}
	dParams["format.secfrac"]  = {"required":False, "type":"integer"}
	dParams["format.sigdigit"] = {"required":False, "type":"integer"}
	dParams["format.delim"]    = {"required":False, "type":"string"}
	dParams["format.width"]    = {"required":False, "type":"integer"}
	dParams["format.height"]   = {"required":False, "type":"integer"}
	dParams["format.serial"]   = {
		"name":"Serialization",
		"required":False, 
		"enum":["text","xml","binary"]
	}
	dParams['format.version']  = {"required":False, "type":"string"}
	

	