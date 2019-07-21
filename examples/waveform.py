"""This is a full featured python reader script demonstrating:
  
  1. How to send a mostly binary das2 stream in python2 or 3
  2. How to efficently transmit waveform data
  3. How to send error and progerss messages out to client programs 
  4. How to send messages to the server log
  
Much of this code is general to any python based das2 reader and could be setup
as part of the das2 library.  Instead it has been included here to provide a 
mostly stand-alone example.  Only the DasTime class is used from the das2
module and this could be replaced with native python datetime objects.

The output of this reader can be converted to a UTF-8 file using the 
das2_ascii filter as follows:

  ./example_waveform.py $(pwd) 1979-03-01T12:26 1979-03-01T12:30 | das2_ascii -s 6 -r 4 > temp.d2t
  
It can also be converted to a power spectral density stream using

  ./example_waveform.py $(pwd) 1979-03-01T12:26 1979-03-01T12:30 | das2_psd 1584 2 > temp_spec.d2s
  
"""

import sys
import os
import optparse
import logging
import struct

from os.path import basename as bname
from os.path import dirname as dname
from os.path import join as pjoin

import das2

##############################################################################
# boiler plate to deal with python2/3 and unicode/bytes

try:
	unicode
except NameError:
	unicode = str
	
def write(thing):
	"""Python 2/3 safe function that encodes all unicode objects as utf-8,
	leaves raw byte arrays alone, and doesn't try to "help" with line endings.
	"""
	if sys.version_info[0] == 2:
		if isinstance(thing, unicode): 
			sys.stdout.write(thing.encode('utf-8'))
		else:
			sys.stdout.write(thing)
	else:
		if isinstance(thing, unicode):    
			sys.stdout.buffer.write(thing.encode('utf-8'))
		else:
			sys.stdout.buffer.write(thing)

def flush():
	if sys.version_info[0] == 2: sys.stdout.flush()
	else: sys.stdout.buffer.flush()

##############################################################################
# Select native byte order for 4-byte IEEE reals

if sys.byteorder == 'little':
	_g_sFloatType = "little_endian_real4" 
else:
	_g_sFloatType = "sun_real4"

##############################################################################
# Reusable python logging Setup

def setupLogger(sLevel="info"):
	"""Utility to setup a standard python logger
	sLevel - Logging level, starts with one of: C,c,E,e,W,w,I,i,D,d 
	         [critical,error,warning,info,debug]				
	"""

	sLevel = sLevel.lower()
	nLevel = logging.WARNING	
	sMsgFmt = '%(levelname)-8s: %(message)s'
	
	if sLevel.startswith("c"):
		nLevel = logging.CRITICAL
	elif sLevel.startswith("e"):
		nLevel = logging.ERROR
	elif sLevel.startswith("i"):
		nLevel = logging.INFO
	elif sLevel.startswith("d"):
		nLevel = logging.DEBUG
		# Add time information at debug level
		sMsgFmt = '%(name)-12s %(levelname)-8s: %(message)s'
	
	rootLogger = logging.getLogger('')
	rootLogger.setLevel(nLevel)
	
	# The das2 server CGI script sends all standard error output to log files
	# under the LOG_PATH directory specified in the das2server.conf file.
	conHdlr = logging.StreamHandler(sys.stderr)
	
	formatter = logging.Formatter(sMsgFmt)
	conHdlr.setFormatter(formatter)
	rootLogger.addHandler(conHdlr)
		
	return rootLogger


###############################################################################
# Reusable progress tracker

class TimeProgressTracker(object):
	"""Progress Tracker suitable for use with monotonic time tagged records"""
	
	def __init__(self, sWho, dtBeg, dtEnd, nIncrements):
		if nIncrements < 10:
			raise ValueError
		self.dtBeg = dtBeg.copy()  # Caller might change these objects, maintain
		self.dtEnd = dtEnd.copy()  # a static copy
		
		self.nIncrements = nIncrements
		self.rTotal = self.dtEnd - self.dtBeg
		self.rReportThreshold = self.rTotal / float(nIncrements)
		self.dtLastReport = self.dtBeg.copy()
		self.sWho = sWho.replace("<","&lt;").replace(">","&gt;").strip('"')
		
		sMsg = '<comment type="taskSize" value="%d" source="%s" />\n'%(
		        self.nIncrements, self.sWho)
		write( "[xx]%06d%s"%(len(sMsg), sMsg) )

	def status(self, dtCurrent):
		if self.rTotal == 0.0:
			return
				
		if (dtCurrent - self.dtLastReport) > self.rReportThreshold:
			nProg = int( ((dtCurrent - self.dtBeg) / self.rTotal)* self.nIncrements )	
			
			sMsg = '<comment type="taskProgress" value="%d" source="%s" />\n'%(
			         nProg, self.sWho)
			write( "[xx]%06d%s"%(len(sMsg), sMsg) )
			
			self.dtLastReport = dtCurrent.copy()

###############################################################################
# Reusable output functions

g_bStrmHdrWritten = False
 
def streamHeader(dProps):
	lHdr = ['<stream version="2.2">']
	if len(dProps) > 0:
		lHdr.append( '   <properties')
		for sKey in dProps:
			lHdr.append( '%s%s="%s"'%(" "*14, sKey, dProps[sKey]))
	lHdr += ['   />', '</stream>']
	
	sHdr = u'\n'.join(lHdr)
	sHdr += '\n'
	
	return "[00]%06d%s"%(len(sHdr), sHdr)


def _das2Except(sType, sMsg):
	sFmt = '<exception type="%s" message="%s" />\n'
	sMsg = sMsg.replace('\n', '&#13;&#10;').replace(u'"', u"'")		  
	sOut = sFmt%(sType, sMsg)
	
	if not g_bStrmHdrWritten:
		sSmHdr = '<stream version="2.2" />'
		write("[00]%06d%s"%(len(sSmHdr), sSmHdr))
	
	write("[xx]%06d%s"%(len(sOut), sOut))

def sendNoData(log, dtBeg, dtEnd):
	sMsg = "No data in interval %s to %s UTC"%(str(dtBeg)[:-3], str(dtEnd)[:-3])
	log.info(sMsg)
	_das2Except("NoDataInInterval", sMsg)
	return 0

def queryErr(log, sMsg):
	log.error(sMsg)
	_das2Except("IllegalArgument", sMsg)
	return 101

def serverErr(log, sMsg):
	log.error(sMsg)
	_das2Except("ServerError", sMsg)
	return 102



###############################################################################
# Begin Task Specific Code

class VgrWfrmRecord(object):
	"""Handles interpreting a single binary record from a Voyager PWS
	Wideband frame PDS product into a Das2 Stream packet"""
	
	@staticmethod
	def das2HeaderPacket(nPacketId):
		"""Static class function to write a packet header that corresponds
		to the packet records emitted by the das2Packet function below"""
		sHdr = ""
	
		# The renderer="waveform" hint in the title let's Autoplot know to
		# unroll the time tags in the Y-Values onto the X-axis thus reproducting
		# the time series without requiring a 27+byte time value for each 
		# entry.  Autoplot doesn't understand the SI time interval unit: μs 
		# so the non-standard microsec unit is used below instead
		
		# Tell Jeremy: Autoplot bug if yUnits below are not "s" and <x> units
		# are not t2000
		sHdr = '''<packet>
   <x type="time24" units="t2000"></x>
   <yscan type="%s" name="relative_deflection" nitems="1584" zUnits="" yUnits="s" yTagInterval="3.472222e-05" >
        <properties String:yLabel="Relative Deflection"
                    String:yScaleType="linear" />
   </yscan>
</packet>
'''%_g_sFloatType

		return "[%02d]%06d%s"%(nPacketId, len(sHdr), sHdr)
	
	
	def __init__(self, dtFrame, rawBytes):
		"""Given the frame start time and one record's worth of bytes
		initialze the waveform record
		"""
		self.bytes = rawBytes
		(nLineCount, ) = struct.unpack(">H", self.bytes[116:118])
		
		self.dtBeg = dtFrame + (nLineCount - 1)*0.060 #60 ms/line
		self.dtEnd = dtFrame + nLineCount*0.060
		

	def das2DataPacket(self, nPktId):
		"""Creates a binary das2 record in host native byte order
		Input data are 4-bit integers where 0 is the maximum negative
		value.  Connert to floats centered at 7.5
		"""		
		
		sPkt = "%s "%str(self.dtBeg)[:-3]
		lVals = []
		for b in self.bytes[228:1020]:   # Starting at 228 instead of 220 because
			n1 = ( ord(b) & 0xF0) >> 4    # 1st 16 samples are junk at Jupiter
			n2 = ord(b) & 0x0F
			
			lVals.append( struct.pack("=f", float(n1) - 7.5) )
			lVals.append( struct.pack("=f", float(n2) - 7.5) )
				
		sPkt += ''.join(lVals)
		return ":%02d:"%nPktId + sPkt	


class VgrFileReader(object):
	"""Provides an interface for iterating over records in a voyager
	PWS Wideband frame PDS product file"""
	
	def __init__(self, log, sFile):
		log.info("Reading %s"%sFile)
		self.sFile = sFile
		self.fIn = open(sFile, 'rb')
		self.dtFrame = None
		
	def __iter__(self):
		self.fIn.seek(0)
		return self
		
	def next(self):
		bytes = self.fIn.read(1024)
		if len(bytes) < 600:
			raise StopIteration
			
		if self.fIn.tell() == 1024:
			self.dtFrame = das2.DasTime(bytes[274:297])
			bytes = self.fIn.read(1024)
		
		if len(bytes) < 600:
			raise StopIteration
		else:
			return VgrWfrmRecord(self.dtFrame, bytes)


def getVgrFileBegTime(sPath):
	"""Read the Waveform Frame start time from the filename"""
	s = bname(sPath)
	if not s.startswith('VG'):
		return None
		
	try:
		nYr = int(s[4:8], 10)
		nMn = int(s[9:11], 10)
		nDom = int(s[12:14], 10)
		nHr = int(s[15:17], 10)
		nMin = int(s[18:20], 10)
		nSec = int(s[21:23], 10)
		nMilli = int(s[24:27], 10)
		fSec = float(nSec) + nMilli / 1000.0
	except:
		#Doesn't look like a voyager file, skip it
		return None
	
	return das2.DasTime(nYr, nMn, nDom, nHr, nMin, fSec)

###############################################################################
def main(argv):
	
	global g_bStrmHdrWritten
	
	sVer = " \n".join( [g_sRev, g_sWho, g_sWhen, g_sURL] )
	sUsage = "%s [options] DATA_DIRECTORY BEGIN END"%bname(argv[0])
	sDesc = """
Reads Voyager 1 High-Rate waveform values and produce a Das2 Stream.  Three
parameters are required, (1) The path to the directory where the datafiles
reside, (2) The minmum time value of records to transmit, and (3) the
maximum time value.
"""
	psr = optparse.OptionParser(usage=sUsage, description=sDesc, version=sVer,
	                            prog=bname(argv[0]))
	
	psr.add_option('-l', "--log-level", dest="sLevel", metavar="LOG_LEVEL",
	               help="Logging level one of [critical, error, warning, "+\
	               "info, debug].  The default is info.", type="string",
	               action="store", default="info")
	
	(opts, lArgs) = psr.parse_args(argv[1:])
	log = setupLogger(opts.sLevel)
	log = logging.getLogger('')
	
	if len(lArgs) < 1:
		return serverErr(log, "Misconfigured DSDF, data directory is missing")
	sRoot = lArgs[0]
	
	if len(lArgs) < 3:
		return queryErr(log, "Query error, Start and or Stop time is missing")
		
	try:
		dtBeg = das2.DasTime(lArgs[1])
	except:
		return queryErr(log, "Couldn't parse time value '%s'"%lArgs[1])
	try:
		dtEnd = das2.DasTime(lArgs[2])
	except:
		return queryErr(log, "Couldn't parse time value '%s'"%lArgs[2])
	
	# Send the stream header as soon as you can, this way if data loading
	# takes a while the client program knows the reader is alive and will
	# not shutoff the connection.  
	sHdr = streamHeader({
      'String:renderer':'waveform',#<-- Tell Autoplot to use Waveform Rendering
		'String:title':'Voyager PWS Wideband, Jupiter Encounter',
		'Datum:xTagWidth': '120 ms',  # Twice the time between rows 
		'DatumRange:xCacheRange': "%s to %s UTC"%(str(dtBeg)[:-3], str(dtEnd)[:-3]),
		'String:xLabel' : 'SCET (UTC)'
	})
	write(sHdr)
	g_bStrmHdrWritten = True
	write( VgrWfrmRecord.das2HeaderPacket(1) )
	
	flush()  # It's good to flush stdout output right after sending headers so
            # Autoplot get's something right a way.

	
	# File search range starts 48 seconds before given time range since Voyager
	# waveform frame files contain 48 seconds worth of data
	dtSearchBeg = dtBeg.copy()
	dtSearchBeg -= 48.0
	
	# Though it's not needed for the small time extent of the sample dataset,
	# sending task progress messages allows Autoplot to display a data loading
	# progress bar (aka Human Amusement Device)
	progress = None
	
	lFiles = os.listdir(sRoot)
	lFiles.sort()
	
	# Interation below assumes file list and file records are in ascending
	# time order, this is typically the case.
	nSent = 0
	for sFile in lFiles:
		dtFileBeg = getVgrFileBegTime(sFile)
		
		# Skip unknown files and files that are out of the query range
		if dtFileBeg == None:
			continue
		if dtFileBeg < dtSearchBeg or dtEnd <= dtFileBeg:
			continue
		
		if progress == None:
			progress = TimeProgressTracker(bname(argv[0]), dtFileBeg, dtEnd, 100)
		
		for rec in VgrFileReader(log, pjoin(sRoot, sFile)):
		
			# since input data are monotonic, quit when encountering a 
			# record that is past the end point
			if rec.dtEnd >= dtEnd:
				break
			
			if rec.dtBeg < dtEnd and rec.dtEnd > dtBeg:
				write(rec.das2DataPacket(1))
				nSent += 1
		
			# Check/Send progress
			progress.status(rec.dtBeg)
			
	
	# If not data were available in the given time range inform the client
	if nSent == 0:
		sendNoData(log, dtBeg, dtEnd)
	
	return 0
	
###############################################################################
if __name__ == "__main__":
	sys.exit( main(sys.argv) )


