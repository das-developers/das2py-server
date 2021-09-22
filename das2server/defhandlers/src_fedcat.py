"""Default handler for sending data source information as JSON description"""

from io import StringIO     # handles unicode strings

import sys
import os
import json
from urllib.parse import urlencode, quote_plus

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

#############################################################################

def formatsInterface(dConf):
	"""Return an interface section for the available formats"""
	dFmts = {
		'das2binary': {
			"name":"das2 binary",
			"title":"das2 binary stream, application/vnd.das2.das2stream (*.d2s)",
			"enabled":{"value":True},
		},

		'das2text': {
			"name":"das2 text",
			"title":"das2 text stream, text/vnd.das2.das2stream; charset=utf-8",
			"enabled":{"value":False,
				"set":{"param":"format.mime", "value":"application/vnd.das2.das2stream"},
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
		},

		'csv':{
			"name":"delimited text",
			"title":"Text columns, typically separated by commas (CSV)",
			"enabled":{"value":False,
				"set":{"param":"format.mime","value":"text/csv"},
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
			},
			"delim":{
				"name":"Field Deliminator",
				"title":"Change the field deliminator",
				"value":"comma",
				"set":{
					"param":"format.delim",
					"enum":[{"value":"comma"},{"value":"semicolon"},{"value":"tab"}]
				}
			}
		},

		'png':{
			"name":"PNG Image",
			"title":"Output a plot image instead of data",
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
		},

		"votable":{
			"name":"VOTable",
			"title":"Output a VOTable for use with TOPCAT",
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
	}

	return dFmts

##############################################################################
def formatHttpParams(dConf):
	"""Return a dictionary of formatting parameters to add to the http params 
	section
	"""
	dFmtParams = {
		"format.mime"     : {"required":False, "name":"MIME"},
		"format.secfrac"  : {"required":False},
		"format.sigdigit" : {"required":False},
		"format.delim"    : {"required":False},
		"format.width"    : {"required":False},
		"format.height"   : {"required":False},
		"format.serial"   : {"required":False}
	}
	return dFmtParams;

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface
	"""
	sDsdf = os.getenv("PATH_INFO")  # Knock off leading '/source'
	if sDsdf.startswith('/source/'):
		sDsdf = sDsdf[len('/source/'):]
	else:
		U.webio.serverError(fLog, u"PATH_INFO did not start with /source/")

	if sDsdf.endswith('/das2.json'):
		sDsdf = sDsdf.replace("/das2.json", '.dsdf')
	else:
		U.webio.serverError(fLog, u"PATH_INFO did not end with /das2.json")

	sDataUrl = "%s/%s/data"%(U.webio.getScriptUrl(), sDsdf.replace('.dsdf','').lower())
	
	fLog.write("\nDas2 HttpStreamSrc definition Handler")
	
	if 'DSDF_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	# Hidden debug switch
	bInternal = False
	if form.getfirst('internal', '') != '':
		bInternal = True

	dDef = U.source.dsdfToSrcExternal(dConf, sDsdf, sDataUrl fLog)
	
	# Add our supported output conversion interface controls and parameters
	if dsdf.isTrue('qstream'):
		dDef['interface']['format']['qstream'] = {
			"enabled": {"value":True }, "mime":"application/vnd.das2.qstream",
			"extension":"qds", "name":"QStream"
		}
	else:
		dDef['interface']['format'] = availFormats(dConf)
		for key in dFmtParams:
			dDef['protocol']['http_params']['key'] = dFmtParams['key']

	# Set the base urls and the example urls for the query:
	dDef['protocol']['base_urls'] = [sDataUrl]
	for key in dDef['protocol']['examples']:
		dEx = dDef['protocol']['examples'][key]
		
		# Really, the Juno/WAV/Survey.json from the disk should know nothing
		#         about my http param scheme.  It should denote args from it's
		#         command line point of view.  At least it's isolated from my
		#         base URL.
		#         Fixing this is a problem for pyserver v2.4 -cwp 2021-09-21
		
		if ("http_params" in dEx) and (len(dEx["http_params"]) > 0):
			dEx['url'] = "%s?%s"%(sDataUrl, urlencode(dEx, quote_via=quote_plus))
		else:
			dEx['url'] = sDataUrl

	pout('Access-Control-Allow-Origin: *\r\n')
	pout('Access-Control-Allow-Methods: GET\r\n')
	pout('Access-Control-Allow-Headers: Content-Type\r\n')
	pout("Content-Type: application/json; charset=utf-8\r\n")
	
	sOut = json.dumps(dDef, ensure_ascii=False, sort_keys=True, indent=3)
	sys.stdout.buffer.write(sOut.encode('utf-8'))
	return 0



