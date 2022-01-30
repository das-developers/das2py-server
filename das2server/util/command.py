"""Helpers for running sub-commands"""

import sys
import subprocess
import select
import fcntl
import os

from . import webio

# ########################################################################## #
# Default Command templates, could make this external #

g_dDefCmds = {

"psd":{
	"trigger":{"key":"dft.length"},
	"order":2,
	"template":["das2_psd -d -j 0.05 #[dft.length] #[dft.slide] "],
	"input":"application/vnd.das2.das2stream",
	"output":"application/vnd.das2.das2stream"
},

"bin":{
	"trigger":{"key":"bin.time.max","value":0,"compare":"gt"},
	"order":3,
	"template":[ 
		"das2_bin_avgsec #bin.time.max# ",
		"#[read.time.min| -b @ | ]  #[bin.merge/min| -r | ] #[bin.merge/max| -r | ]#",
	],
	"input":"application/vnd.das2.das2stream",
	"output":"application/vnd.das2.das2stream"
},
	
"format.csv":{
	"trigger":{"key":"format.mime","value":"text/csv"},
	"order":4,
	"template":[
		"das2_csv",
		"#[-d #format.delim#|]#",
		"#[-s #format.secfrac#|]#",
		"#[-r #format.sigdigit#|]#"
	],
	"input":"application/vnd.das2.das2stream",
	"output":"text/csv"
},

"format.png":{
	"trigger":{"key":"format.mime","value":"image/png"},
	"order":4,
	"template":[
		"autoplot_url2png.py",
		"server=#SERVER#",
		"dataset=#DATASET#",
		"start_time=#read.time.min#",
		"end_time=#read.time.max#",
		"image=#FILE#",
		"param=#[#read.options#|]#"
	],
	"input":"application/vnd.das2.das2stream",
	"output":"image/png"
}

}


##############################################################################
def sendCmdOutput(fLog, uCmd, sMimeType, sContentDis, sOutFile):
	"""Send the output of a command pipeline as an HTTP message body.
	
	Standard output is sent on as an http message body, standard error
	output is spooled and send back to the caller.  Output is:
	
	   ( return_code,  stderr_output, hdrs_flag)
		
	return_code - The value returned by the sub-shell that can the command
	
	stderr_output - A string containing the output of the standard error
	                channel form the sub-command
	
	hdrs_flag  - This is true if any HTTP headers have already been sent,
	             false otherwise.
	
	NOTE: This handles writing HTTP Headers AND the response body.
	"""
	
	# We can't output the HTTP headers until we know that running program
	# doesn't produce an error.  But we don't want to buffer all the data
	# until it finishes.
	
	# Solution: Check the 1st non-zero read from stdout, if it starts
	# with anything that looks like <stream> then you're good, say it's data
	
	# Change shell=False, and fix fillDsdfDefaults to work on windows
	proc = subprocess.Popen(uCmd, shell=True, stdout=subprocess.PIPE, 
	                        stderr=subprocess.PIPE, bufsize=-1)
	
	fdStdOut = proc.stdout.fileno()
	fdStdErr = proc.stderr.fileno()
	
	fl = fcntl.fcntl(fdStdOut, fcntl.F_GETFL)
	fcntl.fcntl(fdStdOut, fcntl.F_SETFL, fl | os.O_NONBLOCK)
	
	fl = fcntl.fcntl(fdStdErr, fcntl.F_GETFL)
	fcntl.fcntl(fdStdErr, fcntl.F_SETFL, fl | os.O_NONBLOCK)
	
	bBreakNext = False
	bHttpHdrsSent = False
	lStdErr = []
		
	while True:
		lReads = [fdStdOut, fdStdErr]
		lReady = select.select(lReads, [], [])
		
		for fd in lReady[0]:
			
			if fd == fdStdOut:
				xRead = proc.stdout.read()
				if len(xRead) != 0:
					
					if not bHttpHdrsSent:
						webio.pout('Access-Control-Allow-Origin: *\r\n')
						webio.pout('Access-Control-Allow-Methods: GET\r\n')
						webio.pout('Access-Control-Allow-Headers: Content-Type\r\n')	
						webio.pout("Content-Type: %s\r\n"%sMimeType)
						webio.pout("Status: 200 OK\r\n")
						webio.pout("Expires: now\r\n")
						webio.pout('Content-Disposition: %s; filename="%s"\r\n\r\n'%(
						      sContentDis, sOutFile))
						webio.flushOut()
						bHttpHdrsSent = True
					
					webio.pout(xRead)
					webio.flushOut()
				
			if fd == fdStdErr:
				xRead = proc.stderr.read()
				if len(xRead) != 0:
					#fLog.write(xRead)
					lStdErr.append(xRead)
		
		if bBreakNext:
			break
		
		if proc.poll() != None:
			# Go around again to make sure we have read everything
			bBreakNext = True
	
	
	fLog.write("Finished Read")
	
	if sys.version_info[0] == 2:
		sStdErr = ''.join(lStdErr)
	else:
		xStdErr = b''.join(lStdErr)
		sStdErr = xStdErr.decode('utf-8')
	
	return (proc.returncode, sStdErr, bHttpHdrsSent)

##############################################################################
# Suitable for commands that should produce a few KB of output

def getCmdOutput(fLog, uCmd):
	"""run a command and get it's return code, standard output and standard
	error.  This buffers the entire output in memory, so don't use this if
	a large amount of output is expected.
	"""
	
	proc = subprocess.Popen(uCmd, shell=True, stdout=subprocess.PIPE, 
	                        stderr=subprocess.PIPE, bufsize=-1)
	
	fdStdOut = proc.stdout.fileno()
	fdStdErr = proc.stderr.fileno()
	
	fl = fcntl.fcntl(fdStdOut, fcntl.F_GETFL)
	fcntl.fcntl(fdStdOut, fcntl.F_SETFL, fl | os.O_NONBLOCK)
	
	fl = fcntl.fcntl(fdStdErr, fcntl.F_GETFL)
	fcntl.fcntl(fdStdErr, fcntl.F_SETFL, fl | os.O_NONBLOCK)
	
	bBreakNext = False
	lStdOut = []
	lStdErr = []
	while True:
		lReads = [fdStdOut, fdStdErr]
		lReady = select.select(lReads, [], [])
		
		for fd in lReady[0]:
			
			if fd == fdStdOut:
				xRead = proc.stdout.read()
				if len(xRead) != 0:
					lStdOut.append(xRead)
				
			if fd == fdStdErr:
				xRead = proc.stderr.read()
				if len(xRead) != 0:
					fLog.write(xRead)
					lStdErr.append(xRead)
		
		if bBreakNext:
			break
		
		if proc.poll() != None:
			# Go around again to make sure we have read everything
			bBreakNext = True
	
	
	fLog.write("Finished Read")
	
	if sys.version_info[0] == 2:
		sStdErr = "".join(lStdErr)
		sStdOut = "".join(lStdOut)
	else:
		xStdErr = b''.join(lStdErr)
		xStdOut = b''.join(lStdOut)
		sStdErr = xStdErr.decode('utf-8')
		sStdOut = xStdOut.decode('utf-8')
	
	return (proc.returncode, sStdOut, sStdErr)
