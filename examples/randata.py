#!/usr/bin/env python

import sys

import das2

import datetime
import random
import time

arg = sys.argv

start_time = das2.DasTime(arg[1])
end_time = das2.DasTime(arg[2])

ndata = 200
delta_t = (end_time - start_time) / 200.

packet = '''<packet>
    <x type="time27" units="us2000"></x>
    <y type="ascii15" name="radius" units="">
        <properties String:yLabel="R!DE!N" />
    </y>\n</packet>'''

data = []
for i in range(ndata):
    tt = start_time + delta_t*i
    data.append({"datetime": tt, "value":random.uniform(-10, 10)})

header = '''<stream version="2.2">
    <properties double:zFill="-1.0e+31"
                DatumRange:xRange="%s to %s UTC"
                String:title="Random points" />
</stream>'''.str(start_time), str(end_time)

print("[00]{:06d}{}".format(len(header), header))
print("[01]{:06d}{}".format(len(packet), packet))
for item in data:
    print(":01:{} {:+.11f}".format(str(item['datetime']),item['value']))
