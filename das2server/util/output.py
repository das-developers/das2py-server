"""Helpers related to output formatting"""

#############################################################################

def addFormatSelection(dConf, dFmts):
	"""Add our formats to the interface/formats section"""

	# TODO: Check to see if QStream converts are mentioned in the dConf

	if not dFmts['default']['mime'].startswith('application/vnd.das2.das2stream'):
		return

	dFmts['das2text'] = {
		"name":"das2 text",
		#"title":"text/vnd.das2.das2stream; charset=utf-8 (*.d2t)",
		#"mime":"text/vnd.das2.das2stream; charset=utf-8",
		#"extension":".d2t",
		"enabled":{"value":False,
			"set":{"param":"format.mime", "value":"text/vnd.das2.das2stream"},
		},
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

	dFmts['csv'] = {
		"name":"delimited text",
		"title":"text/csv; charset=utf-8",
		#"mime":"text/csv; charset=utf-8",
		#"extension":".csv",
		"enabled":{"value":False,
			"set":{"param":"format.mime","value":"text/csv"},
		},
		"frac_secs":{
			"name":  "Factional Seconds",
			"title": "digits after decimal mark, minimum is 0",
			"value": 3,
			"set":{"param":"format.secfrac"}
		},
		"sig_digits":{
			"name":"Significant Digits",
			"title":"for general data values, not UTC times",
			"value":5,					
			"set":{"param":"format.sigdigit"}
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

	dFmts["votable"] = {
		"name":"VOTable",
		"title":"Output a VOTable for use with TOPCAT, application/x-votable+xml (*.xml)",
		"mime":"application/x-votable+xml",
		"extension":".xml",
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

##############################################################################
def addFormatHttpParams(dConf, dParams):
	"""Add our output formatting parameters to the protocol/http_params section
	Should check dConf to see if:
		Image server is set

	Here we say what the server will accept and don't really care if any
	of these are enablem in the inteface section or not.
	"""

	dParams["format.mime"]     = {
		"required":False, "name":"MIME",
		"enum":[
			"application/vnd.das2.das2stream",
			"text/vnd.das2.das2stream",
			"text/csv", "image/png", "application/x-votable+xml"
		]
	}
	dParams["format.secfrac"]  = {"required":False, "type":"integer"}
	dParams["format.sigdigit"] = {"required":False, "type":"integer"}
	dParams["format.delim"]    = {"required":False, "type":"string"}
	dParams["format.width"]    = {"required":False, "type":"integer"}
	dParams["format.height"]   = {"required":False, "type":"integer"}
	dParams["format.serial"]   = {
		"name":"Serialization",
		"required":False, 
		"enum":["tabledata","binary"]
	}
	