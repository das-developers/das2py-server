"""Capabilities handler for Helophysics API subsystem"""

import sys
import json
import error

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	fLog.write("\nDas 2.2 HAPI Capabilities handler")
	pout("Content-Type: application/json; charset=utf-8")
	
	if not error.paramCheck(fLog, 'capabilities', [], form):
		return 18
	
	pout("Status: 200 OK\r\n")
	
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
