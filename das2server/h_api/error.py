"""HAPI error handling, it's different that das2"""

import json
import sys


def sendJson(fLog, dOut):
	sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
	
	fLog.write("   Code %d: %s\n"%(dOut['status']['code'],
	                               dOut['status']['message']))
	
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

def _pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')


##############################################################################
def sendDasError(fLog, U, e, bSendContent=False):
	"""
	U - The das2server util module handle
	e - the exception
	"""
	
	dStatus = {'message': str(e) }
	dOut = {"HAPI": "1.1", 'status':dStatus}	
	
	if isinstance(e, U.errors.ForbidError):
		if bSendContent:
			_pout("Content-Type: application/json; charset=utf-8")

		_pout('Status: 501 Not Implemented\r\n')
		
		dStatus['code'] = 1698
		dStatus['message'] = 'Protocol Error - Authentication required ' \
		                     'but HAPI does not support authentication'
									
	elif isinstance(e, U.errors.QueryError):
		if bSendContent: 
			_pout("Content-Type: application/json; charset=utf-8")

		_pout('Status: 400 Bad Request\r\n')
		dStatus['code'] = 1400
	
	else:
		# Picks up ServerError and TodoError as well as anything else
		if bSendContent: 
			_pout("Content-Type: application/json; charset=utf-8")

		_pout('Status: 500 Internal Server Error\r\n')
		dStatus['code'] = 1500
	
	sendJson(fLog, dOut)


##############################################################################
def sendUnkId(fLog, sKey, bSendContent=False):
	if bSendContent: 
		_pout("Content-Type: application/json; charset=utf-8")

	_pout('Status: 404 Not Found\r\n')
	
	dStatus = {'code': 1406, 'message':'Bad Request - unknown dataset id'}
	dOut = {"HAPI": "1.1", 'status':dStatus}
	
	sendJson(fLog, dOut)

##############################################################################
def sendServerError(fLog, sMsg, bSendContent=False):
	if bSendContent: 
		_pout("Content-Type: application/json; charset=utf-8")

	_pout('Status: 500 Internal Server Error\r\n')
	
	dStatus = {'code':1500, 'message': sMsg}
	dOut = {"HAPI": "1.1", 'status':dStatus}
	sendJson(fLog, dOut)

##############################################################################
def sendIncompatable(fLog, sInternalMsg, bSendContent=False):
	if bSendContent: 
		_pout("Content-Type: application/json; charset=utf-8")

	_pout("Status: 501 Not Implemented\r\n")
	
	sMsg = 'Protocol Error - Data source incompatable with HAPI transport protocol: '
	sMsg += sInternalMsg
	
	dOut = {
		"HAPI":"1.1", 
		'status':{'code':1699, 
		'message':sMsg}
	}
	sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
	fLog.write("   Not HAPI, %s"%sInternalMsg)	
	_pout(sOut.encode('utf8'))

##############################################################################
def sendTodo(fLog, sMsg, bSendContent=False):
	if bSendContent: 
		_pout("Content-Type: application/json; charset=utf-8")

	_pout("Status: 501 Not Implemented\r\n")
	
	dOut = {
		"HAPI":"1.1", 
		'status':{'code':1698, 
		'message':'Server Error - %s'%sMsg}
	}
	sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
	
	fLog.write('     TODO Error: %s'%sMsg)
	
	_pout(sOut.encode('utf8'))

##############################################################################
def paramCheck(fLog, sEndPoint, lLegal, form, bSendContent=False):
	"""Check a CGI FieldStorage object for illegal query parameters and send
	an error message if any are found"""
	
	for sKey in form.keys():
		if sKey not in lLegal:
			if bSendContent: 
				_pout("Content-Type: application/json; charset=utf-8")
			_pout('Status: 400 Bad Request\r\n')
			
			sReason = "GET parameter '%s' not allowed for %s endpoint in HAPI 1.1"%(
			          sKey, sEndPoint)
			fLog.write("   ERROR: %s"%sReason)
			dStatus = {
				'message': 'Bad request - unknown request parameter',
				'code':1401, 
				'x_reason':sReason
			}
			dOut = {"HAPI": "1.1", 'status':dStatus}	
			sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
			sys.stdout.write(sOut)
		
			return False
		else:
			# It is present, but check for shell injection problems and empty values
			sVal = form.getfirst(sKey,'')
			sReason = None
			if len(sVal) == 0:
				sReason = "Value of GET parameter '%s' is empty"%sKey
			if not sReason:
				for sTest in ('|','../','..\\', ':\\', '>', '&'):
					if sVal.find(sTest) != -1:
						sReason = "Value of GET parameter '%s' looks like a shell injection attack"%sKey
						break
			
			if sReason:
				if bSendContent: 
					_pout("Content-Type: application/json; charset=utf-8")
				_pout('Status: 400 Bad Request\r\n')
				fLog.write("   ERROR: %s"%sReason)
				dStatus = {
					'message': 'Bad request - unknown request parameter',
					'code':1401, 
					'x_reason':sReason
				}
				dOut = {"HAPI": "1.1", 'status':dStatus}	
				sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
				sys.stdout.write(sOut)
				return False
					
	return True

##############################################################################		
def reqCheck(fLog, sEndPoint, tLegal, form, bSendContent=False):
	"""Check that required parameters are present.  This function assumes that
	paramCheck() has also been used to verify the values this this functionality
	is not included here"""
	
	lKeys = form.keys()
	
	for sKey in tLegal:
		if sKey not in lKeys:
			if bSendContent: 
				_pout("Content-Type: application/json; charset=utf-8")
			_pout('Status: 400 Bad Request\r\n')
			sReason = "GET parameter '%s' is required for %s endpoint in HAPI 1.1"%(
			           sKey, sEndPoint)
			fLog.write("   ERROR: %s"%sReason)
			dStatus = {
				'message': 'Bad request - missing request parameter',
				'code':1697, 
				'x_reason':sReason
			}
			dOut = {"HAPI": "1.1", 'status':dStatus}	
			sOut = json.dumps(dOut, ensure_ascii=False, sort_keys=True, indent=3)
			sys.stdout.write(sOut)
			return False         	
	
	return True
























