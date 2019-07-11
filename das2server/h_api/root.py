"""Default handler for root of Helophysics subsystem"""

import sys

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	pout("Content-Type: text/html; charset=utf-8\r\n")
	
	sScript = U.io.getScriptUrl()
	
	dRep = {
		"caps": "%s/hapi/capabilities"%sScript,
		"cat":  "%s/hapi/catalog"%sScript,
		"info": "%s/hapi/info"%sScript,
		"data": "%s/hapi/data"%sScript
	}
	
	pout('''<html>
<head><title>Das 2.2 HAPI Subsystem</title></head>
<body>
<h2>Das2 HAPI Subsystem</h2>
<p> This Das2 server supports the Heliophysics Application Programming 
Programming Interface (HAPI) 1.1 specification for query and delivery of
single resolution, uniform time series data.  The following common 
Das2 data sources will not fit within into the HAPI specification and are
automatically excluded from the <a href="%(cat)s">catalog</a>:</p>
<ul>
<li>Selectable resolution data sources such as spacecraft ephemerides and 
magnetic field models
</li>
<li>Variable frequency resolution data sources such as the Cassini RPWS
Low-Rate Complete survey set</li>
<li>Any data source that redirects operations to another server</li>
<li>Any data source that requires authentication</li>
</ul>
<p>Because of these restrictions, dependence on the Heliophysics API as
the primary access mechanism for the data on this server is <b>not</b>
recommend.
</p>
<h3>Endpoints</h3>
<p>The HAPI subsystem consists of the following four paths that will respond 
to HTTP GET requests.
</p>
<ol>
<li> <a href="%(caps)s">capabilities</a> describe the capabilities of the
     server; this lists the output formats the server can emit (CSV)
</li>
<li><a href="%(cat)s">catalog</a> list the datasets that are available; each 
    dataset is associated with a unique id</li>
<li><a href="%(info)s">info</a> obtain a description for dataset of a given id;
    the description defines the parameters in every dataset record</li>
<li><a href="%(data)s">data</a> stream data content for a dataset of a given id;
    the streaming request must have time bounds (specified by request
	 parameters time.min and time.max) and may indicate a subset of parameters
	 (default is all parameters)</li>
</ol>
<p>Many datasets available from this server may not fit into the output 
format required by the API.  For these, use of the native Das2 stream format
is recommended.  For more information on the Helophysics API, it's capabilities
and restrictions, see <a href="http://spase-group.org/hapi">this page</a> at
the SPASE web site.  </p>

</body>
</html>
'''%dRep)


#<h3>Warning: HAPI's unconventional fill values</h3>
#</p>
#The HAPI 1.1 requirement on the use of floating point fill values in
#CSV streams with <i>"exact numeric representation"</i> when converted to 
#an unspecified binary format, is ridiculous.  The authors of the specification
#seemed to be aware of this incrongruity and provided an alternative, which is to
#include the string NaN in the output as in:

#<blockquote><tt> ... ,3.189e+06,NaN,NaN,2.373e+06, ... </tt></blockquote>

#This is also a poor choice as it breaks expections of numeric values in output
#columns.  CSV has a long established exact and compact representation of fill,
#which is mearly two commas with no intervening characters.  Though the Das2
#Server developer's do not agree with inflating streams with non-numeric output,
#the subsystem does follow the HAPI 1.1 specification in this regard.  Client
#programs should be aware of this aspect of the HAPI stream format when parsing
#data values.
#<p>

#</body>
#</html>
#	'''%dRep)
	
	return 0
