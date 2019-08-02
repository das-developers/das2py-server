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
    
