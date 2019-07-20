"""Default capabilities request handler"""

import glob
import sys
import json

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription the handler
	interface
	"""
	
	sScript = U.webio.getScriptUrl()
	
	# list the things this server can do
	fLog.write("\nDas 2.3 Capabilities handler")
	pout("Content-Type: application/json; charset=utf-8")
		
	pout("Status: 200 OK\r\n")
	
	#sRef = "http://das2.org/Das2.2.2-ICD_2017-05-09.pdf"
	
	dCap = {
		'id':{
			'version':"1.0", 
			'_purpose':"Get the name of this server",
			'_reference':"http://das2.org/icd/server/id.html"
		},
		'logo':{
			'version':"1.0",
			'_purpose':"Get a little image to associate with this server",
			'_reference':"http://das2.org/icd/server/logo.html"
		},
		'peers': {
			'version':"1.0",
			'_purpose':"Provides a list of peer das2 servers",
			'_reference':"http://das2.org/icd/server/peers.html"
		},
		'list':{
			'version':'1.0',
			'_purpose':'Provide a list of available data sources',
			'_reference':'http://das2.org/icd/server/list.html',
		},
		'dsdf':{
			'version':'1.0',
			'_purpose':'Provide a machine readable description of a data source',
			'_reference':'http://das2.org/icd/server/dsdf.html',
		},
		'dataset':{
			'version':'1.0',
			'_purpose':'Provide data streams from a single source',
			'_reference':'http://das2.org/icd/server/dataset.html',
		},
		'image':{
			'version':'experimental',
			'_purpose':'Instead of sending data, generate a plot and send an image',
		},
		
		# The new Das 2.3 endpoints
		'services':{
			'version':'0.9',
			'_purpose':'Provide this list',
			'_reference':'http://das2.org/icd/server/services.html',
		},
		'directory':{
			'version':'experimental', 
			'_purpose':'Provides path based navigation to datasets in addition to GET keys',
		},
		'source':{
			'version':'experimental',
			'_purpose':'Provide expanded data source definitions in JSON format',
			'_reference':'http://das2.org/icd/server/experimental/source.html'
		},
		'data':{
			'version':'experimental',
			'_purpose':'Provide data streams via flexible GET query parameters'
		}
		
		#,
		#'coverage':{
		#	'version':'experimental',	
		#	'_purpose':'Special reduced dataset providing only records per coordinate bin',
		#}
	}
	
	# Check with the config file to see if HAPI is turned on before saying
	# we have the cap
	sKey = "ENABLE_HAPI_SUBSYS"
	if (sKey in dConf) and (dConf[sKey].lower() in ('true','yes','1')):
		dCap['HAPI'] = {
			'version':'1.0',
			'_purpose':'Provides a heliophysics application programming interface for das2 data sources',
			'_reference':'http://das2.org/icd/server/hapi.html',
		}
	
	sOut = json.dumps(dCap, ensure_ascii=False, sort_keys=True, indent=3)
	pout(sOut.encode('utf8'))
	
	return 17
	

	
