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

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.handlers.intro.py for a decription of this function
	interface
	"""

	sSource = os.getenv("PATH_INFO")  # Knock off leading '/source'
	if sSource.startswith('/source/'):
		sSource = sSource[len('/source/'):]
	else:
		U.webio.serverError(fLog, u"PATH_INFO did not start with /source/")

	if sSource.endswith('/api.json'):
		sSource = sSource.replace("/api.json", '.dsdf')
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
		dDef = U.source.external(dConf, sSource,fLog)
	except U.errors.QueryError:
		U.webio.queryError(fLog, "Data source does not exist")
		return 17
	except U.errors.ServerError as e:
		U.webio.serverError(fLog, str(e));
		return 17
	
	pout('Access-Control-Allow-Origin: *')
	pout('Access-Control-Allow-Methods: GET')
	pout('Access-Control-Allow-Headers: Content-Type')
	pout("Content-Type: application/json; charset=utf-8\r\n")
	
	sOut = json.dumps(dDef, ensure_ascii=False, sort_keys=True, indent=3)
	sys.stdout.write(sOut)
	return 0



