"""Intermediate navigation pages in the data source tree"""

import sys

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\r\n')
	
##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):

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

	# ####################################################################### #
	# The main show #

	U.page.navheader(dConf, fLog, sPathInfo.replace('form.html','download'))

	pout('<h1>TODO: Data Download Page</h1>')


	# END Article Div, and Main DIV ######################################### #
	pout('  </div>\n</div>\n') 
	
	U.page.footer(dConf, fLog)

	pout('''</body>
</html>''')
	
	return 0
