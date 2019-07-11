"""Helpers for running sub-commands"""

import sys
import subprocess
import select
import fcntl
import os

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')

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
				sRead = proc.stdout.read()
				if len(sRead) != 0:
					
					if not bHttpHdrsSent:
						pout("Content-Type: %s"%sMimeType)
						pout("Status: 200 OK")
						pout("Expires: now")
						pout('Content-Disposition: %s; filename="%s"\r\n'%(
						      sContentDis, sOutFile))
						sys.stdout.flush()
						bHttpHdrsSent = True
					
					sys.stdout.write(sRead)
					sys.stdout.flush()
				
			if fd == fdStdErr:
				sRead = proc.stderr.read()
				if len(sRead) != 0:
					fLog.write(sRead)
					lStdErr.append(sRead)
		
		if bBreakNext:
			break
		
		if proc.poll() != None:
			# Go around again to make sure we have read everything
			bBreakNext = True
	
	
	fLog.write("Finished Read")
	
	sStdErr = "".join(lStdErr)
	
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
				sRead = proc.stdout.read()
				if len(sRead) != 0:
					lStdOut.append(sRead)
				
			if fd == fdStdErr:
				sRead = proc.stderr.read()
				if len(sRead) != 0:
					fLog.write(sRead)
					lStdErr.append(sRead)
		
		if bBreakNext:
			break
		
		if proc.poll() != None:
			# Go around again to make sure we have read everything
			bBreakNext = True
	
	
	fLog.write("Finished Read")
	
	sStdErr = "".join(lStdErr)
	sStdOut = "".join(lStdOut)
	
	return (proc.returncode, sStdOut, sStdErr)
