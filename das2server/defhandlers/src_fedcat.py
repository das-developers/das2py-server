"""Default handler for sending data source information as JSON description"""

from io import StringIO     # handles unicode strings

import sys
import os
import json
from os.path import join as pjoin
from os.path import basename as bname
from os.path import dirname as dname

from urllib.parse import urlencode, quote_plus

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

#############################################################################

def addFormatSelection(dConf, dFmts):
	"""Return an interface section for the available formats"""

	# TODO: Check to see if QStream converts are mentioned in the dConf

	if not dFmts['default']['mime'].startswith('application/vnd.das2.das2stream'):
		return

	dFmts['das2text'] = {
		"name":"das2 text",
		"title":"das2 text stream, text/vnd.das2.das2stream; charset=utf-8 (*.d2t)",
		"mime":"text/vnd.das2.das2stream; charset=utf-8",
		"extension":".d2t",
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
		"title":"Text columns, with a header row. Typically separated by commas (CSV)",
		"mime":"text/csv; charset=utf-8",
		"extension":".csv",
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
	}

	dFmts['png'] = {
		"name":"PNG Image",
		"title":"Output a plot image instead of data",
		"mime":"image/png",
		"extension":".png",
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

	if sDsdf.endswith('/api.json'):
		sDsdf = sDsdf.replace("/api.json", '.dsdf')
	else:
		U.webio.notFoundError(fLog, u"PATH_INFO did not end with /api.json")
	
	fLog.write("\nDas2 HttpStreamSrc definition Handler")
	
	if 'DSDF_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DSDF_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	# Hidden debug switch
	bInternal = False
	if form.getfirst('internal', '') != '':
		bInternal = True
	
	# See if this dsdf is for this server, if not send file not found
	# in das2.3 it's the catalogs job to advertise other servers, not
	# the server itself.
	
	try:
		dDef = U.source.fromDsdf(dConf, sDsdf,fLog)
	except U.errors.QueryError:
		U.webio.queryError(fLog, "Data source does not exist")
		return 17
	except U.errors.ServerError as e:
		U.webio.serverError(str(e));
		return 17
	
	pout('Access-Control-Allow-Origin: *')
	pout('Access-Control-Allow-Methods: GET')
	pout('Access-Control-Allow-Headers: Content-Type')
	pout("Content-Type: application/json; charset=utf-8\r\n")

	# Add our supported output conversion interface controls and parameters
	addFormatSelection(dConf, dDef['interface']['format'])
	
	sOut = json.dumps(dDef, ensure_ascii=False, sort_keys=True, indent=3)
	sys.stdout.write(sOut)
	return 0



