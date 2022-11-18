"""These utilities are intended to be used *outside* the CGI and websock 
environments.  

They send output to standard error and use unwrapped standard python exceptions.
Neither of which are suitable for responding to live web queries
"""

from . import convdsdf
from . import convjson
from . import formats
from . import catalog
