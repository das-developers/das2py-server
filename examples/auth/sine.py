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

import sys
import random
import math as M

import das2 as D

##############################################################################
def getLogVec(nX, iX, nY, rZmin, rZmax):
	"""make a gausian smeared sign wave that oscillates twice from iBeg to iEnd
	and logrithmically covers rZmin to rZmax. 
	"""
	
	# Make the gausian centered a sin wave
	iYcent = int( (nY/2) * M.sin(4*M.pi*iX/nX) + nY/2 ) 
		
	rZrng = (rZmax - rZmin)
	
	rZnoiseRng = rZrng/8.0
	
	lVec = [None]*nY
	
	for iY in range(0, nY):
		
		rNum = (iY - iYcent)*(iY - iYcent)
		
		# Pick 1/8 the y range as the width
		rDen = 2*nY*nY/(64.0)
		
		rZ = rZrng * M.pow(M.e, -rNum/rDen) + rZmin
	
		#print nY, iYcent, iY, rNum, rDen, M.pow(M.e, -rNum/rDen), rZ
	
		# Add noise
		rZ = rZ + random.random()*rZnoiseRng
		
		lVec[iY] = M.pow(10.0, rZ)

	return lVec


##############################################################################
def sendHdr(dtBeg, dtEnd, fOut):

	rSec = dtEnd - dtBeg
	rInterpWidth = rSec/200

	# First header is always the stream header, send an interpolation with
	buf = D.DasHdrBuf(0)
	buf.add(u'<stream version="2.2">\n')
	buf.add(u'''  <properties
    Datum:xTagWidth="%.3g s"
    double:zFill="-1.0"
    String:title="Das 2.2 Server Test Data!c(Looks like your server works)"
    String:xLabel="Time"
    String:yLabel="Frequency (Hz)"
    String:yScaleType="log"
    String:zLabel="Spectral Density (V!a2!n m!a-2!n Hz!a-1!n)"
    String:zScaleType="log"
  />
</stream>
'''%rInterpWidth)
	
	buf.send(fOut)
	
	lYTags = [1]*100
	for i in range(0,100):
		lYTags[i] = "%.4g"%(pow(10, (3*i)/100.0) + 66.0)
	
	sYTags = ', '.join(lYTags)
	
	buf = D.DasHdrBuf(1)
	buf.add(u'''<packet>
  <x type="time24" units="us2000"></x>
  <yscan name="lfr_lo_e" type="ascii11" nitems="100" yUnits="Hz" zUnits="V**2 m**-2 Hz**-1"
         yTags="%s">
  </yscan>
</packet>
'''%sYTags)

	buf.send(fOut)
	

##############################################################################
def main(argv):
	"""Transmit a test dataset of 300 spectra given any input times
	"""
	
	perr = sys.stderr.write
	
	if len(argv) < 3:
		perr("Expected command line %s START_TIME END_TIME [PARAMETERS]\n")
		perr("Any times are fine as long as they are parseable and start < end\n")
		return 10
	
	dtBeg = D.DasTime(argv[1])
	dtEnd = D.DasTime(argv[2])
	
	if dtBeg >= dtEnd:
		perr("Start time (%s) is >= end time (%s)"%(str(dtBeg), str(dtEnd)))
		return 11
	
	sendHdr(dtBeg, dtEnd, sys.stdout)
	
	rSec = dtEnd - dtBeg
	rCadence = rSec/300
	
	# Randomly pick 3 sets of ten vectors to skip
	lSkip = []
	for i in range(0, 3):
		n = random.randrange(300)
		for j in range(0,10):
			if n < 289:
				lSkip.append(n + j)
			else:
				lSkip.append(n - j)
	
	# Randomly pick 30 other vectors to contain fill
	lFill = []
	for i in range(0, 30):
		lFill.append( random.randrange(300) )
	
	lSkip.sort()
	
	# Okay, start producing data
	dt = dtBeg.copy()
	for iX in range(0, 300):
		
		dt.adjust(0, 0, 0, 0, 0, rCadence)  # Yea this can get round off errors
		                                    # but it's only a test function
		if iX in lSkip:
			continue
		
		if iX in lFill:
			lVec = [-1.0]*100		
		else:
			lVec = getLogVec(300, iX, 100, -18.0, -6.0)
	
		buf = D.DasPktBuf(1)
		buf.add(dt.round(dt.MILLISEC))
		buf.add(" ")
		
		for iY in range(0, 100):
			if iY < 99:
				buf.add("%10.3e "%lVec[iY])
			else:
				buf.add("%10.3e\n"%lVec[iY])
				
		buf.send(sys.stdout)
		
	return 0

	
##############################################################################
if __name__ == '__main__':
	main(sys.argv)
