"""Default handler for sending out peers data"""

import sys
import os
import ConfigParser

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')


##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See das2server.defhandlers.intro.py for a decription of this function
	interface
	"""
	
	if 'PEERS_FILE' not in dConf:
		U.io.serverError(fLog, u"Create an INI file contaning known das2 servers, then "
		      "add a PEERS_FILE key to \n%s to point to your peers list."%dConf['__file__'])
		return 17
	
	sPeersFile = dConf['PEERS_FILE']
	
	if not os.path.isfile(sPeersFile):
		U.io.serverError(fLog, u"Peers file %s is missing"%sPeersFile)
		return 17
	
	psr = ConfigParser.SafeConfigParser()
	psr.read(dConf['PEERS_FILE'])
	
	pout("Content-Type: text/xml; charset=utf-8\r\n")
			
	pout('<?xml version="1.0" encoding="UTF-8" ?>')
	pout('<?xml-stylesheet type="text/xsl" href='
	     '"%s/resource/das2server.xsl"?>'%os.environ['SCRIPT_NAME'])
	pout('<das2server>')
	pout('  <peers>')
	
	lSec = psr.sections()
	lSec.sort()
	
	for sSec in lSec:
		pout('    <server>')
		pout('      <name>%s</name>'%sSec)
		if psr.has_option(sSec, 'url'):
			pout('      <url>%s</url>'%psr.get(sSec, 'url'))
		if psr.has_option(sSec, 'description'):
			pout('      <description>%s</description>'%psr.get(sSec, 'description'))
		pout('    </server>')
	
	pout('  </peers>')
	pout('</das2server>')
	
	return 0
