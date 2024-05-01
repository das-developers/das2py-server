#!/usr/bin/env python3
"""
A websocket client for server testing

A Note on Capitalization:
   
   Async functions in python are actually objects in the classic sense. Calling
   one actually instantiates an object and registers it with the main event
   loop.  Thus ALL async functions in this code are capitalized so that the
   reader thinks of them as the objects that they are instead of the direct
   call functions that they emulate.
"""

import os
import sys
import ssl
import argparse
import logging
from functools import partial as delegate
from urllib.parse import urlparse
import trio
from trio_websocket import open_websocket_url, HandshakeError, \
 ConnectionRejected,ConnectionClosed

def perr(sMsg):
	sys.stderr.write("%s\n"%sMsg)

# ########################################################################## #

async def ReadPkts(ws):
	while True:
		try:
			pkt = await ws.get_message()
			sys.stdout.buffer.write(pkt)

		# Since we're not in nursery code, exceptions work like they always have
		except ConnectionClosed as cc:
			if cc.reason.code == 1000: # AKA normal close
				return True
			else:
				return False

	return True


async def HandleConnection(ws):
	l = ws.path.replace('/dasws/','').split('?')

	logging.info("%s connection to %s:%s for endpoint %s"%(
		'Encrypted' if ws.remote.is_ssl else 'Plain',
		ws.remote.address, ws.remote.port, l[0]
	))

	logging.info("Query %s"%(l[1].replace('&',' ')))
	try:
		async with trio.open_nursery() as taskManager:
			taskManager.start_soon(ReadPkts, ws)

	# Uh-oh, opened a task manager, now we have to deal with exception 
	# groups.  Dig deep and pull up the actual cause of the problem
	except ExceptionGroup as grp:
		while True:
			for subex in grp:
				if isinstance(subex, ExceptionGroup):
					grp = subex
				else:
					raise subex

	return True

async def ConnectAndRead(sUrl, sCAFile=None):#, bSubscribe=False):
	
	ssl_context = None
	if sUrl.startswith('wss:'):
		try:
			ssl_context = ssl.create_default_context()
			if not sCAFile:
				ssl_context.check_hostname = False
				ssl_context.verify_mode = ssl.CERT_NONE
			else:
				ssl_context.load_verify_locations(sCAFile)
				logging.debug("Loaded Certificate Authority: %s"%sCAFile)
		except BaseException as e:
			logging.error("Could not create SSL context %s"%repr(e))
			return False
	else:
		ssl_context = None
	
	try:
		logging.debug("Connecting to WebSocket...")
		async with open_websocket_url(sUrl, ssl_context) as ws:
			await HandleConnection(ws)

	except HandshakeError as ex:
		logging.error("Connection attempt failed: %s", e)
		return False

	except ConnectionClosed as cc:
		sCause = '<no reason>' if cc.reason.reason is None else cc.reason.reason
		if cc.reason.code != 1000:
			logging.error("Connection closed: %s %s %s"%(
				cc.reason.code, cc.reason.name, sCause
			))
			return False			

	logging.info("Data source read complete")
	return True

# ########################################################################## #

def main(args):

	psr = argparse.ArgumentParser(
		description="""A simple test program for the dasflex websocket interface.
		It issues a single datasource request and send the resulting data to
		standard output.

		To test the output of a server operation pipe the output of this program
		into das_valid.
		"""
	)

	#sDef = "/etc/ssl/certs/ca-certificates.crt"
	psr.add_argument(
		"-c", '--cert-auth', metavar="CA_FILE", dest="sCAFile", default=None,
		help="Certificate authority used to validate servers.  If not specified "+\
		"this test client will trust any SSL certificate.  Typically a huge "+\
		"PEM file is needed here that rolls up all certs under /etc/ssl/certs."
	)
	psr.add_argument(
		'-l', '--level', metavar='LEVEL', dest="sLevel", default="info",
		help="Setting the central server logging level.  One of 'error',"+\
		"'warning','info','debug' in order of increasing verbosity"
	)
	#psr.add_argument(
	#	"-s", "--subscribe", dest="bSubscribe", action="store_true", default=False,
	#	help="Instead of a download and quit, request a data subscription that "+\
	#	"is held open allowing new data to come in"
	#)
	psr.add_argument(
		'SOURCE_URL', help="The base socket data source URL without query options,"+\
		" for example: wss://localhost:52245/dasws/examples/random"
	)
	psr.add_argument(
		"PARAMS", nargs="*", help="Any number of query key=value pairs.  For example: "+\
		"read.time.min=2022-09-15 read.time.max=2022-09-16"
	)

	opts = psr.parse_args()

	bFuss = False
	nLevel = logging.INFO
	sLvl = opts.sLevel.lower()
	if sLvl == "error":  nLevel = logging.ERROR
	elif sLvl.startswith("warn"): nLevel = logging.WARNING
	elif sLvl == "info": nLevel = logging.INFO
	elif sLvl == "debug": nLevel = logging.DEBUG
	else:
		bFuss = True

	logging.basicConfig(level=nLevel)
	g_pyLog = logging.getLogger()  # Used initially
	if bFuss:
		g_pyLog.error("Unknown logging level: %s"%sLvl)
		return 7

	sUrl = opts.SOURCE_URL
	if len(opts.PARAMS) > 0:
		sUrl = "%s?%s"%(sUrl, "&".join(opts.PARAMS))

	

	try:
		if not trio.run(ConnectAndRead, sUrl, opts.sCAFile): #, opts.bSubscribe)
			return 7
		else:
			return 0
	except ConnectionRejected as ex:
	
		perr("Connection rejected with status %d, full content follows"%ex.status_code)
		perr("-------")
		for t in ex.headers:
			perr("%s: %s"%(t[0].decode('utf-8'), t[1].decode('utf-8')))
		perr("")
		perr(ex.body.decode('utf-8'))
		return 3
				
		perr('Connection attempt failed because reasons:')	
		for ex in grp.exceptions:
			 perr('   %s'%repr(ex))

	except OSError as ex:
		perr('Connection attempt failed: %s'%ex)

	except KeyboardInterrupt:
		perr('CTRL-C recieved, shutting down')

	return 3

# ########################################################################## #
if __name__ == "__main__":
	sys.exit(main(sys.argv))
