# This is free and unencumbered software released into the public domain.
# 
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
# 
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
# 
# For more information, please refer to <http://unlicense.org>

"""This reader provides a complex example of read CDF files with many
different options and outputs.

Unlike the other two example readers, the behavior of this reader can be
modified by via a third argument, the reader parameters.  The CDF files 
backing this dataset contain 21 correlation components.  For the
Autocorrelations only the magnitude matters, for the cross correlations we
have to be able to output both phase and magintude data.

By default data are transimitted as magnitude and phase variables, but the
keyword 'complex' with trigger output as real and imaginary arrays instead.
For autocorrelations the phase information is 0 so it's dropped from the
output.

See the Params.dsdf file for details.
"""

import sys
import os
import optparse
import logging
import struct

from os.path import basename as bname
from os.path import dirname as dname
from os.path import join as pjoin

import numpy as np
import das2

try:
	# Try one of the included pycdf modules, we do this first because
	# it should not be on the path if it's not needed.
	import pycdf
	from pycdf import const
except ImportError:
	try:
		from spacepy import pycdf        # actually, the normal situation
		from spacepy.pycdf import const
	except ImportError:
		sMsg = "ERROR: Install spacepy or symlink a fallback pycdf module "+\
		       "into das2srv/lib/pythonX.X as described in fallback_pycdf.txt.\n"
		sys.stderr.write(sMsg)
		sys.exit(7)

# ########################################################################### #
# General code to deal with python2/3 and unicode/bytes

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

def writeHdrPkt(nId, thing):
	if isinstance(thing, unicode):  thing = thing.encode('utf-8')
	
	if isinstance(nId, int): write("[%02d]%06d"%(nId, len(thing)))
	else: write("[xx]%06d"%len(thing))
	write(thing)
	flush()


# ########################################################################## #
# Convert a handful of numpy type values to das2.2 stream output types

g_dNpToDasTypeMap = {
	'<f4':'little_endian_real4',
	'<f8':'little_endian_real8',
	'>f4':'sun_real4',
	'>f8':'sun_real8'
}

# Used for binary time output
if sys.byteorder == 'little':   
	_g_sDoubleType = "little_endian_real8" 
else:
	_g_sDoubleType = "sun_real8"

##############################################################################
# Generic python logging Setup

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
	
# ########################################################################### #
# Generic CDF global attribute writing, should probably put this in a library

g_lAsIntTypes = [
	const.CDF_INT1.value, const.CDF_INT2.value,
	const.CDF_INT4.value, const.CDF_INT8.value,
	const.CDF_UINT1.value, const.CDF_UINT2.value,
	const.CDF_UINT4.value, const.CDF_BYTE.value
]

g_lAsDoubleTypes = [
	const.CDF_FLOAT.value, const.CDF_DOUBLE.value
]

def cdfToDas22Hdr(cdf, lIgnore=[], dExtra={}):
	"""Write all the Constant CDF properties into a das2.2 header. 
	Don't include changable parameter ranges since we'll probably build a cache
	and these won't be valid anyway.
	
	Das2.2 has some restrictions that the upcomming das2.3 protocol won't have
	but as of 2019-07-01 no clients understand that protocol yet.	
	"""
	
	lOut = [u'<stream version="2.2">',u'  <properties']
	
	lKeys = list(cdf.attrs.keys())
	lKeys.sort
	
	for sKey in lKeys:
		if sKey in lIgnore: continue

		# If the key starts with a little x, y or z drop it because this
		# will interfer with the simplistic encoding used for das2.2 streams.
		# will be fixed for general das2.3 streams.
		if sKey[0] in 'xyz': continue
		
		sVal = str(cdf.attrs[sKey])
		sVal = sVal.replace('"', "'") # Convert any " charaters to '
		sVal = sVal.replace('\n',' ') # re-wrap (or rather de-wrap)
		sVal = sVal.strip()
		
		# Don't send empty values 
		if len(sVal) == 0: continue
		
		# By default encode as string except for a few known numeric types
		nCdfType = cdf.attrs[sKey].type(0)  # Just look at first one
		
		if nCdfType in g_lAsDoubleTypes: sType = u"double:"
		elif nCdfType in g_lAsIntTypes:  sType = u"int:"
		else: sType = u""
		
		lOut.append(u'    %s%s="%s"'%(sType, sKey, sVal))
		
	
	# Add in any extra parameters the caller has specified
	for sKey in dExtra:
		lOut.append(u'    %s="%s"'%(sKey, dExtra[sKey]))
			
	lOut.append(u'  />')
	lOut.append(u'</stream>')
	
	sOut = u'\n'.join(lOut)
	sOut += u'\n'
	writeHdrPkt(0, sOut)
	
# ########################################################################### #
# Utility to make title using VESPA metadata, reader specific
	
def getVespaTitle(cdf, sDefault, lComp):
	
	sTitle = sDefault
	if 'VESPA_instrument_host_name' in cdf.attrs:
		sTitle = str(cdf.attrs['VESPA_instrument_host_name'])
		if 'VESPA_receiver_name' in cdf.attrs:
			sTitle = "%s : %s"%(sTitle, str(cdf.attrs['VESPA_receiver_name']))
	
	# Throw names of components into the title
	sTitle = "%s, %s"%(sTitle, " ".join(["%s*"%s for s in lComp] ))
	return sTitle


# ########################################################################### #
# Utility function for getting correlation location, specific to this reader

# Notes on the BB_xyz_xyz, EE_xyz_xyz and BE_xyz_xyz variables
#
# BB_xyz_xyz has the shape (for example):
# 
#    [100, 6, 2, 164]
#      ^   ^  ^   ^
#      |   |  |   |
#      |   |  |   +-- Varies with frequency
#      |   |  |  
#      |   |  +-- Real & complex components, only serving autocorrelations
#      |   |      so imaginary part is always 0.
#      |   |
#      |   +-- Varies by component (BxBx, ByBy, we want 0, 3, 5)
#      |
#      +-- Varies by time
#
# EE_xyz_xyz has a similar layout

def getComp(cdf, lComp):
	"""Get information on the CDF varibles that we want to transmit
	Args:
		cdf (pycdf.CDF) : A CDF object containing the THEMIS correlation
			variables
		lComp (list, str) : The list of correlation components to send
		bPolar (bool) : If true output magnitude and phase angle 
	
	Returns:
		list: 
			A list of tuples, one for each component to output, in alphabetical
			order by component name. Each entry contains a tuple of the
			following items:
			   (sComp - The name of the component
				 sVar -  The name of the CDF variable that has the component
				 iIdx - The index of the variable in BB_xyz_xyz, EE_xyz_xyz,
				        or BE_xyz_xyz
				 bAuto - True if this is an autocorrelation and so imaginary
				        part is always 0
            )
	"""
	_lComp = list(lComp)
	_lComp.sort()
	
	# Used to invert the labels and get the index of the component, the
	# strip command converts this 'BxEy*   ' -to-> 'BxEy'.
	var = cdf['SM_BB_LABEL']
	lBB = [str(var[i]).strip('* ')  for i in range( var.shape[0] )]
	
	var = cdf['SM_EE_LABEL']
	lEE = [str(var[i]).strip('* ')  for i in range( var.shape[0] )]
	
	var = cdf['SM_BE_LABEL']
	lBE = [str(var[i]).strip('* ')  for i in range( var.shape[0] )]
	
	
	lOut = []
	for sComp in _lComp:
		sVar = 'BB_xyz_xyz'
		bAuto = (sComp[:2] == sComp[2:]) # if same vars, it's an autocoor
		lLabels = lBB
		
		if 'E' in sComp:
			if 'B' in sComp:
				sVar = 'BE_xyz_xyz'
				lLabels = lBE
			else:
				sVar = 'EE_xyz_xyz'
				lLabels = lEE
		
		# Next line may throw.  Since we can't take any alternate actions if it
		# does, don't add in any special error handling. Just let the das2 server
		# log the resulting standard error stream.
		iIdx = lLabels.index(sComp)
		lOut.append( (sComp, sVar, iIdx, bAuto) )
		
	return lOut

# ########################################################################### #
# Grab variable attributes and send a packet header.  Reader specific code

def sendPktHdr(cdf, lComp, bPolar):
	"""Send a packet definition for a given set of E and B components.
	Args:
		cdf (pycdf.CDF) : The CDF object, various metadata are pulled from
		   this object to generate the packet header.
		lComp (list, str) : A list of the correlations to transmit
		bPolar (bool) : If true send Magnitude and Phase
	"""

	# Get the CDF variable name and item index for each component and 
	# whether the component is an autocorrelation or a cross correlation.
	lCompInfo = getComp(cdf, lComp)

	lHdr = [
		'<packet>',
		'  <x type="%s" units="t2000">'%_g_sDoubleType,
		'    <properties Datum:xTagWidth="0.5 s" />',
		'  </x>'
	]
	
	for tInfo in lCompInfo:
		(sComp, sVar, iIdx, bAuto) = tInfo
		nFreq = cdf['FREQUENCY'].shape[0]
		sFreqs = ','.join( ["%.6e"%r for r in cdf['FREQUENCY'][:] ] )
		sFreqUnits = cdf['FREQUENCY'].attrs['UNITS']
		sDatUnits = cdf[sVar].attrs['UNITS'].replace('^','**')
		
		# For effiency, let's output data in the same format at they are
		# stored in the numpy arrays created by pycdf.
		
		sDasType = g_dNpToDasTypeMap[ cdf[sVar][:].dtype.str ]
		
		# For autocorrelations we are only going to output the real part,
		# no need to decorate the name
		if bAuto:
			sName = sComp
			sLabel = '%s* (%s)'%(sComp, sDatUnits)
			
		else:
			if bPolar:
				sName = sComp + "_magnitude"
				sLabel = '%s* Magnitude (%s)'%(sComp, sDatUnits)
			else:
				sName = sComp + "_real"
				sLabel = '%s* Real (%s)'%(sComp, sDatUnits)
		
		# Do real part (or magnitude) plane
		
		lHdr += [
			'  <yscan type="%s" name="%s" nitems="%d" zUnits="%s" yUnits="%s"'%(
				sDasType, sName, nFreq, sDatUnits, sFreqUnits
			),
			
			'    yTags="%s"'%sFreqs, 
			'  >',
			'    <properties yLabel="Frequency (%s)"'%sFreqUnits,
			'                zLabel="%s"'%sLabel,
			'                yScaleType="%s"'%cdf['FREQUENCY'].attrs['SCALETYP'],
			'    />',
			'  </yscan>'
		]
		
		# If this is a cross correlation, add in the phase (or imaginary) var
		if not bAuto:
			if bPolar:
				sName = sComp + "_phase"
				sLabel = '%s* Phase (%s)'%(sComp, sDatUnits)
				sDatUnits = "degrees"
			else:
				sName = sComp + "_img"
				sLabel = '%s* Imaginary (%s)'%(sComp, sDatUnits)
		

			lHdr += [
				'  <yscan type="%s" name="%s" nitems="%d" zUnits="%s" yUnits="%s"'%(
					sDasType, sName, nFreq, sDatUnits, sFreqUnits
				),
				
				'    yTags="%s"'%sFreqs, 
				'  >',
				'    <properties yLabel="Frequency (%s)"'%sFreqUnits,
				'                zLabel="%s"'%sLabel,
				'                yScaleType="%s"'%cdf['FREQUENCY'].attrs['SCALETYP'],
				'    />',
				'  </yscan>'
			]
		
	
	lHdr += [ '</packet>']
	
	sHdr = '\n'.join(lHdr)
	sHdr += '\n'
	writeHdrPkt(1, sHdr)
	flush()
	

# ########################################################################### #
# Send data packets, dataset specific #

g_bHdrSent = False  # Only need to send the header once per run

def sendDataPackets(cdf, dtBeg, dtEnd, lComp, bPolar):

	"""Output all packets for a given file that are within the specified time
	range.
	
	Globals:
		g_bHdrSent: Tracks whether a header has been sent for this particular
		            variable set, and if so what is it's packet ID.	
	Args:
		sFile (str): The name of the CDF file
		
		dtBeg (DasTime): The inclusive lower bound minimum time to output
		
		dtEnd (DasTime): The exclusive upper bound maximum time to output
		
		lComp (list) : A list of the correlations to output, defaults to all
		               the autocorrelations
							
		bPolar (bool) : If True output Magnitude and Phase angle instead of 
		                real and imaginary components
	Returns:
		bool : True if output should continue, False if done.
		
	"""
	
	global g_bHdrSent
	
	lCompInfo = getComp(cdf, lComp)
	
	aTime = cdf['Epoch']
	
	# Output data in range
	nPkts = 0
	for i in range( aTime.shape[0] ):
		dt = das2.DasTime(aTime[i])
		
		if dt < dtBeg or dt >= dtEnd: continue
		
		if not g_bHdrSent:
			sendPktHdr(cdf, lComp, bPolar)
			g_bHdrSent = True
		
		write(':01:')
		
		# Various time encodings are supported by das2, we've somewhat randomly
		# chosen T2000, which happens to be seconds since 2000-01-01T00:00:00
		# ignoring leap seconds
		xTime = struct.pack("=d", dt.t2000())
		
		write( xTime )
		
		# Write the data for all the selected components
		for tInfo in lCompInfo:
			(sComp, sVar, iIdx, bAuto) = tInfo
			
			aRe = cdf[sVar][i, iIdx, 0, : ]
			
			# Optimization:  We specified numpy byte order so that we can
			# kick raw numpy bytes out the door without converting them.
			# only works if we don't have to do any calculations
			if bAuto:
				write( aRe.tobytes() )
			else:
				aIm = cdf[sVar][i, iIdx, 1, : ]
				
				
				if bPolar:
					aCplx = np.empty(aRe.shape, dtype=complex)
					aCplx.real = aRe
					aCplx.imag = aIm
					
					# Make sure we use the same internal representation as the 
					# original arrays because we are dumping binaries...
					aMag = np.absolute(aCplx).astype(aRe.dtype)
					aPhase = np.angle(aCplx, deg=True).astype(aRe.dtype)
					
					write(aMag.tobytes())
					write(aPhase.tobytes())
				else:
					write(aRe.tobytes())
					write(aIm.tobytes())
			
		# Flush packets as we go
		flush()
		nPkts += 1
			
	return nPkts

# ########################################################################### #
# Generic reporting of improper program invocation #

def queryErr(log, sMsg):
	log.error("Query error, %s"%sMsg)
	writeHdrPkt(0, '<stream version="2.2" />\n')
	sMsg = sMsg.replace('"', "'")
	sOut = '<exception type="IllegalArgument" message="Query error, %s" />\n'%sMsg
	writeHdrPkt('xx', sOut)
	
def serverErr(log, sMsg):
	log.error("Server error, %s"%sMsg)
	writeHdrPkt(0, '<stream version="2.2" />\n')
	sMsg = sMsg.replace('"', "'")
	sOut = '<exception type="ServerError" message="Server error, %s" />\n'%sMsg
	writeHdrPkt('xx', sOut)


# ########################################################################### #
def main(argv):
	
	sUsage = "%%prog [options] DATA_DIRECTORY BEGIN END"
	sDesc = """
Reads Themis spectral density auto-correlation values from archive CDFs.
Format is similar to the Cluster Active Archive, see document: CAA-EST-UG-002
for details.
"""

	psr = optparse.OptionParser(
		usage=sUsage, description=sDesc, prog=bname(argv[0])
	)
	
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
		return queryErr(log, "Start and or Stop time is missing")
		
	try:
		dtBeg = das2.DasTime(lArgs[1])
	except:
		return queryErr(log, "Couldn't parse time value '%s'"%lArgs[1])
	try:
		dtEnd = das2.DasTime(lArgs[2])
	except:
		return queryErr(log, "Couldn't parse time value '%s'"%lArgs[2])
	
	# Take all the rest of the arguments and glop them together in a single
	# string.  That way running the reader from the command line feels the
	# same as running it from Autoplot	
	sParams = ''
	if len(lArgs) > 3: sParams = ' '.join(lArgs[3:])
	
	# pull out the polar style output, i.e: Magnitude and Phase Angle
	bPolar = True
	if sParams.find('complex') != -1:
		sParams = sParams.replace('complex','').strip()
		bPolar = False

	# Default to printing all the autocorrelations
	sComp = 'BxBx ByBy BzBz ExEx EyEy EzEz'
	if len(sParams) > 0: sComp = sParams
	lComp = sComp.split()
	lComp.sort()
	
	
	# Look in directory tree for files that match.  We sort the file names
	# under the assumption that sort order = numerical time order, but that
	# may not be true for some file types
	lDir = os.listdir(sRoot)
	lDir.sort()
	
	nSent = 0
	bSentHdr = False
	for sF in lDir:
		if not sF.endswith('.cdf'): continue             # only want CDFs
		if not sF.startswith('tha_l3_sm'): continue      # Only want L3 SM
		
		# Make ISO-8601 strings
		sBeg = "%s-%s-%sT%s:%s:%s"%(
			sF[10:14], sF[14:16], sF[16:18], sF[19:21], sF[21:23], sF[23:25]
		)
		sEnd = "%s-%s-%sT%s:%s:%s"%(
			sF[26:30], sF[30:32], sF[32:34], sF[35:37], sF[37:39], sF[39:41]
		)
		
		sPath = pjoin(sRoot, sF)
		
		try:
			dtFileBeg = das2.DasTime(sBeg)
			dtFileEnd = das2.DasTime(sEnd)
			
			# Since the themis files truncate the seconds field, round up by
			# one second for the file end time...
			dtFileEnd += 1.0
			
		except ValueError as e:
			log.waring("Unknown file %s in data area"%sPath)
			continue
		
		# If overlaps with desired range, include it in the output, send header
		# if haven't done so
		if (dtFileBeg < dtEnd) and (dtFileEnd > dtBeg):
			log.info("Reading %s"%sPath)
			cdf = pycdf.CDF(sPath)
		
			# Assmue all the files are similar enough that an informational 
			# header can be created from the first one that fits the range
			if not bSentHdr:
				lIgnore = ['TIME_MAX','TIME_MIN', 'TIME_resolution']
				dExtra = {
					'title':getVespaTitle(cdf, 'THEMIS', lComp), 
					'Datum:xTagWidth':'0.5 s'  # Max interp width for Autoplot
				}
				cdfToDas22Hdr(cdf, lIgnore, dExtra)
				bSentHdr = True
			
			nSent += sendDataPackets(cdf, dtBeg, dtEnd, lComp, bPolar)
		
	if nSent == 0:
		if not bSentHdr: writeHdrPkt(0, '<stream version="2.2" />\n')
		sFmt = '<exception type="NoDataInInterval" message="%s" />\n'
		sOut = sFmt%("No data in interval %s to %s UTC"%(str(dtBeg), str(dtEnd)))
		writeHdrPkt('xx', sOut)
	
	return 0
	
# ########################################################################### #
if __name__ == "__main__":
	sys.exit( main(sys.argv) )
