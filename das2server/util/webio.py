# make py2 code safer by preventing relative imports
from __future__ import absolute_import

import os
import sys
import time
import codecs

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

##############################################################################
# mime type globals 

# Final entries are
# Content-Type 
# inline or attachment
# file extension

# Maybe add support for CDF, since a series of CDF files is fine
# to present to the user.

#  ('application/x-cdf', 'attachment', 'cdf')

MIME = 0
INLINE = 1
EXTENSION = 2

g_dDasClientMime = { 
	'text': 
		{'d2s': ('text/vnd.das2.das2stream; charset=utf-8', 'inline', 'd2t'),
		 'qds': ('text/vnd.das2.qstream; charset=utf-8', 'inline', 'qdt'),
		 'vap': ('application/x-autoplot-vap+xml', 'attachment', 'vap'),
		 'csv': ('text/csv','attachment','csv')
		 },
				 
	'bin':
		{'d2s': ('application/vnd.das2.das2stream', 'attachment', 'd2s'),
		 'qds': ('application/vnd.das2.qstream', 'attachment', 'qds'),
       'vap': ('application/vnd.autoplot.vap+xml', 'attachment', 'vap'),
		},
		 
	'image':
		{'d2s': ('image/png', 'inline', 'png'),
		 'qds': ('image/png', 'inline', 'png')}
}

g_dBrowserMime = {
	'text': 
		{'d2s': ('text/plain; charset=utf-8', 'inline', 'd2t'),
		 'qds': ('text/plain; charset=utf-8', 'inline', 'qdst'),
       'vap': ('application/x-autoplot-vap+xml', 'attachment', 'vap'), 
		 'csv': ('text/csv','attachment','csv')
		},
				 
	'bin':g_dDasClientMime['bin'],

	'image':g_dDasClientMime['image']
}

# Top level mime switch toggled off of 'isBrowser' function

g_dMime = {True:g_dBrowserMime, False:g_dDasClientMime}


##############################################################################
# Client communication globals

# I wish there was a more reliable way to do this, for example if all
# das2 apps set a user agent string that could be known to the server.

g_lNotDas2App = ['firefox','explorer', 'safari', 'chrome', 'edge', 'konqueror']

def isBrowser():
	if "HTTP_USER_AGENT" not in os.environ:
		return False
	
	sAgent = os.environ['HTTP_USER_AGENT'].lower()
	
	for sTest in g_lNotDas2App:
		if sAgent.find(sTest) != -1:
			return True
	
	return False


##############################################################################
def getOutputMime(sOutCat, sOutFmt='d2s'):
	"""Getting a mime-type for a return object based on it output category and
	optionally the type of data generated by the reader
	
	sOutCat - The category of output, one of 'text','bin','image'
	sOutFmt - When the output is text or bin, also specify if you are sending
	          a das2stream or a Qstream, should be one of 'd2s' or 'qds'
				 
	Returns the following 3-strings in a tuple:
	  
	     ( mime-type, content disposition, filename extension)
	
	For the text types charset=utf-8 is added
	"""
	
	return g_dMime[isBrowser()][sOutCat][sOutFmt]
	
##############################################################################
def getMimeByExt(sPath):
	"""Returns a mime-type string for one of our files types, or None if
	the file-type isn't recognized"""
	
	i = sPath.rfind('.')
	if i == -1:
		return None
		
	sExt = sPath[i+1:].lower()
	
	if sExt == 'qdst': 
		return g_dMime[isBrowser()]['text']['qds']
		
	if sExt == 'd2t':
		return g_dMime[isBrowser()]['text']['d2s']
	
	if sExt == 'qds': 
		return g_dMime[isBrowser()]['bin']['qds']
		
	if sExt == 'd2s':
		return g_dMime[isBrowser()]['bin']['d2s']
		
	if sExt == 'vap':
		return g_dMime[isBrowser()]['text']['vap']
		
	if sExt == 'csv':
		return g_dMime[isBrowser()]['text']['csv']
	
	return None

##############################################################################
# Printing errors in a format most useful to the client

# Only ever send one set of headers
g_bHdrSent = False

def dasExcept(sType, uOut, fLog=None, bHdrSent=False):
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
			sOut = "<stream version=\"2.2\" />\n"
			pout("[00]%06d%s"%(len(sOut), sOut))

		uOut = uOut.replace(u'\n', u'&#13;&#10;').replace(u'"', u"'")
		
		# Handle replacement of < and >
		uOut = uOut.replace(u'<', u'&lt;').replace(u'>',u'&gt;')
		
		uOut = u'<exception type="%s" message="%s" />\n'%(sType, uOut)
		sOut = uOut.encode('utf-8')
		pout("[xx]%06d"%len(sOut))
		pout(sOut)
	
	sys.stdout.flush()

##############################################################################
# Error types

def serverError(fLog, uOut, bHdrSent=False):
	if not bHdrSent:
		pout("Status: 500 Internal Server Error\r\n")
	dasExcept('InternalServerError', uOut, fLog, bHdrSent)

def todoError(fLog, uOut, bHdrSent=False):
	if not bHdrSent:
		pout("Status: 501 Not Implemented\r\n")
	dasExcept('NotImplemented', uOut, fLog, bHdrSent)

def queryError(fLog, uOut, bHdrSent=False):
	if not bHdrSent:
		pout("Status: 400 Bad Request\r\n")
	dasExcept('BadRequest', uOut, fLog, bHdrSent)
	
def forbidError(fLog, uOut, bHdrSent=False):
	if not bHdrSent:
		pout("Status: 403 Forbidden\r\n")
	dasExcept('Forbidden', uOut, fLog, bHdrSent)

def notFoundError(fLog, uOut, bHdrSent=False):
	pout("Status: 404 Not Found\r\n")
	dasExcept('NoSuchDataSource', uOut, fLog, bHdrSent)
	
	
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




