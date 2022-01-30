"""Default handler for sending out peers data"""

import sys
import os

# Python 2/3 change
try:
	from ConfigParser import SafeConfigParser
except ImportError:
	from configparser import SafeConfigParser

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.handlers.intro.py for a decription of this function
	interface
	"""
	
	if 'PEERS_FILE' not in dConf:
		U.webio.serverError(fLog, u"Create an INI file contaning known das2 servers, then "
		      "add a PEERS_FILE key to \n%s to point to your peers list."%dConf['__file__'])
		return 17
	
	sPeersFile = dConf['PEERS_FILE']
	
	if not os.path.isfile(sPeersFile):
		U.webio.serverError(fLog, u"Move etc/das2peers.ini.example to %s and customize"%sPeersFile)
		return 17
	
	psr = SafeConfigParser()
	psr.read(dConf['PEERS_FILE'])
	
	U.webio.pout("Content-Type: text/xml; charset=utf-8\r\n\r\n")
			
	U.webio.pout('<?xml version="1.0" encoding="UTF-8" ?>\n')
	U.webio.pout('<?xml-stylesheet type="text/xsl" href='
	     '"%s/static/das2server.xsl"?>\n'%os.environ['SCRIPT_NAME'])
	U.webio.pout('<das2server>\n')
	U.webio.pout('  <peers>\n')
	
	lSec = psr.sections()
	lSec.sort()
	
	for sSec in lSec:
		U.webio.pout('    <server>\n')
		U.webio.pout('      <name>%s</name>\n'%sSec)
		if psr.has_option(sSec, 'url'):
			U.webio.pout('      <url>%s</url>\n'%psr.get(sSec, 'url'))
		if psr.has_option(sSec, 'description'):
			U.webio.pout('      <description>%s</description>\n'%psr.get(sSec, 'description'))
		U.webio.pout('    </server>\n')
	
	U.webio.pout('  </peers>\n')
	U.webio.pout('</das2server>\n')
	
	return 0
