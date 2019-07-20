"""Handle Das2 Authentication"""

import os
import base64
import crypt
import os.path

import das2

AUTH_SUCCESS = 0
AUTH_FAIL    = 1
AUTH_SVR_ERR  = 2

##############################################################################
# Helpers

def _ageToTime(fLog, sResource, sAge):
	sAge = sAge.strip()
	
	dtLockPt = das2.DasTime.now()
	bAdjusted = False
	
	try:
		sAccmVal = ""
		for c in sAge:
			c = c.lower()
			if c.isdigit():
				sAccmVal += c
			elif c == 'y':
				if sAccmVal != "":
					nDec = int(sAccmVal, 10)
					dtLockPt.adjust(-nDec)
					sAccmVal = ''
					bAdjusted = True
			elif c == 'm':
				if sAccmVal != "":
					nDec = int(sAccmVal, 10)
					dtLockPt.adjust(0, -nDec)
					sAccmVal = ''
					bAdjusted = True
			elif c == 'd':
				if sAccmVal != "":
					nDec = int(sAccmVal, 10)
					dtLockPt.adjust(0, 0, -nDec)
					sAccmVal = ''
					bAdjusted = True
			elif c == 'h':
				if sAccmVal != "":
					nDec = int(sAccmVal, 10)
					dtLockPt.adjust(0, 0, 0, -nDec)
					sAccmVal = ''
					bAdjusted = True
			else:
				raise ValueError("Unexpected Units value '%s', in '%s'"%(c, sAge))
				
	except ValueError as e:
		bAdjusted = False
		
	if not bAdjusted:
		fLog.write("   Authorization: ERROR! In AGE value '%s' for %s"%(
		           sAge, sResource))
		return None
	else:
		return dtLockPt		


def _getUserPasswd(fLog):
	
	if 'HTTP_AUTHORIZATION' in os.environ:
		sAuth = os.environ['HTTP_AUTHORIZATION']
		
		if sAuth.startswith('Basic') and len(sAuth) > 12:
			sAuthPlain = base64.b64decode(sAuth[6:])
			lAuth = sAuthPlain.split(':')
			return( lAuth[0], ':'.join(lAuth[1:]) )
			
	else:
		fLog.write("Required variable HTTP_AUTHORIZATION no available to script!\n")
		fLog.write("Check you sever config (Hint: Apache need a mod_rewrite rule to set this\n")
			
	return (None, None)
	

##############################################################################
# Nitty gritty of user authentication

def authenticate(dConf, fLog, sUser, sPasswd):
	
	if 'USER_PASSWD' not in dConf: 
		fLog.write("   Authorization: ERROR! Configuration entry 'USER_PASSWD' "+\
		           "missing, can't authenticate Das2 users")
		return AUTH_SVR_ERR
		
	if not os.path.isfile(dConf['USER_PASSWD']):
		fLog.write("   Authorization: ERROR! Password file '%s' is missing."%dConf['USER_PASSWD'])
		return AUTH_SVR_ERR
	
	try:
		fIn = file(dConf['USER_PASSWD'], 'rb')
	except IOError:
		fLog.write("   Authorization: ERROR! Can't open password file, '%s'"%dConf['USER_PASSWD'])
		return AUTH_SVR_ERR
	
	for sLine in fIn:
		sLine = sLine.strip()
		if len(sLine) == 0:
			continue
		lLine = sLine.split(':')
		if len(lLine) < 2:
			fLog.write("   Authorization: ERROR! Improperly formatted password file, %s"%dConf['USER_PASSWD'])

		if len(lLine) > 1 and lLine[0] == sUser:
			sCrypt = ':'.join(lLine[1:])         # Passwd string may have hand a ':'
			                                     # character in it
			sTest = crypt.crypt(sPasswd, sCrypt)
			
			#fLog.write("Test Crypt: %s"%sTest)
			
			if sTest == sCrypt:
				fLog.write("   Authorization: User %s authenticated"%sUser)
				return AUTH_SUCCESS
				
	fLog.write("   Authorization: Cipher match failure for user %s"%sUser)
	return AUTH_FAIL

##############################################################################

def getUserGroups(dConf, fLog, sUser):
	"""Returns:
	
	   (nStatus, lGroups)
	
	Where nStatus is one of: 
	
	  AUTH_SVR_ERR - Can't read group file
	  AUTH_SUCCESS - Read group file, lGroups has valid data
	  
	Note: It is possible that the user isn't in any groups, so lGroups may
	      be a zero length list
	"""
	if 'USER_GROUP' not in dConf: 
		fLog.write("   Authorization: ERROR! Configuration entry 'USER_GROUP'"+\
		           " missing, can't authenticate Das2 users")
		return (AUTH_SVR_ERR, None)
	
	if not os.path.isfile(dConf['USER_GROUP']):
		fLog.write("   Authorization: ERROR! Group file '%s' is missing."%dConf['USER_GROUP'])
		return (AUTH_SVR_ERR, None)

	lGroups = []

	try:
		fIn = file(dConf['USER_GROUP'], 'rb')
	except IOError:
		fLog.write("   Authorization: ERROR! Can't open group file, '%s'"%dConf['USER_GROUP'])
		return (AUTH_SVR_ERR, None)
		
	for sLine in fIn:
		sLine = sLine.strip()
		if len(sLine) == 0:
			continue
		lLine = sLine.split(':')
		if len(lLine) != 4:
			fLog.write("   Authorization: ERROR! Expected 4 sections in each line of %s"%dConf['USER_GROUP'])
			return (AUTH_SVR_ERR, None)
					
		if len(lLine[0]) == 0:
			fLog.write("   Authorization: ERROR! Bad group name in %s"%dConf['USER_GROUP'])
			return (AUTH_SVR_ERR, None)
		
		lUsers = lLine[3].split(',')
		
		if sUser in lUsers:
			lGroups.append( lLine[0])
		
	return (AUTH_SUCCESS, lGroups)
	

##############################################################################
# Standard interface for check methods
#
#  dConf - The configuration dictionary
#  fLog  - The logger object
#  form  - The form values
#  sResource - A name to call this resource in error messages
#  sValue - The value to check
#  
#  os.environ - Where to get certian CGI gateway values

def checkAgeAccess(dConf, fLog, form, sResource, sValue):
	"""Checks to see if the query string asks for data that is old
	enough.  Only works for Das 2.1 queries right now.
	"""
	
	(sBeg, sEnd) = (form.getfirst('start_time',''), form.getfirst('end_time',''))
	if sBeg == '' or sEnd == '':
		(sBeg, sEnd) = (form.getfirst('time.min',''), form.getfirst('time.max',''))
		if sBeg == '' or sEnd == '':
			fLog.write("   Authorization: Can't determine query time range, start_time or end_time missing")
			return AUTH_FAIL
	
	try:
		dtBeg = das2.DasTime(sBeg)
		dtEnd = das2.DasTime(sEnd)
	except ValueError as e:
		fLog.write("   Authorization: Bad Query can't parse time range (%s to %s)"%(sBeg, sEnd))
		return AUTH_FAIL
	
	# Get age in seconds
	dtLockBeg = _ageToTime(fLog, sResource, sValue)
	fLog.write("   Authorization: Lockout begins %s, query ends %s."%(
	            str(dtLockBeg)[:-7], str(dtBeg)[:-7]))
					
	if dtLockBeg == None:
		return AUTH_SVR_ERR
		
	if dtBeg <= dtEnd and dtEnd < dtLockBeg:
		return AUTH_SUCCESS
	
	return AUTH_FAIL

def checkGroupAccess(dConf, fLog, form, sResource, sValue):
	"""Checks to see if the given user is in an authorized group"""

	(sUser, sPasswd) = _getUserPasswd(fLog)
	fLog.write("User is: %s"%sUser)
	if sUser == None:
		return AUTH_FAIL
	
	nRet = authenticate(dConf, fLog, sUser, sPasswd)
	if nRet != AUTH_SUCCESS:
		return nRet
	
	(nRet, lGroups) = getUserGroups(dConf, fLog, sUser)
	if nRet != AUTH_SUCCESS:
		return nRet
	
	if not (sValue in lGroups):
		fLog.write("   Authorization: User %s is not in group %s"%(sUser, sValue))
		return AUTH_FAIL
	else:
		return AUTH_SUCCESS


def checkUserAccess(dConf, fLog, form, sResource, sValue):
	"""Checks to see if the given user validates"""
	
	(sUser, sPasswd) = _getUserPasswd(fLog)
	if sUser == None:
		return AUTH_FAIL
		
	if sUser != sValue:
		fLog.write("   Authorization: Username mismatch")
		return AUTH_FAIL
	
	return authenticate(dConf, fLog, sUser, sPasswd)

##############################################################################
def authorize(dConf, fLog, form, sResource, sAccess):
	"""
	Handle authorization for a Das2 resource
	
	dConf - The configuration dictionary, The keywords USER_PASSWD and
	        possibly USER_GROUP are consulted from this.  If those strings
	        aren't present in the configuration file authorization will
	        likely fail.
			  	
	fLog - The logger object
	
	form - the cgi.FieldStorage object that contains the GET information
	       the start_time and end_time in the form may be consulted if the
	       'AGE' based authorization was specified in sAccess.  Also for		 
	
	sResource - A name for this resource to put in log file messages so 
	       that problems may be found quickly. 
	
	sAccess - The contents of an authorization string from the DSDF or DSID
	       file.  All access methods are attempted, if at least one
	       succeeds, then the return value will be True.  If this string
			 is None or a length 0 string then access is automatically
			 granted.  If parsing the sAccess string fails, the return 
			 value is false, and the failure to parse is also logged.

	
	In addition the os.environ dictionary is consulted to get the value
	of the 'HTTP_AUTHORIZATION' variable.  Note, the name of this variable
	can be changed in the config if desired.
	
	Returns:
	
	  0 - If at least one check passes
	  1 - If all access checks are processed normally but none succeed.
	  2 - If there is a sever error when processing the request.
	"""
	
	if sAccess == None or len(sAccess) == 0:
		return AUTH_SUCCESS
	
	if len(sAccess) < 3:
		fLog.write("  Authorization: ERROR! Syntax error in access list '%s' in datasource %s"%(
		           sAccess, sResource))
		return AUTH_SVR_ERR
	
	lAccess = sAccess.split('|')
	for sCondition in lAccess:
	
		lTmp = sCondition.split(':')
		if len(lTmp) < 2:
			fLog.write("  Authorization: ERROR! Syntax error in access condition '%s' in access list '%s' in datasource %s"%(
			           sCondition, sAccess, sResource))
			return AUTH_SVR_ERR
		
		sCheckType = lTmp[0].upper().strip()
		sValue = ':'.join(lTmp[1:])
		
		# See if the request comes from a system that has been configured with
		# auto-allow access:
		if 'TEST_FROM' in dConf and 'REMOTE_ADDR' in os.environ:
			lHosts = dConf['TEST_FROM'].split()
			for i in range(0, len(lHosts)):
				lHosts[i] = lHosts[i].strip()
			
			if os.environ['REMOTE_ADDR'] in lHosts:
				fLog.write("   Authorization: Host %s allowed access"%os.environ['REMOTE_ADDR'])
				return AUTH_SUCCESS
		
		
		nRet = AUTH_SUCCESS	
		if sCheckType == 'AGE':
			fLog.write("   Authorization: Checking access by data AGE")
			nRet = checkAgeAccess(dConf, fLog, form, sResource, sValue)
		elif sCheckType == 'GROUP':
			fLog.write("   Authorization: Checking access by GROUP membership")
			nRet = checkGroupAccess(dConf, fLog, form, sResource, sValue)
		elif sCheckType == 'USER':
			fLog.write("   Authorization: Checking access by USER account")
			nRet = checkUserAccess(dConf, fLog, form, sResource, sValue)				
		else:
			fLog.write("  Authorization: ERROR! Auth method '%s' is unknown in access list '%s' for datasource %s"%(
			           sCheckType, sAccess, sResource))
			return AUTH_SVR_ERR
		
		# If the check passes or we get a server failure message return now.
		if nRet != AUTH_FAIL:
			if nRet == AUTH_SUCCESS:
				fLog.write("   Authorizaiton: Access granted")
			return nRet
	
	fLog.write("   Authorizaiton: Access denied")
	return AUTH_FAIL
