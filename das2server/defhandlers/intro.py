"""Default Handler for no argument hit on the top level of the server"""

import sys
import os
from os.path import join as pjoin

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
##############################################################################
# Provide a list of name and directory tuples from a given data level

def _isVisible(sDsdf):
	if not os.path.isfile(sDsdf): return False
	
	try:
		fIn = open(sDsdf, 'r')

		for sLine in fIn:
			if sLine.find('#') != -1:
				sLine = sLine[: sLine.find('#') ]
			sLine = sLine.strip()
			if sLine.startswith('hidden'):
				lLine = [s.strip().strip("'") for s in sLine.split('=')]
				if len(lLine) > 1:
					if lLine[1].lower() in ('yes','true','1'):
						fIn.close()
						return False;

		fIn.close()
	except:
		return False
	return True

def _getWebTargets(U, dConf, fLog, sRelPath):
	"""Get a list of links and names for everything at a particular level
	
	sRelPath - Level under SCRIPT/source, use a '/' to get
	           information for the top of the dsdf root
	"""

	sScriptURL = U.webio.getScriptUrl()
	
	# Keep a list of directories

	if 'DSDF_ROOT' not in dConf:
		fLog.write("   ERROR: Configuration item DSDF_ROOT missing")
		return None

	sRoot = dConf['DSDF_ROOT']
	
	if not os.path.isdir(sRoot):
		fLog.write("   ERROR: DSID_ROOT dir '%s' does not exist"%sRoot)
		return None
	
	if sRelPath == '/':
		sPath = sRoot
	else:
		sPath = pjoin(sRoot, sRelPath)
		
	if not os.path.isdir(sPath):
		fLog.write("   ERROR: Data directory '%s' does not exist"%sPath)
		return None
	
	lOut = []
	
	lItems = os.listdir(sPath)
	lItems.sort()
	
	fLog.write("   INFO: Listing items in %s"%sPath)
	for sItem in lItems:
		sItemPath = pjoin(sPath, sItem)
		if os.path.isdir( sItemPath ):

			sDirDsdf = pjoin(sItemPath, '_dirinfo_.dsdf')
			if not _isVisible(sDirDsdf): continue

			sUrl = '%s/source%s%s/info.html'%(sScriptURL, sRelPath.lower(), sItem.lower())
			sName = sItem.replace('_',' ')
			lOut.append( (sName, sUrl) )

		elif os.path.isfile( sItemPath ):
			if not sItem.endswith(".dsdf"): continue
			if sItem == "_dirinfo_.dsdf": continue
			if not _isVisible(sItemPath): continue

			sSourceDir = sItemPath.strip('.dsdf').lower();
			sUrl = '%s/source%s%s/form.html'%(sScriptURL, sRelPath.lower(), sSrcDir)
			sName = sItem.replace('_',' ')
			lOut.append( (sName, sUrl) )
	
	return lOut

##############################################################################
def allowViewLog(dConf, fLog, sIP):
	"""Check the config and see if sIP is allowed to view log files"""
	
	fLog.write("   WARNING: das2server.util.site.allowViewLog not implemented, always says yes")
	
	return True
	

##############################################################################
# Helper for browseHeader, provides an optional header that shows the data
# hierarchy down to the current level

def _dataNavHeader(U, sReqType, dConf, fLog, form, sPathInfo):
	
	sScriptURL = U.webio.getScriptUrl()
	
	sDataSet = sPathInfo.replace('/source/', '')
	
	# Split the path up into parts that retain the trailing '/'
	lParts = [ '%s/'%s for s in sDataSet.split('/')]
	
	if lParts[-1] == '/':
		lParts[-2] = "%s/"%(lParts[-2])
		lParts = lParts[:-1]
		
	if len(lParts) < 1:
		return
	
	pout('  <center><ul id="datanav">')
	
	
	for i in range(0, len(lParts)):
		sPart = lParts[i]
		sName = 	lParts[i].rstrip('/').replace('_',' ').upper()
		
		sUrl = '%s/source/%s'%(sScriptURL, ''.join(lParts[:i+1]))
		
		if i > 0:
			sSep = ' &gt '
		else:
			sSep = ''
			
		pout('    <li>%s<a href="%s">%s</a></li>'%(sSep, sUrl, sName))
	
	pout(' </ul></center>')
		
	
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
	
	sExQuery = ""
	
	dReplace['SERVER_VER'] = "Das2.3 (prototype)"
		
	if 'SAMPLE_DSDF' in dConf:
		dReplace['dataset'] = dConf['SAMPLE_DSDF']
			
	if 'SAMPLE_START' in dConf and 'SAMPLE_END' in dConf:
		dReplace['min'] = dConf['SAMPLE_START']
		dReplace['max'] = dConf['SAMPLE_END']
	
	bHSubSys	= False
	sKey = "ENABLE_HAPI_SUBSYS"
	if sKey in dConf:
		bHSubSys = dConf[sKey].lower() in ('true','yes','1')
		
				
	sViewLog = ""
	sViewLogNav = ""
	if 'VIEW_LOG_URL' in dConf:
		if len(dConf['VIEW_LOG_URL']) > 0:
			sViewLog = '<a href="%s">Recent '%dConf['VIEW_LOG_URL']+\
			           'activity logs</a> for your IP address are available.'
			sViewLogNav = '<hr><a href="%s">Activity Log</a>'%dConf['VIEW_LOG_URL'] 
	
	sScriptURL = U.webio.getScriptUrl()
	
	if 'SITE_NAME' in dConf:
		sSiteId = dConf['SITE_NAME']
	else:
		sSiteId = "Set SITE_NAME in %s"%dConf['__file__']
	dReplace['SITE_NAME'] = sSiteId	

	if 'SERVER_ID' in dConf:
		sServerId = dConf['SERVER_ID'].upper()
	else:
		sServerId = "{Set SERVER_ID in %s}"%dConf['__file__']
	dReplace['SERVER_ID'] = sServerId

	if 'STYLE_SHEET' in dConf:
		sCssLink = "%s/static/%s"%(sScriptURL, dConf['STYLE_SHEET'])
	else:
		sCssLink = "%s/static/das2server.css"%sScriptURL
	
	pout('''
<html>
<head>
   <title>%s</title>
   <link rel="stylesheet" type="text/css" media="screen" href="%s" />
</head>
'''%(sSiteId, sCssLink))
	
	pout('''
<body>
<div class="header">
	<div class="hdr_left">
		<img src="%(script)s/static/logo.png" alt="%(SERVER_ID)s" width="70" height="70" >
	</div> 
	<div class="hdr_center">
	%(SERVER_ID)s, a %(SERVER_VER)s Server
	<h1>%(SITE_NAME)s</h1>
	</div>
	<div class="hdr_right">
		<a href="http://das2.org">
		<img src="%(script)s/static/das2logo_rv.png" alt="das2" width="80" height="80">
		</a>
	</div>
</div>
'''%dReplace)
	
	# Add side navigation bar to top level categories ...
	pout('<div class="main">')
		
	pout('<div class="nav">Data Sources<hr>')
	pout('  <ul>')
	
	lTop = _getWebTargets(U, dConf, fLog, '/')
	
	if lTop != None:
		for (sName, sUrl) in lTop:
			pout('    <li><a href="%s">%s</a><br><br></li>'%(sUrl, sName))

	pout('  </ul>')
	pout('''%s
  <br><br>
  <a href="%s/peers">Peer Servers</a>
</div>'''%(sViewLogNav, sScriptURL))
	
	pout('<div class="article">')
			
	if sPathInfo.startswith('/source/'):
		if sPathInfo != '/source/':
			_dataNavHeader(U, sReqType, dConf, fLog, form, sPathInfo)
	
	pout("""<p>
This is a <b>das2/v2.3 (prototype) server</b>.  It provides data streams,
typically in das2/v2.2 format, via an HTTP GET query protocol.  It operates
by running full-resolution data stream creators on the server and if 
requested, processing those streams as they flow through the server to
your client program.</p>

<img src=%(script)s/static/flowdiagram.png</img>

<p>Forms are provided to download data from this server as das2 streams,
helophysics API streams, text delimited value streams (csv), PNG images,
and eventually as VOTables (in work) via the navigation bar to the right.
</p>

<p>Full use of this server requires a client program capable of reading
data in one of the provided formats and producing plots.  Programs which
can parse das2 streams include:</p>
<ul>
<li> <a href="http://das2.org/autoplot">Autoplot</a> via the
<a href="https://github.com/das-developers/das2java">das2java</a> library.  
This is most common client.</li>
<li> <a href="https://spedas.org/blog/">SPEDAS (Space Physics Environment Data Analysis Software)</a>
via the <a href="https://github.com/das-developers/das2dlm">das2dlm</a> module.</li>
<li><a href="http://www.sddas.org/">SDDAS (Southwest Data Display and Analysis System)</a>
    via the <a href="github.com/das-developers/das2C">das2C</a> library</li>
</ul>

<p>In addition, custom scripts written in 
<a href="https://github.com/das-developers/das2py">Python</a>, 
or <a href="https://github.com/das-developers/das2pro">IDL</a>
my utilize these data.</p>

<h4><i>
This is an <b>alpha version</b> of the server and not all
functionality is complete.</i></h4>
""")
			
	# Site Navagation ######################################################## #

	pout("""
<h2>Interface</h2>

<p>This server provides the following "filesytem" style interface which is accessed
via HTTP GET messages.</p>

<p>Note that clients do <i>not</i> need to understand this layout.  Merely
providing one of the catalog files: <a href="%(script)s/sources.json">sources.json<a>
or <a href="%(script)s/sources.csv">sources.csv<a> is sufficent as these files
contain <i>fully qualified URLs</i> pointing to data retrieval locations within
the server. </p>

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
  |                  |- das2.json - A das2 HttpStreamSource definiton
  |                  |- dsdf.d2t - A das2 v2.1/2.2 source definition
  |                  |- form.html - A web form for querying this source   
  |                  |- voservice.xml - A <a href="https://ivoa.net/documents/VODataService/index.html">VODataService</a> definition
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
  |- <a href="%(script)s/id.txt">id.txt</a> - das2 2.1/2.2 style info text
  |- <a href="%(script)s/logo.png">logo.png</a> - A server identifier logo
</pre>

<p>
Almost all content provided by this server is generated dynamically.  The filesystem
interface is just a facade.  You can ease the load on your server and provide faster
metadata response times by replicating this server's non-data content onto a static
site.  The following commands illustrate this process.
</p>
<pre>
   $ wget -nH --cut-dirs=2 -r --no-parent %(script)s/sources/  # note trailing slash
   $ wget -nH %(script)s/sources.json
   $ wget -nH %(script)s/sources.csv
</pre>
<p>All content in those locations contain fully qualified URLs to other 
resources and may thus be copied off the server without issue.  Furthermore,
metadata items do not require a password.</p>

"""%dReplace)
	
	# Das 2.1/2.2 support ################################################### #

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

# Plot maker ############################################################### #

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

	if bHSubSys:
		pout("""
<h2>Helophysics API Support</h2>
<p>All queries rooted at <a href="%s/hapi">%s/hapi</a> will respond to
helophysics API requests as documented at 
https://github.com/hapi-server/data-specification</p>
"""%(dReplace["script"], dReplace["script"]))
		
	
	pout('  </div>\n</div>\n') 
	# END MAIN DIV ############################################################
	
	pout('''

<div class="footer">
  <div>More information about das2 can be found at:
  <a href="http://das2.org/">http://das2.org/</a>.</div>
  <div>%s</div>
</div>'''%os.getenv('SERVER_SIGNATURE'))

	pout('''
</body>
</html>''')
	
	return 0

	
