#!/usr/bin/env python

import os
import sys
from os.path import basename as bname
from os.path import dirname as dname
import os.path

perr = sys.stderr.write

def prn_help():
	perr("\n")
	perr("Replaces any line beginning with g_sConfPath with:\n")
	perr('g_sConfPath = "%(SERVER_ETC)s/das2server.conf"\n')
	perr("\n")
	perr("And replaces any line that looks like '#!/usr/bin/env python with:'\n")
	perr("#!%s\n"%sys.executable)
	perr("\n")
	perr("Usage: %s INFILE OUTFILE\n"%os.path.basename(sys.argv[0]))
	perr("\n")
	
if len(sys.argv) < 3:
	prn_help()
	sys.exit(13)

if not os.getenv('SERVER_ETC'):
	perr("Environment variable SERVER_ETC is not defined.  Set it to the root\n")
	perr("settings directory for das2 programs\n")
	sys.exit(17)
	

# Determine the name of the python interperater
sInterp = sys.executable
while os.path.islink(sInterp):
	sInterp = os.path.realpath(sInterp)
	

if bname(sys.argv[2]) != sys.argv[2]:
	if not os.path.isdir(dname(sys.argv[2])):
		os.makedirs(dname(sys.argv[2]))

fIn = file(sys.argv[1], 'rb')
fOut = file(sys.argv[2], 'wb')

for sLine in fIn:
	if sLine.startswith('g_sConfPath'):
		fOut.write('g_sConfPath = "%s/das2server.conf"\n'%os.getenv('SERVER_ETC'))
	elif sLine.startswith("#!/usr/bin/env python"):
		fOut.write("#!%s\n"%sInterp)
	else:
		fOut.write(sLine)

fIn.close()
fOut.close()

sys.exit(0)

