"""Helpers for running sub-commands"""

import sys
import subprocess
import select
import fcntl
import os

from . import webio
from . import errors as E

# ########################################################################## #
# Helpers #
def _list2Str(thing):
	if isinstance(thing, list):
		return " ".join(thing)
	else:
		return thing

# ########################################################################## #
def _collapseByMime(dInOrder):
	"""Solve the g'zin, g'zout problem in one of two ways.
	1. If the first command is unique, forward propogate.
	2. If the last command is unique, back propogate

	Args:
		dInOrder, a dictionary where each key is the ordering value for the
			commands to run, and each value is a list of command objects 
			(dictionary).  Each command object must have the following keys:
			input: The input mime type
			output: The output mime type
			template: The command template to run

	Returns:
		An orderd list of command templates.
	"""

	lOrders = list(dInOrder.keys())
	lOrders.sort()
	bUnique = False
	lTplts = []

	if len(dInOrder[ lOrders[0] ]) == 1:

		dCmd = dInOrder[ lOrders[0] ][0]
		lTplts.append( _list2Str(dCmd['template'])  )

		sGzin = dCmd['output']   # Input for next stage

		for i in range(1, len(lOrders)):  # Loop over all remaining stages

			lCmds = dInOrder[ lOrders[i] ]
			iFound = -1
			for j in range(len(lCmds)):
				if lCmds[j]['input'] == sGzin:
					if iFound == -1: iFound = j
					else: iFound == -1

			if iFound == -1:
				raise E.ServerError("No unique input choice for mime %s and stage %s"%(
					sGzin, lCmds[j]['stage']
				))
			
			dCmd = lCmds[iFound]
			lTplts.append( _list2Str(dCmd['template']))
			sGzin = dCmd['output']

	if (not bUnique) and (len( dInOrder[ lInOrder[-1] ]) == 1):


	if not bUnique
		raise E.QueryError("Ambiguous request, could not resolve query to an unique command set.")


# ########################################################################## #
# Upstream Solver #

def upstreamCmdSolver(dConf, dDefault, dSrc, dParams):
	"""Given a default set of command templates, a source definition and
	a set of HTTP params, produce a command line "solution" for stream 
	generation.  

	This version does not consider the cache system at all.  For a version
	that attemps to generate a cache command read, see the cache.py module.

	Returns (string): 
		The command line to run to generate the data, or None if no suitable
		command line could be generated that satisfies all the given 
		parameters.
	"""

	# Make a complete set of commands
	if ('internal' not in dSrc) or ('command' not in dSrc['internal']):
		raise E.ServerError("No commands in source from '%s'"%dSrc['__path__'])
		

	lCmds = deepcopy(dDefault)
	for dCmd in dSrc['internal']['commands']:
		_overrideCmd(lCmds, dCmd)

	if 'disable' in dSrc['internal']:
		_filterCmds(lCmds, dSrc['internal']['disable'])

	# Throw away all 'read.cache' commands.
	if 'read.cache' in lCmds: dCmds.pop('read.cache')

	# See which commands have been triggered, gather a list of command
	# orders.  (Lowest order is first, higher orders are next, etc.)
	dInOrder = []
	for sType in dCmds:
		dCmd = dCmds[sType]

		if triggered(dCmd, dParams): 
				
			dCmd['stage'] = sType
			if dCmd['order'] not in dInOrder:
				dInOrder[ dCmd['order'] ] = [ dCmd ]
			else:
				dInOrder[ dCmd['order'] ].append(dCmd)

	# If no commands are left, pop a query error
	if len(dInOrder) == 0:
		raise E.QueryError("No internal data production commands associated with the given HTTP query.")


	lTplts = _collapseByMime(dInOrder)

	return makeCmdLine(lTplts, dParams)


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
