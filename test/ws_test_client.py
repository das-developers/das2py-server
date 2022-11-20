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

import sys
import argparse
from functools import partial as delegate
from urllib.parse import urlparse
import trio
from trio_websocket import open_websocket_url, ConnectionRejected

def perr(sMsg):
	sys.stderr.write("%s\n"%sMsg)

# ########################################################################## #

async def ReadPkt(ws):
	await ws.send_message("howdy")
	while True:
		pkt = await ws.get_message()
		sys.stdout.buffer.write(pkt)

async def ConnectAndRead(sUrl):
	
	async with open_websocket_url(sUrl) as ws:
		#await ws.send_message('hello world!')
		await ReadPkt(ws)

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

	psr.add_argument(
		'URL', help="The data source query.  This can take many forms, an"+\
		" example to get you started:  "+\
		"ws://localhost:52245/dasws/examples/random?read.time.min=2023-01-01&read.time.max=2023-01-02"
	)

	opts = psr.parse_args()

	try:
		trio.run(ConnectAndRead, opts.URL)
		return 0
	except ConnectionRejected as ex:
		perr("Connection rejected with status %d, body follows"%ex.status_code)
		perr("-------")
		for t in ex.headers:
			perr("%s: %s"%(t[0].decode('utf-8'), t[1].decode('utf-8')))
		perr("")
		perr(ex.body.decode('utf-8'))

	except OSError as ex:
		perr('Connection attempt failed: %s'%ex)

	except KeyboardInterrupt:
		perr('CTRL-C recieved, shutting down')

	return 3

# ########################################################################## #
if __name__ == "__main__":
	sys.exit(main(sys.argv))
