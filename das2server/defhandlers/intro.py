"""Default Handler for no argument hit on the top level of the server"""

import sys

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""The interface for a handler function is as follows:
	
	Parameter Inputs:
	
	   U - The das2server utility module, contains handy functions
	
	   sReqType - A string indicating the internal name for this type of 
		    request

		dConf - A dictionary containing all the parameters loaded from 
		    the configuration file
			 
		fLog - A DasLogFile object, contains a write member, just use that
		
		form - A cgi.FieldStorage instance, provides the query parameters
		
		sPathInfo - The URL path after the script name itself

   File Inputs:

      stdin - Has already been consumed by the FieldStorage instance, there's
		   nothing to read there
			
   Environment Inputs:
	
	   The standard CGI environment variables are present and set up, some of
		the utilitly module functions use these is the background
			
	Outputs:
		stdout - Write any data ment for the client program to standard output
		
		stderr - Not used, don't even bother unless you are doing some wierd
		         non-embedded testing
					
	   fLog - Log your errors or other information in fLog, or better yet use
		       the error output functions in U.webio.
		
	Return Value:
	
	   Return 0 if everything went okay, non-zero to indicate an error return
	
	Exceptions:
		There is a traceback handler at the top level, so thrown exceptions will
		be caught, logged and sent to the client.  In addition the log message
		will be sent as plain  text or as a das2exception packet depending on the
		client type.
	"""
	
	pout('Content-Type: text/html; charset=utf-8\r\n')
	pout('<!DOCTYPE html>')
	
	dReplace = {"script":U.webio.getScriptUrl()}
				
	sScriptURL = U.webio.getScriptUrl()

	if 'STYLE_SHEET' in dConf:
		sCssLink = "%s/static/%s"%(sScriptURL, dConf['STYLE_SHEET'])
	else:
		sCssLink = "%s/static/das2server.css"%sScriptURL

	if 'SITE_NAME' in dConf:
		sSiteId = dConf['SITE_NAME']
	else:
		sSiteId = "Set SITE_NAME in %s"%dConf['__file__']

	pout('''<html>
<head>
   <title>%s</title>
   <link rel="stylesheet" type="text/css" media="screen" href="%s" />
</head>
'''%(sSiteId, sCssLink))
	
	pout('<body>')

	U.page.header(dConf, fLog)
	
	# Add side navigation bar to top level categories, need to put this in a
	# libray call
	pout('<div class="main">')
	
	U.page.sidenav(dConf, fLog)
	
	pout('<div class="article">')
			
	pout("""<p>
This is a <b>das2/v2.3 (prototype) server</b>.  It provides data streams
via an HTTP GET query protocol.</p>

<img src="%(script)s/static/flowdiagram.svg"
  alt="das2-pyserver data flow diagram" id="flowdiagram"
/>
<center><i><span style="font-size: 80%%">Internal Stream Processing</span></i></center>

<p>This server runs full-resolution data stream generators, processes the
flow, and optionally caches the results.  Almost all processing steps are
optional.
</p>

<h4><span style="color: #993300"><i>This is an <b>alpha version</b> of the server and not all
functionality is complete.</i></span></h4>

<h2>Clients</h2>

<p>Forms are provided to download data from this server as das2 streams,
text delimited value streams (CSV), PNG images, hapi streams, and eventually
as VOTables (in work) via the navigation bar to the right.
</p>

<p>Full use of this server requires a client program capable of reading
data in one of the provided formats and producing plots.  Programs which
can parse das2 streams include:</p>
<ul>
<li> <a href="http://das2.org/autoplot">Autoplot</a> via the
<a href="https://github.com/das-developers/das2java">das2java</a> library.  
This is the most common client.</li>
<li> <a href="https://spedas.org/blog/">SPEDAS (Space Physics Environment Data Analysis Software)</a>
via the <a href="https://github.com/das-developers/das2dlm">das2dlm</a> module.</li>
<li><a href="http://www.sddas.org/">SDDAS (Southwest Data Display and Analysis System)</a>
    via the <a href="https://github.com/das-developers/das2C">das2C</a> library</li>
</ul>

<p>In addition, custom scripts written in 
<a href="https://github.com/das-developers/das2py">Python</a>, 
or <a href="https://github.com/das-developers/das2pro">IDL</a>
my utilize these data.</p>

"""%dReplace)
			
	# Site Navagation ######################################################## #

	pout("""
<h2>Interface</h2>

<p>The most common data output format is mime-type: <tt>application/vnd.das2.das2stream</tt>
However, streams may be reformatted if requested.</p>

<p>This server provides the following "filesytem" style interface which is accessed
via HTTP GET messages.</p>
<p>Note that clients do <i>not</i> need to understand this layout. 
Merely reading one of the catalog files: <a href="%(script)s/sources.json">sources.json</a>
or <a href="%(script)s/sources.csv">sources.csv</a> is sufficent.</p>

<pre>
<a href="%(script)s">server/</a>  This introductory page, at %(script)s
  |
  |- <a href="%(script)s/hapi/">hapi/</a> - Heliophysics API subsystem (if enabled)
  |
  |- <a href="%(script)s/static/">static/</a> - static files such as logos, etc
  |
  |- <a href="%(script)s/source/">source/</a> - root directory for all data sources 
  |    |
  |    |- <i>category</i>/ - A top level category directory
  |         |         <i>(typically named after missions)</i>
  |         |
  |         |- info.html - Describes this category
  |         |
  |         |- <i>sub-category</i>/ - A sub-category directory
  |             |              <i>(typically named after instruments)</i>
  |             |
  |             |- info.html - Describes this sub-category
  |             |
  |             |- <i>data-source</i>/ - A data source directory
  |                  |
  |                  |- api.json - A das2 HttpStreamSource definiton
  |                  |- dsdf.d2t - A das2 v2.1/2.2 source definition
  |                  |- form.html - A web form for querying this source   
  |                  |- voservice.xml - A VO <a href="https://www.ivoa.net/documents/DataLink/20150617/index.html">DataLink</a> definition
  |                  |
  |                  |- data - form action handler (hidden)
  |
  |- <a href="%(script)s/sources.json">sources.json</a> - A das2 catalog listing all HttpStreamSource objects
  |     on this server.  Provide this URL to <b>new_RootNode_url()</b> in das2C or 
  |     <b>das2.get_node()</b> in das2py.
  |
  |- <a href="%(script)s/sources.csv">sources.csv</a> - A listing of all das2/v2.2 source definitions.
  |
  |- <a href="%(script)s/verify">verify</a> - Included das2 stream verification tool (if enabled)
  |
  |- <a href="%(script)s/id.json">id.json</a> - Server identification information
  |- <a href="%(script)s/id.txt">id.txt</a> - das2 v2.1 style info text
  |- <a href="%(script)s/logo.png">logo.png</a> - A server identifier logo
  |- <a href="%(script)s/peers.xml">peers.xml</a> - Other recognized das2 servers
</pre>

<p>
Almost all content provided by this server is generated dynamically.  The filesystem
interface is just a facade.  You can ease the load on your server and provide faster
metadata response times by replicating non-data content onto a static site.
The following commands illustrate this process.
</p>
<pre>
   $ wget -nH --cut-dirs=2 -r --no-parent %(script)s/sources/  # note trailing slash
   $ wget -nH %(script)s/sources.json
   $ wget -nH %(script)s/sources.csv
</pre>
<p>Of course you'll have to repeat the process whenever data source definitions
are altered.</p>

"""%dReplace)
	
	# Das 2.1/2.2 support ################################################### #

	if 'SAMPLE_DSDF' in dConf:
		dReplace['dataset'] = dConf['SAMPLE_DSDF']
			
	if 'SAMPLE_START' in dConf and 'SAMPLE_END' in dConf:
		dReplace['min'] = dConf['SAMPLE_START']
		dReplace['max'] = dConf['SAMPLE_END']

	pout("""
<h2>Traditional Queries</h2>

<p>The das2/v2.1 server query API is also supported by this server.  A summary
of the scheme follows.</p>
<ul>
<li><b>Data Source List:</b>  <a href="%(script)s?server=list">%(script)s?server=list</a><br /><br /></li>
<li><b>Peer List:</b>  <a href="%(script)s?server=peers">%(script)s?server=peers</a><br /><br /></li>
<li><b>Dataset Definition:</b>  %(script)s?server=dsdf&dataset=<i>DATA_SET_ID</i>
"""%dReplace)
	
	if 'dataset' in dReplace:
		pout("""<br />Example: <a href="%(script)s?server=dsdf&dataset=%(dataset)s">
%(script)s?server=dsdf&dataset=%(dataset)s</a>"""%dReplace)
	pout("<br /><br /></li>")
	
	pout("""<li><b>Data Download:</b> Use the pattern<br />
%(script)s?server=dataset&dataset=<i>DATA_SET_ID</i>&start_time=<i>BEGIN</i>&end_time=<i>END</i>&resolution=<i>SECONDS</i>
<br />
Where the <i>START</i> and <i>END</i> are time strings, and <i>SECONDS</i> is a floating
point number.  To reterive data at the native resolution omitt the <b>resolution</b> 
parameter.
"""%dReplace)

	if 'dataset' in dReplace and 'min' in dReplace and 'max' in dReplace:
		pout("""<br />
Example:
<a href="%(script)s?server=dataset&dataset=%(dataset)s&start_time=%(min)s&end_time=%(max)s">
%(script)s?server=dataset&dataset=%(dataset)s&start_time=%(min)s&end_time=%(max)s</a>
		"""%dReplace)
	
	pout("<br /><br /></li>")
	
	pout("</ul>")

	# Plot maker ############################################################ #

	if 'PNG_MAKER' in dConf:
		pout("""
<li><b>Plot Download</b> -- This server has been extended with a server side
plotter which delivers data as PNG images.  To use this functionality enter a
URL with the pattern:
<br /><br />
%(script)s?server=image&dataset=<i>DATA_SET_NAME</i>&start_time=<i>BEGIN</i>&end_time=<i>END</i>		
<br /><br />
"""%dReplace)

		if 'min' in dReplace and 'max' in dReplace and \
		   'dataset' in dReplace:
			pout("""
For example:
<br /><br />
<a href="%(script)s?server=image&dataset=%(dataset)s&start_time=%(min)s&end_time=%(max)s">
%(script)s?server=image&dataset=%(dataset)s&start_time=%(min)s&end_time=%(max)s</a>
		"""%dReplace)
			
		pout("<br /><br /></li>")
	
	# Helophysics API support ############################################### #

	bHSubSys	= False
	sKey = "ENABLE_HAPI_SUBSYS"
	if sKey in dConf:
		bHSubSys = dConf[sKey].lower() in ('true','yes','1')

	if bHSubSys:
		pout("""
<h2>Helophysics API Support</h2>
<p>All queries rooted at <a href="%s/hapi">%s/hapi</a> will respond to
helophysics API requests as documented at 
https://github.com/hapi-server/data-specification</p>
"""%(dReplace["script"], dReplace["script"]))
		
	
	# END Article Div, and Main DIV ######################################### #
	pout('  </div>\n</div>\n') 
	
	U.page.footer(dConf, fLog)

	pout('''</body>
</html>''')
	
	return 0
