import sys

import das2

import datetime
import random
import time

##############################################################################
# boiler plate to deal with python2/3 and unicode/bytes

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

##############################################################################
# now for the reader ...

arg = sys.argv

start_time = das2.DasTime(arg[1])
end_time = das2.DasTime(arg[2])

ndata = 200
delta_t = (end_time - start_time) / 200.

header = '''<stream version="2.2">
  <properties 
    double:zFill="-1.0e+31"
    DatumRange:xRange="%s to %s UTC"
    String:title="Random points" 
  />
</stream>
'''%(str(start_time), str(end_time))

write("[00]{:06d}{}".format(len(header), header))

packet = '''<packet>
  <x type="time27" units="us2000"></x>
  <y type="ascii7" name="radius" units="Re">
    <properties String:yLabel="R!DE!N" />
  </y>
</packet>
'''
    
write("[01]{:06d}{}".format(len(packet), packet))

flush()  # It's good to flush stdout output right after sending headers so
         # Autoplot get's something right a way.

for i in range(ndata):
    dt = start_time + delta_t*i
    val = random.uniform(-10, 10)
    write(":01:{} {:+.3f}\n".format(dt,val))
    
