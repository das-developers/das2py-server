#!/usr/bin/env python3

from os.path import basename as bname
import collections
import sys
from io import BytesIO
from os.path import join as pjoin
import argparse

import cgi
import cgitb
cgitb.enable(format='text')

# Stuff that might not work if server is mis-configured
import xml.parsers.expat
from lxml import etree
	 
Packet = collections.namedtuple(
	'Packet', ['tag', 'id', 'length', 'content']
)

# ########################################################################## #

def pout(item):
	"""Encode strings if needed, send binary stuff out the door as is"""
	if isinstance(item, str):
		sys.stdout.buffer.write(item.encode('utf-8'))
		sys.stdout.buffer.write(b'\n')
	else:
		sys.stdout.buffer.write(item)


_g_BrowserAgent = ['firefox','explorer','chrome','safari']

def errorExit(sOut):
	"""Cut down error handling for use before the util modules are loaded,
	script must exit afte calling this or multiple HTTP headers will be 
	emitted.
	"""
	
	bClientIsBrowser = False
	if "HTTP_USER_AGENT" in os.environ:
		
		sAgent = os.environ['HTTP_USER_AGENT'].lower()
	
		for sTest in _g_BrowserAgent:
			if sAgent.find(sTest) != -1:
				bClientIsBrowser = True
				break	
	pout("Status: 500 Internal Server Error\r\n")
	
	if bClientIsBrowser:
		pout("Content-Type: text/plain; charset=utf-8\r\n\r\n")
		cgitb.enable(format='text')
		
		pout(sOut)
	else:
		pout("Content-Type: text/plain; charset=utf-8\r\n\r\n")
		pout(sOut)

	sys.exit(5)


# ########################################################################### #

g_sDas23       = 'das2.3-basic.xsd'
g_sDas23Strict = 'das2.3-basic-strict.xsd'
g_sDas22       = 'das2.2-mostly.xsd'
g_sDas22Strict = 'das2.2-mostly-strict.xsd'

# Schema by version. Defaults to no schema specified
g_dSchemas = {}
	
def getSchema(sSchemaDir, bStrict, sForceSchema, sStreamVer):
	global g_dSchemas
	
	if (sStreamVer, bStrict) in g_dSchemas:
		return g_dSchemas[sStreamVer]
	
	# If a fixed schema is given we have to load that
	if sForceSchema:
		sFile = sForceSchema
	elif sStreamVer == '2.2' and bStrict:
		sFile = pjoin(sSchemaDir, g_sDas22Strict)
	elif sStreamVer == '2.2':
		sFile = pjoin(sSchemaDir, g_sDas22)
	elif sStreamVer == '2.3/basic' and bStrict:
		sFile = pjoin(sSchemaDir, g_sDas23Strict)
	elif sStreamVer == '2.3/basic':
		sFile = pjoin(sSchemaDir, g_sDas23)
	else:
		raise ValueError("Unknown stream version %s"%sStreamVer)
	
	pout("Reading XSD: %s"%sFile)	
	fSchema = open(sFile)
	schema_doc = etree.parse(fSchema)
	schema = etree.XMLSchema(schema_doc)
	
	g_dSchemas[(sStreamVer, bStrict)] = schema
	
	return schema


# ########################################################################### #

def isDataPacket(sTag):
	return sTag in ('Dx','Qd')

def isAnyHeader(sTag):
	return (sTag not in ('Dx', 'Qd'))

def isDataHeader(sTag):
	return sTag in ('Hx','Qp')

class PacketReader:
	"""This packet reader can handle either das2.2 or das2.3 packets.  Use
	the bStrict flag in the constructor if only 2.3 parsing is desired."""
	
	def __init__(self, fIn, bStrict=False):
		self.fIn = fIn
		self.lPktSize = [None]*100
		self.lPktDef  = [False]*100
		self.nOffset = 0
		self.bStrict = bStrict
		self.sContent = "das2"
		self.sVersion = "2.2"
		self.bVarTags = False
		
		# See if this stream is using variable tags and try to guess the content
		# using the first 80 bytes.  Assume a das2.2 stream unless we see
		# otherwise
		
		self.xFirst = fIn.read(80)
		
		if len(self.xFirst) > 0:
			if self.xFirst[0:1] == b'|':
				# Can't use single index for bytestring or it jumps over to an
				# integer return. Hence [0:1] instead of [0]. Yay python3 :(
				self.bVarTags = True
				
			if len(self.xFirst) > 3:
				if self.xFirst[0:4] == b'|Qs|':
					self.sContent = "qstream"
			
		if self.xFirst.find(b'version') != -1 and \
		   self.xFirst.find(b'"2.3/basic"') != -1:
			self.sVersion = "2.3/basic"
			
		elif self.xFirst.find(b'dataset_id') != -1:
			self.sContent = 'qstream'
	
	def streamType(self):
		return (self.sContent, self.sVersion, self.bVarTags)
		
		
	def _read(self, nBytes):
		xOut = b''
		if len(self.xFirst) > 0:
			xOut = self.xFirst[0:nBytes]
			self.xFirst = self.xFirst[nBytes:]
			
		if len(xOut) < nBytes:
			xOut += self.fIn.read(nBytes - len(xOut))

		return xOut

	def setDataSize(self, nPktId, nBytes):
		"""Callback used when parsing das2.2 and earlier streams.  These had
		no length values for the data packets.
		"""
		
		if nPktId < 1 or nPktId > 99:
			raise ValueError("Packet ID %d is invalid"%nPktid)
		if nBytes <= 0:
			raise ValueError("Data packet size %d is invalid"%nBytes)
		
		self.lPktSize[nPktId] = nBytes
		
	def __iter__(self):
		return self

		
	def __next__(self):
		"""Get the next packet on the stream. Each iteration returns a Packet
		tuple.  The tuple has the members:
		
		   (tag, id, length, contents)
		
		Where the values are:
		   tag - The 2-character content tag, know header tags for das2.3
			     basic streams are:
			     
           Hs    - Stream Header
           Qs    - QStream Header
           Hx    - X-slice dataset header
           Qp    - QStream packet header
           He,Qe - Exception, Qe is the QStream version, same content
			  Hc,Qc - Comment, Qc is the QStream version, same content
           Dx,Qd - X-slice data packet.  Qd is the QStream verson, same 
			          content.
			  
		   id - The packet integer ID.  Stream and pure dataset packets
			     are always ID 0.  Otherwise the ID is 1 or greater.
			
			length - The original length of the packet before decoding UTF-8
			     strings.
			
			content - Exther a bytestr (data packets) or a string (header 
			     packets.  If the packet is a header then the bytes are 
				  decode as utf-8. If the packet contains data the a raw
				  bytestr is returned.
					
		The reader can iterate over all das2 streams, unless it has been
		set to strict mode, in which case it only parse packets with das2.3
		packet tags (ex: |PH|2|686|)
		"""
		x4 = self._read(4)
		if len(x4) != 4:
			raise StopIteration
					
		self.nOffset += 4
		
		# Try for a das2.3 packet wrappers, fall back to das2.2 unless prevented
		if x4[0:1] == b'|':
			return self._nextVarTag(x4)
			
		elif (x4[0:1] == b'[') or (x4[0:1] == b':'):
			return self._nextStaticTag(x4)
			
		raise ValueError(
			"Unknown packet tag character %s at offset %d, %s"%(
			str(x4[0:1]), self.nOffset - 4, 
			"(Hint: are the type lengths correct in the data header packet?)"
		))
	

	def _nextStaticTag(self, x4):
		"""Return a das2.2 packet, this is complicated by the fact that pre
		das2.3 data packets don't have length value, parsing the associated
		header is required.  The setDataSize() callback is supplied for parsing
		these streams.
		"""
		
		try:
			nPktId = int(x4[1:3].decode('utf-8'), 10)
		except ValueError:
			raise ValueError("Invalid packet ID '%s'"%x4[1:3].decode('utf-8'))
			
		if (nPktId < 0) or (nPktId > 99):
			raise ValueError("Invalid packet ID %s at byte offset %s"%(
				x4[1:3].decode('utf-8'), self.nOffset
			))
			
		if self.nOffset == 4 and (x4 != b'[00]'):
			raise ValueError("Input does not start with '[00]' does not appear to be a das2 stream")
		
		if x4[0:1] == b'[' and x4[3:4] == b']':
		
			x6 = self._read(6)	
			if len(x6) != 6:
				raise ValueError("Premature end of packet %s"%x4.decode('utf-8'))
				
			self.nOffset += 6
			
			nLen = 0
			try:
				nLen = int(x6.decode('utf-8'), 10)
			except ValueError:
				raise ValueError("Invalid header length %s for packet %s"%(
					x6.decode('utf-8'), x4.decode('utf-8')
				))
				
			if nLen < 1:
				raise ValueError(
					"Packet length (%d) is to short for packet %s"%(
					nLen, x4.decode('utf-8')
				))
					
			xDoc = self._read(nLen)
			self.nOffset += nLen
			sDoc = None
			try:
				sDoc = xDoc.decode("utf-8")
			except UnicodeDecodeError:
				ValueError("Header %s (length %d bytes) is not valid UTF-8 text"(
					x4.decode('utf-8'), nLen
				))
			
			self.lPktDef[nPktId] = True
			
			# Higher level parser will have to give us the length.  This is an
			# oversight in the das2 stream format that has been around for a while.
			# self.lPktSize = ? 
			
			# Also comment and exception packets are not differentiated, in das2.2
			# so we have to read ahead to get the content tag
			if x4 == b'[00]': sTag = 'Hs'
			elif nPktId > 0: sTag = 'Hx'
			elif (x4 == b'[xx]') or (x4 == b'[XX]'):
				if sDoc.startswith('<exception'): sTag = 'He'
				elif sDoc.startswith('<comment'): sTag = 'Hc'
				elif sDoc.find('comment') > 1: sTag = 'Hc'
				elif sDoc.find('except') > 1: sTag = 'He'
				else: sTag = 'Hc'
			
			return Packet(sTag, nPktId, nLen, xDoc)
		
		elif (x4[0:1] == b':') and  (x4[3:4] == b':'):
			# The old das2.2 packets which had no length, you had to parse the
			# header.
			
			if not self.lPktDef[nPktId]:
				raise ValueError(
					"Undefined data packet %s encountered at affset %d"%(
					x4.decode('utf-8'), self.nOffset
				))
			
			if self.lPktSize[nPktId] == None:
				raise RuntimeError(
					"Internal error, unknown length for data packet %d"%nPktId
				)
			
			xData = self._read(self.lPktSize[nPktId])
			self.nOffset += len(xData)
			
			if len(xData) != self.lPktSize[nPktId]:
				raise ValueError("Premature end of packet data for id %d"%nPktId)
			
			return Packet('Dx', nPktId, len(xData), xData)

		raise ValueError(
			"Expected the start of a header or data packet at offset %d"%self.nOffset
		)


	def _nextVarTag(self, x4):
		"""Return the next packet on the stream assuming das2.3+ packaging."""
				
		# Das2.3 uses '|' for field separators since they are not used by
		# almost any other language and won't be confused as xml elements or
		# json elements.
		
		nBegOffset = self.nOffset - 4
		
		# Accumulate the packet tag
		xTag = x4
		nPipes = 2
		while nPipes < 4:
			x1 = self._read(1)
			if len(x1) == 0: break
			self.nOffset += 1
			xTag += x1
			
			if x1 == b'|':
				nPipes += 1
			
			if len(xTag) > 20:
				raise ValueError(
					"Sanity limit of 20 bytes exceeded for packet tag '%s'"%(
						str(xTag)[2:-1])
				)
		
		try:
			lTag = [x.decode('utf-8') for x in xTag.split(b'|')[1:4] ]
		except UnicodeDecodeError:
			raise ValueError(
				"Packet tag '%s' is not utf-8 text at offset %d"%(xTag, nBegOffset)
			)
		
		sTag = lTag[0]
		nPktId = 0
		
		if len(lTag[1]) > 0:  # Empty packet IDs are the same as 0
			try:
				nPktId = int(lTag[1], 10)
			except ValueError:
				raise ValueError("Invalid packet ID '%s'"%x4[1:3].decode('utf-8'))
			
		if (nPktId < 0):
			raise ValueError("Invalid packet ID %d in tag at byte offset %d"%(
				nPktId, nBegOffset
			))
		
		try:
			nLen = int(lTag[2])
		except ValueError:
			raise ValueError(
				"Invalid length '%s' in packet tag at offset %d"%(lTag[2], nBegOffset)
			)
			
		if nLen < 2:
			raise ValueError(
				"Invalid packet length %d bytes at offset %d"%(nLen, nBegOffset)
			)
					
		xDoc = self._read(nLen)
		self.nOffset += len(xDoc)
			
		if len(xDoc) != nLen:
			raise ValueError("Pre-mature end of packet %s|%d at offset %d"%(
				sTag, nPktId, self.nOffset
			))
			
		if isAnyHeader(sTag):
			# In a header packet, insure it decodes to text
			sDoc = None
			try:
				sDoc = xDoc.decode("utf-8")
			except UnicodeDecodeError:
				ValueError("Header %s|%d (length %d bytes) is not valid UTF-8 text"(
					sTag, nPktId, nLen
				))
						
			return Packet(sTag, nPktId, nLen, xDoc)
		else:
			# If this packet is too short, complain
			if nLen < self.lPktSize[nPktId]:
				raise ValueError(
					"Short data packet expected %d bytes found %d for |%s|%d| at offset %d"%(
					self.lPktSize[nPktId], nLen, sTag, nPktId, self.nOffset
				))
				
			# If this data packet has extra content and we are in strict mode
			# then complain
			if self.bStrict and (nLen > self.lPktSize[nPktId]):
				raise ValueError("Strict checking requested, extra content "+\
				  "(%d bytes) not allowed for %s|%d at offset %d"%(
				  nLen - self.lPktSize[nPktId], sTag, nPktId, self.nOffset
				)) 

			# Return the bytes
			return Packet('Dx', nPktId, nLen, xDoc)

# ########################################################################### #

class Das22HdrParser:
	"""Deal with original das2's bad choices on properties elements.  Convert
	a single properties element into a container with sub elements so that
	it can be checked by schema documents
	"""

	def __init__(self):
		self._builder = etree.TreeBuilder() # Save the parse tree here
		
		psr = xml.parsers.expat.ParserCreate('UTF-8') # Don't use namesapaces!
		psr.StartElementHandler  = self._elBeg
		psr.EndElementHandler    = self._elEnd
		psr.CharacterDataHandler = self._elData
		
		self._parser = psr
			
	def _elBeg(self, sName, dAttrs):
		# If we are beginning a properties element, then turn the attributes
		# into individual properties
		
		# Don't let the stream actually contain 'p' elements
		if sName == 'p':
			raise ValueError("Unknown element 'p' at line %d, column %d"%(
				self._parser.ErrorLineNumber, self._parser.ErrorColumnNumber
			))
				
		if sName != 'properties':
			el = self._builder.start(sName, dAttrs)
			el.sourceline = self._parser.CurrentLineNumber
			return el
		
		# Break out weird properity attributes into sub elements.  Fortunatly
		# lxml has a sourceline property we can set manually on elements since
		# we are creating them directly instead of the SAX parser.
		# (Thanks lxml!, Ya'll rock!)
		el = self._builder.start('properties', {})
		el.sourceline = self._parser.CurrentLineNumber
		
		for sKey in dAttrs:
			d = {'name':None}
			v = dAttrs[sKey]
			
			if ':' in sKey:
				l = [s.strip() for s in sKey.split(':')]
				
				if len(l) != 2 or (len(l[0]) == 0) or (len(l[1]) == 0):
					raise ValueError(
						"Malformed <property> attribute '%s' at line %d, column %d"%(
						sKey, self._parser.ErrorLineNumber, 
						self._parser.ErrorColumnNumber
					))
				
				d['name'] = l[1]
				if l[0] != 'String': # Strings are the default, drop the type
					d['type'] = l[0]
				
			else:
				d['name'] = sKey
			
			# Put the 'p' elements directly into the tree.  This keeps real
			# p elements from getting included, don't forget the sourceline
			el = self._builder.start('p', d)
			el.sourceline = self._parser.CurrentLineNumber
			self._builder.data(dAttrs[sKey].strip())
			self._builder.end('p')
		
	def _elData(self, sData):
		sData = sData.strip()		
		self._builder.data(sData)
	
	def _elEnd(self, sName):
		return self._builder.end(sName)
		
	def parse(self, fIn):
		if hasattr(fIn, 'read'):
			self._parser.ParseFile(fIn)
		else:
			self._parser.Parse(fIn, 1)
			
		elRoot = self._builder.close()
		return etree.ElementTree(elRoot)
		
# ########################################################################### #
def getValSz(sType):
	"""das2 type names always end in the size, just count backwards and 
	pull off the digits.  You have to get at least one digit
	"""
	sSz = ""
	for c in reversed(sType):
		if c.isdigit(): sSz += c
		else: break
	
	sSz = ''.join(reversed(sSz))
	return int(sSz, 10)

# ########################################################################### #

def getDataLen(elPkt, sStreamVer, nPktId):
	"""Given a <packet> element, recurse through top children and figure 
	out the data length.  Works for das2.2 and das2.3
	"""
	nSize = 0
	for child in elPkt:
		nItems = 1
		
		if sStreamVer == '2.2':
			# das2.2 had no extra XML elements in packet even in non-strict mode,
			# so everything should have a type attribute at this level
			if 'type' not in child.attrib:
				raise ValueError(
					"Attribute 'type' missing for element %s in packet ID %d"%(
					child.tag, nPktId
				))
			nSzEa = getValSz(child.attrib['type'])
		
			if child.tag == 'yscan':
				if 'nitems' in child.attrib:
					nItems = int(child.attrib['nitems'], 10)
			
			nSize += nSzEa * nItems
			
		elif sStreamVer == '2.3/basic':
		
			# das2.3 will allow extra elements at this level, so only look at
			# the stuff defined in the standard
			if child.tag not in ('x','y','z','w','yset','zset','wset'):
				continue
					
			if child.tag in ('yset','zset','wset'):
				if 'nitems' in child.attrib:
					lItems = [s.strip() for s in child.attrib['nitems'].split(',')]
					for sItem in lItems:
						nItems *= int(sItem, 10)
					
			# Add sizes for all the planes, they all have the same number of items
			# but may have different value sizes
			for subChild in child:
				if subChild.tag == 'array':
			
					# Get the value type
					if 'type' not in subChild.attrib:
						raise ValueError(
							"Attribute 'type' missing for element %s in packet ID %d"%(
							subChild.tag, nPktId
						))
				
					nSzEa = getValSz(subChild.attrib['type'])
					nSize += nSzEa * nItems		
		
		else:
			raise ValueError("Unknown das2 stream version %s"%sStreamVer)
	
	return nSize

# ########################################################################### #

def prnErrorContext(curPkt, nLine):
	sHdr = curPkt.content.decode('utf-8')
	lLines = sHdr.split('\n')

	for i in range(len(lLines)):
		# Trim long lines at 80 characters
		if len(lLines[i]) > 80:
			sLine = lLines[i][:76] + " ..."
		else:
			sLine = lLines[i]
			
		# If we have a valid line number only print within 6 lines each 
		# way of the header
		if (nLine > 0) and abs(nLine - (i+1)) > 6: continue
		
		if i + 1 == nLine:
			pout("    %3d---> %s"%(i+1, sLine))
		else:
			pout("    %3d     %s"%(i+1, sLine))


# ########################################################################### #
def main(form):

	pout('Content-Type: text/plain; charset=utf-8\r\n\r\n')
	
	# Ignore confusing help formatting for now.  (I think newline character
	# insertion in help output is the most requested feature of argparse.)
		
	#psr = argparse.ArgumentParser(
	#	description="das2 stream identifier and validator"
	#)
	
	#psr.add_argument(
	#	'-d', '--schema-dir', default=".", metavar="dir", dest="sSchemaDir",
	#	help="Set the directory to search for schema documents.  Defaults to "+\
	#	"the current directory"
	#)
	#
	#psr.add_argument(
	#	'-s','--schema', default=None, help="Full path to a specific XSD "+\
	#	"schema file to load.  Ignores the directory argument above.  "+\
	#	"By default, %s, %s, %s, or %s are read, depending on the stream "%(
	#	g_sDas23, g_sDas23Strict, g_sDas22, g_sDas22Strict)+\
	#	"version detected and your strict (-S) preference",
	#	dest='sSchema', metavar='schema'
	#)
	#
	#psr.add_argument(
	#	'-e','--expect', default=None, dest="sExpect", metavar="version",
	#	help="Don't auto-detect the stream version.  Only streams that match "+\
	#	"VERSION are validated.  Use one of '2.3/basic', '2.2'."
	#)
	#
	#psr.add_argument(
	#	'-S','--strict', default=False, action="store_true", dest="bStrict",
	#	help="Typically das2 client programs should accept and ignore any "+\
	#	"extra elements or attributes in headers.  Use this option to flag "+\
	#	"any extra attributes, elements, or data as an error"
	#)
	#
	#psr.add_argument(
	#	'-p', '--prn-hdrs', default=False, action="store_true",
	#	help="Print each das2 header encountered in the stream prior to "+\
	#	"schema validation.", dest='bPrnHdr'
	#)
	#
	## End command line with list of files to validate...
	#psr.add_argument(
	#	'lFiles', help='The file(s) to validate', nargs='+', metavar='file'
	#)
		
	#pout(str(form))
		
	if 'file' not in form == 0:
		pout("No input files specified, so... all done right?")
		return 0
	
	formItem = form['file']
	sFile = formItem.filename
	fIn = formItem.file
	
	bStrict = False
	sSchemaDir = '/space/html/das2/verify'
	sExpect = None
	sSchema = None
	bPrnHdr = False
	
	pout("Validating: %s\n\n"%sFile)
	
	# Same parsing state info to help with exception output
	curPkt = None
	sCurType = None
	dDataPktCount = {}
	
	try:
		reader = PacketReader(fIn, bStrict)
		
		sStreamContent, sStreamVer, bVarTags = reader.streamType()
		
		if sStreamContent != 'das2':
			pout("This is a %s stream, expected a das2 stream"%sStreamContent)
			return 5
		
		if sExpect and (sExpect != sStreamVer):
			pout("%s: is a %s stream, but %s was expected"%(
				sFile, sStreamVer, sExpect
			))
			return 5
		
		schema = getSchema(sSchemaDir, bStrict, sSchema, sStreamVer)
		
		for pkt in reader:
			curPkt = pkt
			
			if isDataPacket(pkt.tag):
				dDataPktCount[pkt.id] += 1
				continue
		
			if bPrnHdr:
				pout(pkt.content)
								
			fPkt = BytesIO(pkt.content)
			
			if sStreamVer == '2.2':
				parser = Das22HdrParser()
				docTree = parser.parse(fPkt)
			else:
				docTree = etree.parse(fPkt)
			
			elRoot = docTree.getroot()
			sCurType = elRoot.tag
			
			schema.assertValid(docTree)
			
			# If this packet type needs it, get the length
			if isDataHeader(pkt.tag):
				dDataPktCount[pkt.id] = 0
				nDatLen = getDataLen(elRoot, sStreamVer, pkt.id)
				reader.setDataSize(pkt.id, nDatLen)
				pout("|%s| ID %s %s header [OKAY] (data size %d bytes)"%(
					pkt.tag, pkt.id, sCurType, nDatLen
				))
			else:
				pout("|%s| ID %s %s header [OKAY]"%(pkt.tag, pkt.id, sCurType))
				
			curPkt = None
			sCurType = None
	
	except(
		ValueError, etree.XMLSyntaxError, etree.DocumentInvalid, 
		xml.parsers.expat.ExpatError
	) as e:
		if curPkt:
			if sCurType:
				pout("|%s| ID %s %s header [ERROR] (context follows)"%(curPkt.tag, curPkt.id, sCurType))
			else:
				pout("|%s| ID %s data [ERROR]"%(pkt.tag, pkt.id))
			
		# Try to get last line with an error
		nLine = -1
		if isinstance(e, (etree.XMLSyntaxError, etree.DocumentInvalid)):
			#pout(e.error_log)
			nLine = e.error_log[-1].line
		elif isinstance(e, xml.parsers.expat.ExpatError):
			nLine = e.lineno
		
		# Print context if we can get it
		if curPkt and isAnyHeader(curPkt.tag):
			try:
				prnErrorContext(curPkt, nLine)
			except:
				# Assumption here
				pout("Header packet %s%d is not valid UTF-8 text"%(
					curPkt.tag, curPkt.id))
		
		# Hack the non-existent 'p' element back out of any das2.2 error messages
		sErr = str(e)
		if sStreamVer == '2.2' and sErr.startswith("Element 'p',"):
			sFind ="Element 'p', attribute 'type': [facet 'enumeration'] The value"
			sRep = "Element 'properties', the attribute qualifier"
			sErr = sErr.replace(sFind, sRep)
		pout(sErr)
		
		#pout(type(e), "\n   dir:", dir(e.error_log[-1]), '\n   msg:', e.error_log[-1].message)
		#pout("Error in %s:\n%s"%(sFile, str(e)))
		return 5
				
	for nId in dDataPktCount:
		pout("|Dx| ID %d %d data packets [OKAY]"%(nId, dDataPktCount[nId]))
	
	if bStrict:
		pout('Stream validates as a strict %s version %s stream without extensions\n'%(
			sStreamContent, sStreamVer))
	else:	
		pout('Stream validates as a %s version %s stream\n'%(
			sStreamContent, sStreamVer))

	return 0	

##############################################################################
# Stub main for cgi

form = cgi.FieldStorage()

# Return values don't matter in CGI programming.  That's unfortunate
main(form)

