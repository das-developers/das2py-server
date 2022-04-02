"""Handle Das2 Authentication and Authorization"""

import os
import base64
import crypt
import os.path

import unittest

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
			sAuthPlain = base64.b64decode(sAuth[6:]).decode('utf-8')
			lAuth = sAuthPlain.split(':')
			return( lAuth[0], ':'.join(lAuth[1:]) )
			
	else:
		fLog.write("Required variable HTTP_AUTHORIZATION no available to script!\n")
		fLog.write("Check you sever config (Hint: Apache need a mod_rewrite rule to set this\n")
			
	return (None, None)


# ########################################################################### #
# Address to Address Range matching 


def _mkMask(fLog, nBytes, nOnesBits):
	"""Generate a bytearray that starts with all binary 1's and then switches to 0's 

	Args:
		fLog - An object with a .write method that takes as string
		nBytes - The number of bytes (not bits) in the output bytearray
		nOnesBits - In binary, this many bits will be set to 1 after that
			all remaining bits in the the returned bytearray will be 0.

	Returns:
		bytearray
	"""

	xRet = bytearray([0]*nBytes)

	if (nOnesBits / 8) > nBytes:
		fLog.write("Not enough output bytes for %d 1's bits"%nOnesBits)
		return None

	if nOnesBits < 0:
		fLog.write("Negative number of 1's bits: %d "%nOnesBits)
		return None

	# Start with full byte setting, depends on truncation
	for i in range(nOnesBits // 8):
		xRet[i] = 0xFF

	# Handle the last partial byte's worth of bits
	if ((nOnesBits / 8) - (nOnesBits // 8)) > 0:
		
		i = nOnesBits // 8  # Index depends on truncation

		nLeft = nOnesBits - ((nOnesBits // 8) * 8)

		# "Big-endian" bits mapping
		dRep = { 1: 0x80, 2: 0xC0, 3: 0xE0, 4: 0xF0, 5: 0xF8, 6: 0xFC, 7: 0xFE }

		xRet[i] = dRep[nLeft]

	return xRet


def parseIP4Address(fLog, sAddr):
	"""Returns: A bytearray containing the address"""

	if not sAddr:
		fLog.write("Empty IPv4 address '%s'"%sAddr)
		return None

	lParts = [s.strip() for s in sAddr.split('.')]
	if len(lParts) == 0 or len(lParts) > 4:
		fLog.write("Empty IPv4 address '%s'"%sAddr)
		return None		

	xAddr = bytearray([0]*4)

	for i in range(len(lParts)):
		if not lParts[i]:
			fLog.write("Invalid IPv4 address '%s'"%sAddr)
		try:
			n = int(lParts[i], 10)
		except ValueError:
			fLog.write("Invalid IPv4 address '%s"%sAddr)
			return None

		xAddr[i] = n

	return xAddr
	

def parseIP6Address(fLog, sAddr):
	"""Parse an IPv6 address with standard shortcuts (aka :: ). Assumes hexdecimal
	"""

	if not sAddr:
		fLog.write("Empty IPv6 address '%s'"%sAddr)
		return None


	lSides = sAddr.split('::')
	sFront = lSides[0].strip()
	if len(lSides) == 1:
		sBack = ''
	elif len(lSides) == 2:
		sBack = lSides[1].strip()
	else:
		fLog.write("Invalid IPv6 address '%s'"%sAddr)
		return None

	lDest = [0]*8; # There are 8 16-bit sections to an IPv4 address

	lFront = []
	lBack = []
	if len(sFront) > 0: lFront = [s.strip() for s in sFront.split(':') ]
	if len(sBack) > 0:  lBack =  [s.strip() for s in sBack.split(':')  ]

	if (len(lFront) + len(lBack)) > 8:
		fLog.write("Invalid IPv6 address '%s'"%sAddr)
		return None		
	
	i = 0
	for sPart in lFront:
		try:
			n = int(sPart, 16)
		except ValueError:
			fLog.write("Invalid IPv6 address '%s'"%sAddr)
			return None

		lDest[i] = n
		i += 1

	i = 7
	for sPart in reversed(lBack):
		try:
			n = int(sPart, 16)
		except ValueError:
			fLog.write("Invalid IPv6 address '%s'"%sAddr)
			return None

		lDest[i] = n
		i -= 1

	for n in lDest:
		if (n > 0xFFFF) or (n < 0):
			fLog.write("Invalid IPv6 address '%s'"%sAddr)
			return None


	lBytes = [0]*16;
	for i in range(8):
		lBytes[2*i]     = (lDest[i] >> 8) & 0xFF
		lBytes[2*i + 1] = lDest[i] & 0xFF

	return bytearray(lBytes)

def parseIP4Range(fLog, sNet):
	"""Parse an IPv4 network string of *decimal* digits into two bytearray objects"""

	if not sNet:
		fLog.write("Empty network address provided")
		return (None, None)

	lRng = [s.strip() for s in sNet.split('/')]
	sNet = lRng[0]

	if len(sNet) == 0:
		fLog.write("Empty network address portion in '%s'"%sNet)
		return (None, None)

	xNet = parseIP4Address(fLog, sNet)

	sSig = ""
	if len(lRng) > 0:
		sSig = lRng[1]

	if len(sSig) == 0:
		xMask = bytearray([1]*4)
	else:
		try:
			nSig = int(sSig,10)
		except ValueError:
			fLog.write("Couldn't convert network significant bits in network range %s, ")
			return (None, None)
		xMask = _mkMask(fLog, 4, nSig)
		if not xMask:
			return (None, None)

	xMaskNet = bytearray(
		[a & m for a, m in zip(xNet, xMask)] # 'cause "xNet & xMast" would be too easy :(
	)

	return (xMaskNet, xMask)


def parseIP6Range(fLog, sNet):
	"""Parse an IPv6 network string of *hexidecimal* digits into two bytearray
	objects.

	Args:
		fLog - A logger object

		sNet - A string in standard IPv6 forms, optionally followed by the number
			of network bits in the address.  Some examples:
			::1  ::1/128  2620:0:e50::/48 2620:0000:0e50:0000:0000:0000:0000:000/48

	Returns: ( Network - bytearray, Netmask - bytearray)
		The first array contains the network portion of the range, the second
		contains the network mask.  If the address could net be parsed,
		(None,None) is returned
	"""

	if not sNet:
		fLog.write("Empty network address provided")
		return (None, None)

	lRng = [s.strip() for s in sNet.split('/')]
	sNet = lRng[0]

	if len(sNet) == 0:
		fLog.write("Empty network address portion in '%s'"%sNet)
		return (None, None)

	xNet = parseIP6Address(fLog, sNet)

	sSig = ""
	if len(lRng) > 1:
		sSig = lRng[1]

	if len(sSig) == 0:
		xMask = bytearray([1]*16)
	else:
		try:
			nSig = int(sSig,10)
		except ValueError:
			fLog.write("Couldn't convert network significant bits in network range %s, ")
			return (None, None)
		xMask = _mkMask(fLog, 16, nSig)

	xMaskNet = bytearray(
		[a & m for a, m in zip(xNet, xMask)] # 'cause "xNet & xMast" would be too easy :(
	)

	return (xMaskNet, xMask)


def addrInRange(fLog, sAddr, ranges):
	"""Check to see if an address is in a set of address ranges.

	Works with intermixed IPv6 and IPv4 addresses.

	Args:
		sAddr - The address to check.  Assumed to be an IPv4 or IPv6 range

		ranges - Either a whitespace separated list of address ranges, or an
			actual python list containing the forms:
					 
		    DDD.DDD.DDD.DDD/bits
		    HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH:HHHH/bits

		    Common IPv4 and IPv6 short forms are acceptable, for example:

		    192.168/16
		    ::1
		    2620:0:e50::/48

		fLog - Anything with 
	"""

	if not sAddr:
		fLog.write("Empty address")
		return False

	if not isinstance(ranges, list): 
		ranges = [s.strip() for s in ranges.split() ]
		ranges = [s for s in ranges if len(s) > 0]

	if len(ranges) == 0:
		return False

	if ':' in sAddr:
		xAddr = parseIP6Address(fLog, sAddr)
		if not xAddr: return False

		for sRng in ranges:
			if ':' in sRng:
				(xRng, xMask) = parseIP6Range(fLog, sRng)
				if not xRng: return False

				# Bytearray doesn't overload '&', so this is  "xAddr & aMask" in 
				# much less readable form :-( 
				xMaskAddr = bytearray( [a & m for a, m in zip(xAddr, xMask)] )

				if xMaskAddr == xRng:
					return True

	else:
		xAddr = parseIP4Address(fLog, sAddr)
		if not xAddr: return False

		for sRng in ranges:
			if ':' not in sRng:
				(xRng, xMask) = parseIP4Range(fLog, sRng)
				if not xRng: return False

				xMaskAddr = bytearray( [a & m for a, m in zip(xAddr, xMask)] )

				if xMaskAddr == xRng:
					return True

	return False


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
		fIn = open(dConf['USER_PASSWD'], 'r')
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
		fIn = open(dConf['USER_GROUP'], 'r')
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

def checkAgeAccess(dConf, fLog, sResource, sValue, sBeg, sEnd):
	"""Checks to see if the query string asks for data that is old
	enough.  Only works for Das 2.1 queries right now.
	"""
	
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

def checkGroupAccess(dConf, fLog, sResource, sValue):
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


def checkUserAccess(dConf, fLog, sResource, sValue):
	"""Checks to see if the given user validates"""
	
	(sUser, sPasswd) = _getUserPasswd(fLog)
	if sUser == None:
		return AUTH_FAIL
		
	if sUser != sValue:
		fLog.write("   Authorization: Username mismatch")
		return AUTH_FAIL
	
	return authenticate(dConf, fLog, sUser, sPasswd)

##############################################################################
def authorize(dConf, fLog, sResource, sAccess, sBeg=None, sEnd=None):
	"""
	Handle authorization for a Das2 resource
	
	dConf - The configuration dictionary, The keywords USER_PASSWD and
	        possibly USER_GROUP are consulted from this.  If those strings
	        aren't present in the configuration file authorization will
	        likely fail.
			  	
	fLog - The logger object
	
	sResource - A name for this resource to put in log file messages so 
	       that problems may be found quickly. 
	
	sAccess - The contents of an authorization string from the DSDF or DSIF
	       file.  All access methods are attempted, if at least one
	       succeeds, then the return value will be True.  If this string
			 is None or a length 0 string then access is automatically
			 granted.  If parsing the sAccess string fails, the return 
			 value is false, and the failure to parse is also logged.

	sBeg - The start time of the request, if None age based access will
	       always fail.

	sEnd - The end time of the request, if None age based access will
	       always fail.

	
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
		if 'ALLOW_TEST_FROM' in dConf and 'REMOTE_ADDR' in os.environ:
			if addrInRange(fLog, os.environ['REMOTE_ADDR'], dConf['ALLOW_TEST_FROM']):
				fLog.write("   Authorization: Host %s allowed access"%os.environ['REMOTE_ADDR'])
				return AUTH_SUCCESS
		

		nRet = AUTH_SUCCESS	
		if sCheckType == 'AGE' and sBeg and sEnd:
			fLog.write("   Authorization: Checking access by data AGE")
			nRet = checkAgeAccess(dConf, fLog, sResource, sValue, sBeg, sEnd)
		elif sCheckType == 'GROUP':
			fLog.write("   Authorization: Checking access by GROUP membership")
			nRet = checkGroupAccess(dConf, fLog, sResource, sValue)
		elif sCheckType == 'USER':
			fLog.write("   Authorization: Checking access by USER account")
			nRet = checkUserAccess(dConf, fLog, sResource, sValue)				
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


# ########################################################################## #
# to run these tests from the build area issue:
#
#    python3 -m unittest das2server/util/auth.py 
#
# from the root das2-pyserver directory

class TestAddrParsing(unittest.TestCase):

	# Define myself as a logger, which writes nothing
	def write(self, sMessage):
		#import sys
		#sys.stderr.write("%s\n"%sMessage)
		pass  # Sometimes I test thing that should fail!

	def test_addr4(self):
		sAddr = '10.14.237.62'
		xAddr = bytearray([10, 14, 237, 62])
		self.assertEqual( parseIP4Address(self, sAddr), xAddr)

		sAddr = ''
		self.assertEqual( parseIP4Address(self, sAddr), None)

		sAddr = 'a.d.ed.3e'
		self.assertEqual( parseIP4Address(self, sAddr), None)

		sAddr = '255.255'
		xAddr = bytearray([0xFF, 0xFF, 0, 0])
		self.assertEqual( parseIP4Address(self, sAddr), xAddr)

	def test_addr6(self):
		sAddr = '::1'
		xAddr = bytearray([0]*15 + [1])
		self.assertEqual( parseIP6Address(self, sAddr), xAddr)

		sAddr = 'AAAA:BBBB::'
		xAddr = bytearray([0xAA]*2 + [0xBB]*2 + [0]*12)
		self.assertEqual( parseIP6Address(self, sAddr), xAddr)

		sAddr = '0001:0203:0405:0607:0809:0a0b:0c0d:0e0f'
		xAddr = bytearray(list(range(16)))
		self.assertEqual( parseIP6Address(self, sAddr), xAddr)

	def test_net4(self):
		sNet = '127.0.0.1/8'
		xNet  = bytearray([127,0,0,0])
		xMask = bytearray([255, 0, 0, 0])
		self.assertEqual( parseIP4Range(self, sNet), (xNet, xMask))

		sNet = '128.0.0.1/33'
		self.assertEqual( parseIP4Range(self, sNet), (None, None))

		sNet = '255.255.33.127/25'
		xNet = bytearray([255, 255, 33, 0x00])
		xMask  = bytearray([0xFF,0xFF,0xFF,0x80])
		self.assertEqual( parseIP4Range(self, sNet), (xNet, xMask))

	def test_net6(self):
		sNet = '::1/128'
		xNet = bytearray([0]*15 + [1])
		xMask = bytearray([0xFF]*16)
		self.assertEqual( parseIP6Range(self, sNet), (xNet, xMask))

		sNet = "2620:0:e51::/47"
		xNet = bytearray([0x26, 0x20, 0, 0, 0x0e, 0x50] + [0]*10)
		xMask = bytearray( [0xFF]*5 + [0xFE] + [0]*10)
		self.assertEqual( parseIP6Range(self, sNet), (xNet, xMask))

	def test_inrange(self):

		ranges = ["::1", "127.0.0.1/8", "10.14.0.0/16", "fe80::/10"]
		sAddr = "fe80::0807:0605:0403:0201"

		self.assertTrue(  addrInRange(self, sAddr, ranges))
		self.assertFalse( addrInRange(self, "192.168.1.1", ranges))
		self.assertFalse( addrInRange(self, "2620:0:e50:1::", ranges) )

if __name__ == '__main__':
	unittest.main()