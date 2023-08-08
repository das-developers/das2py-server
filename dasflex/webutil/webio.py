# make py2 code safer by preventing relative imports
from __future__ import absolute_import

import os
import sys
import time
import json

from os.path import join as pjoin

from . import errors as E

def pout(item):
	"""If input item is bytes, write them, if item is a string
	encode as utf-8 first"""	
	if isinstance(item, str):
		sys.stdout.buffer.write(item.encode('utf-8'))
	else:
		sys.stdout.buffer.write(item)
			
def flushOut():
	sys.stdout.buffer.flush()

##############################################################################
def getScriptUrl(dConf=None):
	"""Returns an ascii string (not utf-8) that provides the portion of the
	url that leads to this script, should work for any python CGI program.

	If you are offline AND the config is given AND it has SERVER_URL set, 
	then you can also get something from that area as well, but live 
	information from environment vars always takes precedence.
	"""

	if 'SERVER_NAME' not in os.environ:
		if dConf and ('SERVER_URL' in dConf):
			return dConf['SERVER_URL']

	sProto = 'http://'
	sPort = ''

	if os.getenv('HTTPS') != None:
		if os.getenv('HTTPS').lower() in ['1','on']:
			sProto = 'https://'
			
	if os.getenv('SERVER_PORT'):
		nPort = int(os.getenv('SERVER_PORT'))
	else:
		nPort = 80
		if sProto == 'https://':
			nPort = 443
		
	if (sProto == 'http://' and nPort != 80) or (sProto == 'https//' and nPort != 443):
		sPort = ':%d' % nPort
		
	return "%s%s%s%s"%(sProto, os.getenv('SERVER_NAME'), sPort, os.getenv('SCRIPT_NAME'))

##############################################################################
def getUrl():
	"""Returns the full request URL, this could fail with path parameters,
	but those have never been used around here (or most sites that I know of)
	"""
	
	sUri = os.getenv('PATH_INFO')
	if sUri == None:
		sUri = '/'
	
	return "%s%s"%(getScriptUrl(), sUri)

def httpNextYear():
	"""Return a string representation of a date one year from now according to
	RFC 1123 (HTTP/1.1).

	This is used to set expires headers for long term items that shouldn't
	be re-downloaded over and over even though they are sent via script
	"""
	import calendar
	import datetime

	dtNow = datetime.datetime.utcnow()
	dateNow = dtNow.date()

	delta = datetime.timedelta(
		days=366 if (
			(dtNow.month >= 3 and calendar.isleap(dtNow.year+1)) or
			(dtNow.month < 3 and calendar.isleap(dtNow.year))
		) else 365
	)

	dt = dtNow + delta

	weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]
	month = [
		"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
	][dt.month - 1]

	return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (
		weekday, dt.day, month, dt.year, dt.hour, dt.minute, dt.second
	)

##############################################################################
# Client communication globals

# I wish there was a more reliable way to do this, for example if all
# das2 apps set a user agent string that could be known to the server.

# g_lNotDas2App = ['firefox','explorer', 'safari', 'chrome', 'edge', 'konqueror']

def isBrowser():
	#if "HTTP_USER_AGENT" not in os.environ:
	#	return False
	
	#sAgent = os.environ['HTTP_USER_AGENT'].lower()
	#
	#for sTest in g_lNotDas2App:
	#	if sAgent.find(sTest) != -1:
	#		return True

	if "HTTP_ACCEPT" not in os.environ:
		return False
	if os.environ['HTTP_ACCEPT'].find("text/html") >= 0:
		return True
	
	return False

##############################################################################
# Printing errors in a format most useful to the client

# Only ever send one set of headers
g_bHdrSent = False

def dasExcept(sType, uOut, fLog=None, bHdrSent=False, sDasVer="2"):
	"""Send headers if needed, then replace error text newlines with 
	carrage-return newline pairs
	"""
	global g_bHdrSent
	
	if fLog != None:
		fLog.write(uOut)
	
	bClientIsBrowser = isBrowser()
	
	if not bHdrSent:
		if bClientIsBrowser:
			pout("Content-Type: text/plain; charset=utf-8\r\n\r\n")
		else:
			pout("Content-Type: text/vnd.das2.das2stream\r\n\r\n")
		g_bHdrSent = True
	
	# If headers were already sent before we entered this function then it
	# means we were in the middle of a response already, to be safe encode
	# the error as a das2 exception regardless of the client type
	
	if bClientIsBrowser and (not bHdrSent):
		pout(uOut)
	else:
		
		if not bHdrSent:
			if sDasVer.startswith("3"):
				sOut = "<stream version=\"3.0\" type=\"das-basic-stream\"/>\n"
				pout("|Sx||%d|%s"%(len(sOut), sOut))
			else:
				sOut = "<stream version=\"2.2\" />\n"
				pout("[00]%06d%s"%(len(sOut), sOut))

		uOut = uOut.strip()
		uOut = uOut.replace(u'\n', u'&#13;&#10;').replace(u'"', u"'")
		
		# Handle replacement of < and >
		uOut = uOut.replace(u'<', u'&lt;').replace(u'>',u'&gt;')
		
		if sDasVer.startswith("3"):
			sOut = u'<exception type="%s">\n%s\n</exception>\n'%(sType, uOut)
			pout("|Ex||%d|\n%s"%(len(sOut)+1, sOut))
		else:
			sOut = u'<exception type="%s" message="%s" />\n'%(sType, uOut)
			pout("[xx]%06d%s"%(len(sOut), sOut))
	
	sys.stdout.flush()
	return 3

##############################################################################
# Error types

def serverError(fLog, uOut, bHdrSent=False, sDasVer="2"):
	if not bHdrSent:
		pout("Status: 500 Internal Server Error\r\n")
	return dasExcept('ServerError', uOut, fLog, bHdrSent, sDasVer)

def todoError(fLog, uOut, bHdrSent=False, sDasVer="2"):
	if not bHdrSent:
		pout("Status: 501 Not Implemented\r\n")
	return dasExcept('NotImplemented', uOut, fLog, bHdrSent, sDasVer)

def queryError(fLog, uOut, bHdrSent=False, sDasVer="2"):
	if not bHdrSent:
		pout("Status: 400 Bad Request\r\n")
	return dasExcept('BadRequest', uOut, fLog, bHdrSent, sDasVer)
	
def forbidError(fLog, uOut, bHdrSent=False, sDasVer="2"):
	if not bHdrSent:
		pout("Status: 403 Forbidden\r\n", sDasVer="2")
	return dasExcept('Forbidden', uOut, fLog, bHdrSent, sDasVer)

def notFoundError(fLog, uOut, bHdrSent=False, sDasVer="2"):
	pout("Status: 404 Not Found\r\n")
	return dasExcept('NoSuchDataSource', uOut, fLog, bHdrSent, sDasVer)
	
	
# Taking any DasError exception and outputting the proper HTTP codes
def dasErr2HttpMsg(fLog, exp, bHdrSent=False):
	
	if isinstance(exp, E.ServerError):
		serverError(fLog, str(exp), bHdrSent)
	
	elif isinstance(exp, E.QueryError):
		queryError(fLog, str(exp), bHdrSent)
		
	elif isinstance(exp, E.TodoError):
		todoError(fLog, str(exp), bHdrSent)
	
	elif isinstance(exp, E.NotFoundError):
		notFoundError(fLog, str(exp), bHdrSent)
	
	elif isinstance(exp, E.ForbidError):
		forbidError(fLog, str(exp), bHdrSent)
	
	else:
		raise ValueError("Unknown DasError type")
	
	
##############################################################################
class DasLogFile(object):
	"""Replicates the functionality of the prepender script for the perl server.
	"""

	def __init__(self, sDir=None, sRmtAddr="direct_invoke"):
		"""Arguments: Log directory and remote client address"""
		
		if sDir == None or not os.path.isdir(sDir):
			self._file = sys.stderr
		else:
			nSuffix = (int(time.time()) / 86400) % 3
			sLogFile = 'das2.%s_%d.log'%(sRmtAddr, nSuffix)
			sLogPath = pjoin( sDir, sLogFile)
			self._file = open(sLogPath, 'a')
			
		self.sPrefix = "%s %d"%(time.asctime(), os.getpid())
		self.nLine = 0
		
	def newPrefix(self):
		self.sPrefix = "%s %d"%(time.asctime(), os.getpid())
		self.nLine = 0
		
	def fileno(self):
		return self._file.fileno()
		
	def write(self, sMsg):
	
		if isinstance(sMsg, str):
			lMsg = sMsg.split(u'\n')
			
			for sLine in lMsg:
				if len(sLine.strip()) > 0:

					sOut = '[%s %4d] %s\n'%(self.sPrefix, self.nLine, sLine)
					self._file.buffer.write(sOut.encode('utf-8'))
					self.nLine += 1

		else:
			lMsg = sMsg.split(b'\n')
			
			for xLine in lMsg:
				if len(xLine.strip()) > 0:
					
					sPre = '[%s %4d] '%(self.sPrefix, self.nLine)
					self._file.buffer.write(sPre.encode('utf-8'))					
					self._file.buffer.write(xLine)
					self._file.buffer.write(b'\n')
					self.nLine += 1

		self._file.flush()

		
	def close(self):
		if self._file != sys.stderr:
			self._file.close()

# ########################################################################## #

def fileOut(fLog, lHeaders, sPath, sErrMsg=None):
	"""Send a web response that's just a single file and the headers.  If 
	the file can't be sent, then a not-found error is transmitted instead.

	Returns: 0 if everything went well, 1 otherwise
	"""

	try:
		fIn = open(sPath, 'rb')
	except:
		pout("Status: 404 Not Found\r\n\r\n")
		if sErrMsg:
			pout(sErrMsg)
			fLog.write("File %s not found on this server"%sPath)
		return 1
	
	try:
		sHdrs = "%s\r\n\r\n"%('\r\n'.join(lHeaders))
		pout(sHdrs)
		flushOut()

		xBytes = fIn.read(8192)
		while len(xBytes) > 0: 
			pout(xBytes)
			xBytes = fIn.read(8192)

	except Exception as e:
		# Nothing much we can do, data has already went out the door, just log it
		fLog.write(str(e))
		return 1
	
	return 0

def d2sOut(fLog, lHeaders, sPath, sErrMsg):
	"""Send a web response that just a das2 stream on disk and it's headers.
	If an error occurs, send a message as a das2 error packet
	"""

	try:
		fIn = open(sPath, 'rb')
	except:
		if not sErrMsg: sErrMsg = "File %s not found on this server"%sPath
		return notFoundError(fLog, sErrMsg)

	try: 
		sHdrs = "%s\r\n\r\n"%('\r\n'.join(lHeaders))
		pout(sHdrs)

		xBytes = fIn.read(8192)
		while len(xBytes) > 0:
			pout(xBytes)
			xBytes = fIn.read(8192)

	except Exception as e:
		# Nothing much we can do, data has already went out the door, just log it
		fLog.write(str(e))
		return 1

	return 0