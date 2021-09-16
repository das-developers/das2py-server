"""Capabilities handler for Helophysics API subsystem"""

import sys
import json

from . import error

##############################################################################
def pout(sOut):
	if sys.version_info[0] < 3:
		sys.stdout.write(sOut)
		sys.stdout.write('\r\n')
	else:
		sys.stdout.buffer.write(sOut)
		sys.stdout.buffer.write(b'\r\n')
	
##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	fLog.write("\nDas 2.2 HAPI Capabilities handler")
	
	pout(b'Access-Control-Allow-Origin: *')
	pout(b'Access-Control-Allow-Methods: GET')
	pout(b'Access-Control-Allow-Headers: Content-Type')
	pout(b'Content-Type: application/json; charset=utf-8')
	
	if not error.paramCheck(fLog, 'capabilities', [], form):
		return 18
	
	pout(b'Status: 200 OK\r\n')
	
	d = {
		"HAPI":"1.1", 
		"status":{"code":1200, "message":"OK"},  # Already in HTTP header, no
		                                         # reason to put it here, but
		                                         # they did anyway
		"outputFormats":["csv"]
	}
	
	sOut = json.dumps(d, ensure_ascii=False, sort_keys=True, indent=3)
	pout(sOut.encode('utf8'))
	
	return 0
