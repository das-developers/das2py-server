"""Default Handler for no argument hit on the top level of the server"""

import sys
import os

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

      stdin - Has already been consumed by the FieldStorage instance, theres
		   nothing to read there
			
   Environment Inputs:
	
	   The standard CGI environment variables are present and set up, some of
		the utilitly module functions use these is the background
			
	Outputs:
		stdout - Write any data ment for the client program to standard output
		
		stderr - Not used, don't even bother unless you are doing some wierd
		         non-embedded testing
					
	   fLog - Log your errors or other information in fLog, or better yet use
		       the error output functions in U.io.
		
	Return Value:
	
	   Return 0 if everything went okay, non-zero to indicate an error return
		
	
	Exceptions:
		There is a traceback handler at the top level, so thrown exceptions will
		be caught, logged and sent to the client.  In addition the log message
		will be sent as plain  text or as a das2exception packet depending on the
		client type.
	"""
	
	dReplace = {"script":U.io.getScriptUrl()}
	
	sExQuery = ""
	if dConf.has_key('SAMPLE_DSDF'):
		dReplace['dataset'] = dConf['SAMPLE_DSDF']
			
	if dConf.has_key('SAMPLE_START') and dConf.has_key('SAMPLE_END'):
		dReplace['start_time'] = dConf['SAMPLE_START']
		dReplace['end_time'] = dConf['SAMPLE_END']
	
	bHSubSys	= False
	sKey = "ENABLE_HAPI_SUBSYS"
	if sKey in dConf:
		bHSubSys = dConf[sKey].lower() in ('true','yes','1')
	
				
	sViewLog = ""
	if dConf.has_key('VIEW_LOG_URL'):
		if len(dConf['VIEW_LOG_URL']) > 0:
			sViewLog = '<a href="%s">Recent '%dConf['VIEW_LOG_URL']+\
			           'activity logs</a> for your IP address are available.'
	
	pout("Content-Type: text/html; charset=utf-8\r\n")
	pout("<html><title>Das2.2 Simple Server</title>")
	
	pout('<body>')
	pout('<h1>')
	pout('<img src="%(script)s?server=logo" />'%dReplace )

	if dConf.has_key('SITE_NAME'):
		pout( dConf['SITE_NAME'])
	else:
		pout( "Set SITE_NAME in %s"%dConf['__file__'])
		
	pout('</h1>')
	
	if bHSubSys:
		sTmp = """This is a Das 2.2 Server, it provides access to space 
		          physics data sources using a two distinct HTTP GET based query
					 protocols, the native protocol and a simplified time series 
					 cube protocol defined by the helophysics API group. """
	else:
		sTmp = """This is a Das 2.2 Server, it provides access to space 
		          physics data sources using a simple HTTP GET based query
					 protocol. """
	
	pout("""
<p>%s %s
</p>

<p>Full use of this site requires a client progam capable of reading data in
Das2 stream or QStream format.  <a href="http://autoplot.org">Autoplot</a> is a
general client for plotting many types of space physics data, including
streams from this server, and the 
<a href="http://www-pw.physics.uiowa.edu/das2/demo-apps.html">Das2 Clients</a>
from the University of Iowa provide specific interfaces tailored to certian
data sets.
<p>
</p>
Since this server delivers information over HTTP, limited functionality
is available using any standard web browser.  Some example queries are 
provided below.
</p>
"""%(sTmp, sViewLog))

	pout("""
<h2>Example Queries</h2>
<ul>

<li><b>Data Source List</b> -- To download a list of all data sources known to
this server use the following URL:
<br /><br />
<a href="%(script)s?server=list">%(script)s?server=list</a>
<br /><br />
</li>"""%dReplace)

	pout("""
<li><b>Peer List</b> -- To download a list of other Das2 Servers known to this
site use the following URL:
<br /><br />
<a href="%(script)s?server=peers">%(script)s?server=peers</a>
<br /><br />
</li>
"""%dReplace)

	pout("""
<li><b>Dataset Definition</b> -- To gather basic information on a datasource
enter a URL with the pattern:
<br /><br />
%(script)s?server=info&dataset=<i>DATA_SET_NAME</i>
<br /><br />
Where the <i>DATA_SET_NAME</i> is one of the file paths provided by a 
data source list query.
"""%dReplace)

	if dReplace.has_key('dataset'):
		pout("""
For example:
<br /><br />
<a href="%(script)s?server=dsdf&dataset=%(dataset)s">
%(script)s?server=dsdf&dataset=%(dataset)s</a>
		"""%dReplace)
	
	pout("<br /><br /></li>")
	
	pout("""
<li><b>Data Download</b> -- To download data as either 
a Das2Stream or QStream enter a URL with the pattern:
<br /><br />
%(script)s?server=dataset&dataset=<i>DATA_SET_NAME</i>&start_time=<i>BEGIN</i>&end_time=<i>END</i>
<br /><br />
Where the <i>START</i> and <i>END</i> are time strings.  Though may time 
formats will work with most data sources, ISO-8601 format strings are 
recommended, in general these look like YYYY-MM-DDTHH:MM:SS.sss where 
uneeded time fields may be omitted.
"""%dReplace)

	if dReplace.has_key('start_time') and dReplace.has_key('end_time'):
		pout("""
For example:
<br /><br />
<a href="%(script)s?server=dataset&dataset=%(dataset)s&start_time=%(start_time)s&end_time=%(end_time)s">
%(script)s?server=dataset&dataset=%(dataset)s&start_time=%(start_time)s&end_time=%(end_time)s</a>
		"""%dReplace)
	
	pout("<br /><br /></li>")
	
	if dConf.has_key('PNG_MAKER'):
		pout("""
<li><b>Plot Download</b> -- This server has been extended with a server side
plotter which delivers data as PNG images.  To use this functionality enter a
URL with the pattern:
<br /><br />
%(script)s?server=image&dataset=<i>DATA_SET_NAME</i>&start_time=<i>BEGIN</i>&end_time=<i>END</i>		
<br /><br />
"""%dReplace)

		if dReplace.has_key('start_time') and dReplace.has_key('end_time') and \
		   dReplace.has_key('dataset'):
			pout("""
For example:
<br /><br />
<a href="%(script)s?server=image&dataset=%(dataset)s&start_time=%(start_time)s&end_time=%(end_time)s">
%(script)s?server=image&dataset=%(dataset)s&start_time=%(start_time)s&end_time=%(end_time)s</a>
		"""%dReplace)
			
		pout("<br /><br /></li>")
		

	pout("</ul>")
	
	
	if bHSubSys:
		pout("""
<h2>Helophysics API Support</h2>
<p>All queries rooted at <a href="%s/hapi">%s/hapi</a> will respond to
helophysics API requests as documented at 
https://github.com/hapi-server/data-specification</p>
"""%(dReplace["script"], dReplace["script"]))
		
	pout("""
<h2>Documentation</h2>
<p>More information about das2 can be found at:
<a href="http://www-pw.physics.uiowa.edu/das2/">
  http://www-pw.physics.uiowa.edu/das2/</a>.
</p>
"""%dReplace)

	pout("<hr><p>%s</p>"%os.getenv('SERVER_SIGNATURE'))

	pout('</body></html>')
	
	return 0

	
