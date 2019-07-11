#!/usr/bin/env python3

import sys
import urllib
import urllib.parse
import urllib.request
import optparse
import logging
import subprocess
import os
import os.path
#import resource
import fcntl
import select
import time
import smtplib

from os.path import join as pjoin

import das2


# On Jenkins Server this is:  
#
#  ../../../autoplot-release/lastSuccessful/archive/autoplot/Autoplot/dist/autoplot.jar
g_sJenkinsAutoplot = 'autoplot'


##############################################################################
# A generic version reporting block

def stripSVNkey(s):
	if s.find(':') == -1:
		return s.strip(" $") + ": unknown"
	else:
		return s.strip(' $')

g_sRev = stripSVNkey("$Rev: 11571 $")
g_sURL = stripSVNkey("$URL: https://saturn.physics.uiowa.edu/svn/das2/servers/devel/pyserver/scripts/das2_srv_ap_check.py $")
g_sWho = stripSVNkey("$LastChangedBy: cwp $")
g_sWhen = stripSVNkey("$LastChangedDate: 2019-06-20 18:24:51 -0500 (Thu, 20 Jun 2019) $")	


##############################################################################
# Sub-process running, with limit checks

LIMIT_TIMEOUT = 1
LIMIT_STDOUT  = 2
LIMIT_STDERR  = 3

g_LimitMsg = [None, "Command time out", "Standard Output Buffer Limit",
                    "Standard Error Buffer Limit" ]

def runProc(uCmd, nTimeOutSec=600, nStdOutLimit=1048576, nStdErrLimit=1048576):
	"""Run a sub process collecting standard out and standard error up to 
	a point.  Also don't allow the process to take forever, provide a 
	time limit check.
	
	Args:
	  uCmd  - The command to run, a unicode string

	  nTimeOutSec - The maximum number of seconds to let the command run

	  nStdOutLimit - The mamxmum number of bytes to collect from the command's
	                 standard output channel
						  
	  nStdErrLimit - The mamxmum number of bytes to collect from the command's
	                 standard error channel
	
	Returns: (nLimit, nReturn, sStdOut, sStdErr) Where:
	   nLimit - A value representing hiting a resource limit.  If no
		         limits were hit, the value is None.  Other values are:
					
					1 - Command runtime in seconds limit hit.
					2 - Standard output bytes limit hit
					3 - Standard error bytes limit hit
					
		nReturn - Assuming the command wasn't killed to avoid a resource limit
		         this is the command return value
					
		sStdOut - The standard output data collected up until hitting a 
		         resource limit, or all the stdout data if no limit was 
					encountered.
					
		sStdErr - The standard error data collected up until hitting a 
		         resource limit, ar all the stderr data if no limit was
					encountered. 
	if the process completed without
	         triggering a limit check such as a time out, or output limit
	"""
	
	# There return tuple values
	nLimit = None
	nReturn = None
	lStdOut = []
	lStdErr = []	
	
	
	proc = subprocess.Popen(uCmd, shell=True, stdout=subprocess.PIPE, 
	                        stderr=subprocess.PIPE)
	
	fdStdOut = proc.stdout.fileno()
	fdStdErr = proc.stderr.fileno()
	
	fl = fcntl.fcntl(fdStdOut, fcntl.F_GETFL)
	fcntl.fcntl(fdStdOut, fcntl.F_SETFL, fl | os.O_NONBLOCK)
	
	fl = fcntl.fcntl(fdStdErr, fcntl.F_GETFL)
	fcntl.fcntl(fdStdErr, fcntl.F_SETFL, fl | os.O_NONBLOCK)
	
	nStart = int(time.time())

	nStdOutBytes = 0
	nStdErrBytes = 0

	while True:
		
		nNow = int(time.time())
		nMaxTime = nTimeOutSec - (nNow - nStart)
		
		lReads = [fdStdOut, fdStdErr]
		lReady = select.select(lReads, [], [], float(nMaxTime))
		
		if len(lReady) == 0:
			if proc.poll() == None:
				proc.kill()
				nLimit = LIMIT_TIMEOUT
			break
			
		for fd in lReady[0]:
			
			if fd == fdStdOut:
				sRead = proc.stdout.read().decode(encoding='utf-8')
				
				if len(sRead) != 0:
					if nStdOutBytes + len(sRead) > nStdOutLimit:			
						# Get bytes up to the limit
						lStdOut.append(sRead[:nStdOutLimit - nStdOutBytes] )
						nLimit = LIMIT_STDOUT
						proc.kill()
						
					else:
						lStdOut.append(sRead)
					
					nStdOutBytes += len(sRead)
					
				
			if fd == fdStdErr:
				sRead = proc.stderr.read().decode(encoding='utf-8')
				
				if len(sRead) != 0:
					if nStdErrBytes + len(sRead) > nStdErrLimit:			
						# Get bytes up to the limit
						lStdErr.append(sRead[:nStdErrLimit - nStdErrBytes] )
						nLimit = LIMIT_STDERR
						proc.kill()
						
					else:
						lStdErr.append(sRead)
					
					nStdErrBytes += len(sRead)		
		
		if proc.poll() != None:
			break
	
	if nLimit == None:
		return (None, proc.returncode, "".join(lStdOut), "".join(lStdErr))
	else:
		return (nLimit, None, "".join(lStdOut), "".join(lStdErr))
	

##############################################################################
g_sScriptTplt = '''
import java.lang
import autoplot as ap_lib
import autoplotapp as ap_app
from org.das2.dataset import NoDataInIntervalException
from java.net import SocketTimeoutException

try:
   uri= '%s'
   ds= ap_lib.getDataSet(uri)

except NoDataInIntervalException, e:
   print e
   java.lang.System.exit(101)

except SocketTimeoutException, e:
	print e
	java.lang.System.exit(17)

except java.lang.Exception, e:
   print e
   java.lang.System.exit(102)
	
except java.lang.Error, e:
	print e
	java.lang.System.exit(105)
	
if ( ds==None ):
   java.lang.System.exit(103)
	
elif ( ds.length()==0 ):
   java.lang.System.exit(104)
	
ap_app.plot( ds )
#dom.plots[0].title = "%%s!c%%s"%%(ap_app.dom.plots[0].title,'%s')
ap_app.writeToPng( '%s', 640, 480 )
java.lang.System.exit(0)
'''

def makePlot(log, sServer, sSource, sRange, sInterval, sParams, sJavaBin, 
             sAltAutoplot=None):
	'''Returns:  The 2-tuple (nRetCode, sMsg)
	then return codes are:
	
	0 - Plot constructed properly
	1 - 3 Setup problem, can't find autoplot or something like that
	7 - Resource limit hit on sub-program
	101-104 - Bad plot, but everything looked like it should have run
	111 - DSDF problem
	'''

	log.info("Testing %s"%sSource)

	lRange = sRange.split('|')[0].split()
	if len(lRange) < 3 or lRange[1].lower() != 'to':
		return (111, "Improper ExampleRange value")
	
	sMsg = "Range: %s to %s"%(lRange[0], lRange[2])
	
	if sInterval:
		sUri = 'vap+das2server:%s?dataset=%s&start_time=%s&end_time=%s&interval=%s'%(
		       sServer, sSource, lRange[0], lRange[2], sInterval)
		sMsg += ", interval: %s"%sInterval
	else:
		fRes = (das2.DasTime(lRange[2])  - das2.DasTime(lRange[0])) / 1000
		sMsg += ", resolution: %f s"%fRes
		sUri = 'vap+das2server:%s?dataset=%s&start_time=%s&end_time=%s&resolution=%f'%(
		       sServer, sSource, lRange[0], lRange[2], fRes)
	
	if sParams:
		sUri += "&%s"%sParams.replace(' ', '%20')
		sMsg += ", parameters: %s"%sParams
	
	log.info(sMsg)
	
	sPngPath = pjoin( os.getcwd(), sSource.replace('/','_') + ".png")
	
	if os.path.isfile(sPngPath):
		os.remove(sPngPath)
	
	sScript = g_sScriptTplt%(sUri, sSource, sPngPath)
	
	sScriptName = sSource.replace('/','_') + ".jy"
	fOut = open(sScriptName, 'w')
	fOut.write(sScript)
	fOut.close()
	
	sAutoplot = g_sJenkinsAutoplot
	if sAltAutoplot != None:
		sAutoplot = sAltAutoplot
	
	sScriptPath = pjoin(os.getcwd(), sScriptName)
	
	sCmd = '%s -cp %s -Djava.awt.headless=true org.autoplot.AutoplotUI --script "%s"'%(
	       sJavaBin, sAutoplot, sScriptPath)
			 
	log.info("Exec: %s"%sCmd)

	# Run command for up to 5 minutes with 1MB StdOut and StdErr	
	(nLimit, nReturn, sStdOut, sStdErr) = runProc(sCmd, 600, 1048576, 1048576)

	if nLimit != None:
		return (7, "Sub-process resource limit hit: %s"%g_LimitMsg[nLimit])
												
	if nReturn != 0:
		if nReturn == 101:
			sMsg = "No data in interval"
		elif nReturn == 104:
			sMsg = "Dataset not created"
		elif nReturn == 105:
			sMsg = "Zero length data set, but NoData exception is missing."
		elif nReturn == 17:
			sMsg = "Network Connection Timeout"
		else:
			sMsg = sStdOut
		
		log.warning("Exec: %s\n          Return: %d\n          Reason: %s"%(sCmd, nReturn, sMsg))
		return (nReturn, sMsg)
	
	if not os.path.isfile(sPngPath):
		log.error(sStdOut)
		return (1, "Proper Autoplot exit, but %s is missing (HINT: If using pyServer check TEST_FROM in das2server.conf."%sPngPath)
	
	return (0, "%s tested okay"%sSource)

##############################################################################
def setupLogging(sLogLevel, sFile=None, bStderr=True):
	"""Utility to setup standard python logger.
	sLogLevel - Logging level, starts with one of: C,c,E,e,W,w,I,i,D,d 
	           [critical,error,warning,info,debug]
	"""
	sLevel = sLogLevel.lower()
	nLevel = logging.WARNING
	
	sDateFmt = '%Y-%m-%d %H:%M:%S'
	sFileFmt = '%(asctime)s %(levelname)-8s: %(message)s'
	sConFmt = '%(levelname)-8s: %(message)s'
	
	if sLevel.startswith("c"):
		nLevel = logging.CRITICAL
	elif sLevel.startswith("e"):
		nLevel = logging.ERROR
	elif sLevel.startswith("i"):
		nLevel = logging.INFO
	elif sLevel.startswith("d"):
		nLevel = logging.DEBUG
		sFileFmt = '%(asctime)s %(name)-12s %(levelname)-8s: %(message)s'
		sConFmt = '%(name)-12s %(levelname)-8s: %(message)s'
	
	#Logging options:  Console,File|File|Console|None(acually console force crit)
	rootLogger = logging.getLogger('')
	rootLogger.setLevel(nLevel)
	
	conHdlr = logging.StreamHandler(sys.stderr)
	formatter = logging.Formatter(sConFmt, sDateFmt)
	conHdlr.setFormatter(formatter)
	rootLogger.addHandler(conHdlr)
	
	return rootLogger

##############################################################################
class Das2Pkt(object):
	STREAM_HDR  = 0
	PACKET_HDR  = 1
	PACKET_DATA = 2
	COMMENT     = 3

	########################################################################
	def __init__(self, log, sName, xFirst10):
	
		self.sName = sName
		self.log = log
		
		bCanGetLen = True
		self.nLen = None
		if xFirst10[1:3].lower() == b'xx':
			self.nPktId = None
			self.nType = self.COMMENT
		else:
			self.nPktId = int(xFirst10[1:3].decode(encoding='utf-8'))
			if xFirst10[0] == ord('[') and xFirst10[3] == ord(']'):
				if self.nPktId == 0:
					self.nType = self.STREAM_HDR
				else:
					self.nType = self.PACKET_HDR
			elif xFirst10[0] == ord('|') and xFirst10[3] == ord('|'):
				self.nType = self.PACKET_DATA
				bCanGetLen = False
			else:
				raise ValueError("%s: Can't parse '%s' as a Das2 Packet Header"%(
				                 sName, xFirst10))
				
		if bCanGetLen:
			self.nLen = int(xFirst10[4:10].decode(encoding='utf-8'), 10)
		
	########################################################################
	def setData(self, xData):
		if self.nType == self.PACKET_DATA:
			self.xData = xData
		else:
			self.sData = xData.decode(encoding='utf-8')
			
		
	########################################################################
	# Yea, I should be using regular expressions here... do it later if
	# simple parsing has problems.
	
	def getProperty(self, sProperty):
	
		if self.nType == self.PACKET_DATA:
			raise ValueError("Das2 data packets don't have properties")
	
		iPropTag = self.sData.find('<properties')
		if iPropTag == -1:
			self.log.info("%s: No properties tag"%self.sName)
			return None
		
		iProperty = self.sData.find(sProperty)
		if iProperty == -1:
			return None
		
		iQuote1 = -1
		iQuote2 = -1
		
		for j in range(iProperty, len(self.sData)):
			if self.sData[j] == '"':
				if iQuote1 == -1:
					iQuote1 = j
				else:
					iQuote2 = j
					break

		if iQuote1 == -1 or iQuote2 == -1:
			return None
			
		sVal = self.sData[iQuote1+1:iQuote2].replace('&lt;','<')
		sVal = sVal.replace('&gt;','>').replace('&quot;','"')
		return urllib.parse.unquote_plus( sVal )
			
##############################################################################

def readPkt(log, fIn):
	x10 = fIn.read(10)
	if len(x10) < 10:
		return None
	
	pkt = Das2Pkt(log, fIn.geturl(), x10)
	
	if not pkt.nLen:
		return None
	
	sData = fIn.read(pkt.nLen)
	if len(sData) != pkt.nLen:
		log.error("Couldn't get packet length from stream at %s"%fIn.geturl())
		return None
	
	pkt.setData(sData)
	
	return pkt

##############################################################################
def sendMessages(log, sMailHost, sFrom, dAccum, bTest, bSendMail):
	
	nMsgs = 0
	
	for sContact in dAccum.keys():
		
		if bTest:
			lTo = [sFrom]
		else:
			lTo = sContact.split(',')
			
		sSubject = 'Das2 [Data Source Errors]'
		lBody = [
"The following Das2 Data Sources are failing to provide data in example ranges:",
"" ]
		#(nRet, sDataSource, sRange, sMsg)
		for tResult in dAccum[sContact]:
			
			lBody.append( "Das2 Server: %s"%tResult[4] )
			lBody.append( "Data Source: %s"%tResult[1] )
			lBody.append( "-"*(13+len(tResult[1])) )
			lBody.append( "Query Range: %s"%tResult[2] )
			lBody.append( "Error Message:")
			for sLine in tResult[3].split('\n'):
				lBody.append("     %s"%sLine)
			lBody.append( "" ) 
		
		sBody = '\n'.join(lBody)
		
		sMsg = """From: %s
To: %s
Subject: %s

%s
"""%(sFrom, ", ".join(lTo), sSubject, sBody)

		# Write out the message as as text file
		sMsgFile = pjoin(os.getcwd(), "%s.msg"%(sContact.split()[0]) )
		fOut = open(sMsgFile, 'w')
		fOut.write(sMsg)
		fOut.close()
		
		nMsgs += 1
		
		if bSendMail:
			# Also send the message
			try:
				server = smtplib.SMTP(sMailHost)
				server.sendmail(sFrom, lTo, sMsg)
			except:
				e = sys.exc_info()[0]
				log.error(
					"Couldn't send message to %s, using host %s, reason: %s"%(
					lTo, sMailHost, str(e))
				)
			
	return nMsgs

##############################################################################
def main(argv):
	
	psr = optparse.OptionParser(
		usage="%prog [options] DAS2_SERVER_URL SMTP_HOST FROM",
		prog="das2_dsdf_test.py",
		version=" \n".join( [g_sRev, g_sWho, g_sWhen, g_sURL] ),
		description="""
Checks all data sources on a das2 server to determine if data from the 
example range can be plotted by autoplot.  Returns non-zero if one or more 
data sources cannot plot.  The DAS2_SERVER_URL argument is manditory, the contact argument is optional.  SERVER - 
The URL of the server to connect to, MAILHOST - the SMTP server to contact,
and FROM - the email address to use in the 'from:' field for any messages
that are generated.
""")
		
	psr.add_option('-l', "--log-level", dest="sLevel", metavar="LOG_LEVEL",
	               help="Logging level one of [critical, error, warning, "+\
	               "info, debug].  The default is warning, ONLY set the level "+\
	               "lower than this for testing, not production.", 
	               type="string", action="store", default="warning")
												
	psr.add_option('-s', '--skip-plots', dest="bSkipPlots", action="store_true",
	               default=False, help="By default autoplot is called to generate "+\
						"plots using the example range, this option just tests that "+\
						"any data are output by the data source") 
						
	psr.add_option('-a','--autoplot', dest="sAutoplot", metavar="AUTOPLOT",
	               default=None, type="string", action="store", 
	               help="Specify an alternate autoplot executable.  The "+\
						"first executable file named 'autoplot' on the PATH is "+\
						"used by default.")
		               
	sDef = '/usr/bin/java'
	psr.add_option('-j','--java-bin', dest="sJavaBin", metavar="JAVA_BIN",
	               default=sDef, type="string", action="store",
	               help="Specify and alternate path to the java binary, the "+\
	               "default is %s"%sDef)
	               
	psr.add_option('-m', '--mail-to-from', dest="bTest", action="store_true",
	               help="Test the test.  Sends all messages that would have "+\
	               "generated to the from address instead of the tech contact.")
	
	psr.add_option('-M', '--no-mail', dest="bSendMail", action="store_false",
	               default=True, help="Don't actually send any mail regardless "+\
	               "of the destination, just write the messages to disk in "+\
	               "*.msg files.")
						
	psr.add_option('-N', '--no-op', dest="bListOnly", action="store_true",
	               default=False, help="Just list the sources that would have"+\
						" been checked, but don't actually download data")
	               
	psr.add_option('-c','--contact', dest="sInContact", metavar="STR1,STR2,STR3", 
	               default=None, type="string", help="A comma separated list "+\
						"of strings.  The tech contact string must contain at least "+\
						"one of these strings or the data source is skipped. For "+\
						"example using 'chris,matt' will only check data sources"+\
						"where the string chris or matt is present it the "+\
						"techContact field.")
						
	psr.add_option('-C', '--no-contact', dest="sExContact", metavar="STR1,STR2,STR3",
	               default=None, type="string", help="The opposite of -c. "+\
						"Identifies contacts who's sources should *not* be checked."+\
						"If the exclude and include lists overlap, exclude wins.")
	               
	psr.add_option('-d','--data-src', dest="sInSource", metavar="STR1,STR2,STR3",
	               default=None, type="string", help="A comma separated list "+\
						"of strings.  The data source ID must contain one of these "+\
	               "string or the source is skipped.  For example "+\
						"'Juno/WAV,Juno/FGM' will test only the magnetometer and "+\
						"Waves instrument sources.")

	psr.add_option('-D', '--no-data-src', dest="sExSource", metavar="STR1,STR2,STR3",
	               default=None, type="string", help="The opposite of -d. "+\
						"Identifies source IDs that should *not* be checked.  If "+\
						"the exclude and include lists overlap, exclude wins.")

	psr.add_option('-n', '--num-srcs', dest="nCheck", metavar="INTEGER",
	               default=-1, help="Limit the number of sources checked to "+\
	               "INTEGER.  By default all sources are checked", type="int")
	               	
	(opts, lParam) = psr.parse_args(argv[1:])
	
	log = setupLogging(opts.sLevel)
	
	if len(lParam) < 3:
		log.error("Script requires three command line parameters, use -h for help")
		return 13
	
	sDas2Srv  = lParam[0].strip('" ')
	sSmtpSrv  = lParam[1].strip('" ')
	sFrom     = lParam[2].strip('" ')

	if len(lParam) > 3:	
		log.error("Unknown cmdline params present %s, use -h for help"%lParam[4:])
		return 99
	
	# Find autoplot if not specified
	lPath = os.environ['PATH'].split(os.pathsep)
	for sDir in lPath:
		if opts.sAutoplot: break
		
		sBin = pjoin(sDir, 'autoplot')
		if os.path.isfile(sBin) and os.access(sBin, os.X_OK):
			opts.sAutoplot = sBin
	
	# Make sure than autoplot was selected
	if opts.sAutoplot == None:
		log.error("Can't find autoplot")
		return 99
	
	if not os.path.isfile(opts.sAutoplot):
		log.error("Can't find autoplot at %s"%opts.sAutoplot)
		return 99
		
	# Setup the exclude and include lists for contacts and sources
	opts.lInContacts = None
	if opts.sInContact: 
		opts.lInContacts = [s.strip().lower() for s in opts.sInContact.split(',')]
	opts.lExContacts = None
	if opts.sExContact: 
		opts.lExContacts = [s.strip().lower() for s in opts.sExContact.split(',')]
	
	opts.lInSources = None
	if opts.sInSource:
		opts.lInSources = [s.strip() for s in opts.sInSource.split(',')]
	opts.lExSources = None
	if opts.sExSource:
		opts.lExSources = [s.strip() for s in opts.sExSource.split(',')]
		
	
	nTestedDsdfs = 0
	
	dMessages = {}  # Collection of failure messages to send out
	
	log.info("Sending das2.2 list message")
	sURL = '%s?server=list'%sDas2Srv
	fDsdfs = urllib.request.urlopen(sURL)
	sDsdfs = fDsdfs.read().decode(encoding='utf-8')
	fDsdfs.close()
	lDsdfs = sDsdfs.split('\n')
	nSysError = 0
	for i in range(0, len(lDsdfs)):
	
		if (opts.nCheck != -1) and (nTestedDsdfs >= opts.nCheck): break
	
		lTmp = lDsdfs[i].strip().split('|')
		if len(lTmp) < 1:
			continue
		sDataSource = lTmp[0].strip()
		if len(sDataSource) < 1:
			continue
		
		if sDataSource.endswith('/'):
			continue
			
		if sDataSource.lower().find('/test/') != -1:
			continue
			
		if sDataSource.lower().find('/testing/') != -1:
			continue
		
		
		# Match against include/exclude data source IDs
		if opts.lExSources:
			bSkip = False
			for sFrag in opts.lExSources:
				if sDataSource.find(sFrag) >= 0:
					bSkip = True
					break
			if bSkip: continue
		
		if opts.lInSources:
			bSkip = True
			for sFrag in opts.lInSources:
				if sDataSource.find(sFrag) >= 0:
					bSkip = False
					break
			if bSkip: continue
		
            		
		if len(lTmp) > 1:
			sDescription = '|'.join(lTmp[1:])
	
		sDsdfUrl = '%s?server=dsdf&dataset=%s'%(sDas2Srv, sDataSource)
		fDas2Stream = urllib.request.urlopen(sDsdfUrl)
		pkt = readPkt(log, fDas2Stream)
		if pkt.nType != Das2Pkt.STREAM_HDR:
			log.error("Stream %s doesn't start with stream header"%sDsdfUrl)
			
		fDas2Stream.close()
		
		sDsdfContact = pkt.getProperty('techContact')
		if not sDsdfContact:
			log.error("No one is repsonsible for: %s !"%sDataSource)
			continue
		sDsdfContact = sDsdfContact.strip('" \t')
		
		# match against include/exclude contacts
		if opts.lExContacts:
			bSkip = False
			for sFrag in opts.lExContacts:
				if sDsdfContact.lower().find(sFrag) >= 0:
					bSkip = True
					break
			if bSkip: continue
		
		if opts.lInContacts:
			bSkip = True
			for sFrag in opts.lInContacts:
				if sDsdfContact.lower().find(sFrag) >= 0:
					bSkip = False
					break
			if bSkip: continue


		
		if sDsdfContact.find(',') != -1:
			sTmp = 'are'
		else:
			sTmp = 'is'
			
		log.info("%s %s responsible for: %s"%(sDsdfContact, sTmp, sDataSource))
		
		sRange = pkt.getProperty('exampleRange')
		
		if not sRange:
			log.warning("TODO: Send missing exampleRange message")
			continue
			
		sInterval = pkt.getProperty('exampleInterval')
		
		sParams = pkt.getProperty('exampleParams')
				
		#nKbSelf0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
		#nKbSub0  = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
		
		if opts.bListOnly:
			nRet = 0
			sMsg = None
			print("Would have tested: %s,%s"%(sDas2Srv,sDataSource))
		else:		
			(nRet, sMsg) = makePlot(
				log, sDas2Srv, sDataSource, sRange, sInterval, sParams, 
				opts.sJavaBin, opts.sAutoplot
			)
										
		#nKbSelf1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
		#nKbSub1  = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
		
		#log.info("Memory usage change:  Self %+d kB, Children %+d kB"%(
		#         nKbSelf1 - nKbSelf0, nKbSub1 - nKbSub0))
		
		nTestedDsdfs += 1
		
		if nRet == 0:
			log.info("%s: OKAY"%sDataSource)
		elif nRet < 100:
			log.error(sMsg)
			nSysError = 13
		else:
			if sDsdfContact not in dMessages:
				dMessages[sDsdfContact] = []
			dMessages[sDsdfContact].append( (nRet, sDataSource, sRange, sMsg, sDas2Srv) )	
	
	if (opts.lExContacts or opts.lInContacts or opts.lInSources or opts.lExSources) \
	   and (nTestedDsdfs == 0):
		log.info("No data sources matched the filter criteria:")
		if opts.lExContacts: log.info("   exclude contacts %s"%opts.lExContacts)
		if opts.lInContacts: log.info("   include only contacts %s"%opts.lInContacts)
		if opts.lExSources: log.info("   exclude source IDs %s"%opts.lExSources)
		if opts.lInSources: log.info("   include only sources IDs %s"%opts.lInSources)
		
		return nSysError  # which is ususally 0
			
	# Handle sending emails:	
	nMsgs = sendMessages(
		log, sSmtpSrv, sFrom, dMessages, opts.bTest, opts.bSendMail
	)
		
	if nMsgs != 0:
		print("%d Sources OK, %d fail(s)"%(nTestedDsdfs-nMsgs, nMsgs))
		return nMsgs
	else:
		print("%d sources OK"%nTestedDsdfs)
		return nSysError
		
##############################################################################
if __name__ == "__main__":
	sys.exit( main(sys.argv) )
