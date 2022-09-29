#!/usr/bin/env python3

"""A websocket client for server testing"""

import sys
import trio
from trio_websocket import open_websocket_url, ConnectionRejected, ConnectionClosed


# ########################################################################## #
# Packet Generator Object # 

async def ReadPkt(ws):
	await ws.send_message("howdy")
	while True:
		try:
			pkt = await ws.get_message()
			sys.stdout.buffer.write(pkt)
		except ConnectionClosed as ex:
			break

# ########################################################################## #
def helpText():
	print("""
Das web socket test client.  Usage:

  ws_test_client URL > your_file.d3b
  
The exact URL depends on the server and resource you're trying to test.
Here's an example to get you started:

   ws://oberon.physics.uiowa.edu:52245/tracers/l0/msc/em1/sci/data?read.time.min=2022-03-09&read.time.max=2022-03-10
	  
enter the URL above all as one line in QUOTES.  All output is to
standard out, so redirect it if you don't want to spew to the terminal.
""")

# ########################################################################## #
# Main Generator Object # 

async def Main(args):

	# Some paths that will work:
	#
	# /tracers/preflight/msc_em1/l0_sci/data
	# /tracers/preflight/msc_em1/l0_sci_psd/data
	# /juno/waves/burst/lfrl/data
	# /mars_express/marsis/ais/data
	
	for arg in args:
		if (arg == '-h') or (arg == '--help'):
			helpText()
			return
	
	sUrl = None
	if len(args) > 1:
		sUrl = args[1]
	else:
		sBase = 'ws://oberon.physics.uiowa.edu:52245/tracers/l0/msc/em1/sci/data'
		sQuery = "read.time.min=2022-03-09&read.time.max=2022-03-10"
		sUrl = "%s?%s"%(sBase, sQuery)
	
	#print("Requesting socket for: %s"%sDest)
	try:
		async with open_websocket_url(sUrl) as ws:
			#await ws.send_message('hello world!')
			await ReadPkt(ws)

	except ConnectionRejected as ex:
		print("Connection rejected with status %d, body follows"%ex.status_code)
		print("-------")
		for t in ex.headers:
			print("%s: %s"%(t[0].decode('utf-8'), t[1].decode('utf-8')))
		print()
		print(ex.body.decode('utf-8'))

	except OSError as ose:
		print('Connection attempt failed: %s' % ose)

# ########################################################################## #
if __name__ == "__main__":
	trio.run(Main, sys.argv)
