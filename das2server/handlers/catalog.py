"""Default handler for 3.0 style catalog level lists"""

import os
from os.path import join as pjoin
from os.path import basename as bname

# GET /das/server/nodes.csv HTTP/1.1
# HOST: localhost

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.handlers.intro.py for a decription of this function
	interface
	"""
	if 'DATASRC_ROOT' not in dConf:
		U.webio.serverError(fLog, u"DATASRC_ROOT not set in %s"%dConf['__file__'])
		return 17
	
	sUrlPath = os.getenv("PATH_INFO")
	if not sUrlPath or len(sUrlPath) == 0:
		sUrlPath = "/das2list.txt"
	
	lHeaders = [
		"Status: 200 OK",
		'Access-Control-Allow-Origin: *',
		'Access-Control-Allow-Methods: GET',
		'Access-Control-Allow-Headers: Content-Type',
		"Expires: now",
	]

	# Since compiled lists of catalog objects are created in advance, this 
	# is pretty straight forward
	
	sScriptURL = U.webio.getScriptUrl()

	# Output one of three versions:
   # (no path)     - old das2 list
	# /node.csv     - New catalog node list
	# /sources.json - New integrated catalog
	if sUrlPath.endswith('nodes.csv'):
		lHeaders += [
			"Content-Type: text/csv; charset=utf-8",
			'Content-Disposition: attachment; filename="nodes.csv"',
		]

		sFile = pjoin(dConf['DATASRC_ROOT'], 'nodes.csv')
		return U.webio.fileOut(fLog, lHeaders, sFile, "No data sources defined.")

	elif sUrlPath in ("/root.json", "/catalog.json"):
		lHeaders += [
			"Content-Type: application/json; charset=utf-8"
			'Content-Disposition: inline; filename="%s"'%bname(sUrlPath)
		]

		sFile = pjoin(dConf['DATASRC_ROOT'], bname(sUrlPath))
		return U.webio.fileOut(fLog, lHeaders, sFile, "No data sources defined.")

	else:
		lHeaders += [
			"Content-Type: text/plain; charset=utf-8"		
			'Content-Disposition: inline; filename="das2list.txt"'
		]
		sFile = pjoin(dConf['DATASRC_ROOT'], bname(sUrlPath))
		return U.webio.d2sOut(fLog, lHeaders, sFile, "No data sources defined.")
	
	return 1
