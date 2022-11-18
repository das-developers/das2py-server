"""Default Debug Handler, we might need a way of shutting this down"""

import os
import sys
import base64
import crypt

from os.path import join as pjoin

##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	"""See dasflex.handlers.intro.py for a decription of this function
	interface
	"""
	
	bAuth = False
	sUser = None
	sCrypt = None
	if 'HTTP_AUTHORIZATION' in os.environ:
		sAuth = os.environ['HTTP_AUTHORIZATION']
		if sAuth.startswith('Basic') and len(sAuth) > 12:
		
			bAuth = True
		
			sAuthPlain = base64.b64decode(sAuth[5:]).decode('utf-8')
			lAuth = sAuthPlain.split(':')
			sUser = lAuth[0]
			sPasswd = lAuth[1]
			
			if 'USER_PASSWD' in dConf and os.path.isfile(dConf['USER_PASSWD']):
				fIn = open(dConf['USER_PASSWD'], 'r')
			
				for sLine in fIn:
					sLine = sLine.strip()
					lLine = sLine.split(':')
					if len(lLine) > 1 and lLine[0] == sUser:
						sCrypt = lLine[1]
						sTest = crypt.crypt(sPasswd, sCrypt)
						
						if sTest == sCrypt:
							bAuth = True
							break
			
				fIn.close()
			
	if not bAuth:
		sys.stdout.write("Status: 401 Authorization Required\r\n")
		sys.stdout.write('WWW-Authenticate: Basic realm="Das2 Server"\r\n\r\n')
		return 0
	
	print("Content-Type: text/html; charset=utf-8")
	print("")

	print("""<!DOCTYPE html>
<html>
<title>Das2 PyServer Enviroment</title>
<body>
<h1>Das2 PyServer Environment</h1>

<p>Server is defined by config file: %s</p>
<p>Here's the config values</p>
"""%dConf['__file__'])

	print("<ul>")
	lKeys = list(dConf.keys())
	lKeys.sort()
	for sKey in lKeys:
		if sKey != '__file__':
			print("<li>%s = %s</li>"%(sKey, dConf[sKey]))
	print("</ul>")
		
	print("<p>Here's the script environment</p>")
	print("<ul>")
	lKeys = list(os.environ.keys())
	lKeys.sort()
	for sKey in lKeys:
		print("<li>%s = %s</li>"%(sKey, os.getenv(sKey)))
	print("</ul>")
	
	print("<p>Here's the User info</p>")
	print("<ul><li>login = %s</li>"%sUser)
	print("<li>crypt = %s</li></ul>"%sCrypt)
	
	
	print("<p>Here's the form data</p>")
	print("<ul>")
	for sKey in form.keys():
		print("<li>%s = %s</li>"%(sKey, form.getfirst(sKey, "None").lower()))
	print("</ul>")
	
	print("<p>Here's the python module path</p>")
	print("<ul>")
	for item in sys.path:
		print("<li>%s</li>"%item)
	print("</ul>")
	
	print("<p>Here's the binary path</p>")
	print("<ul>")
	lPath = os.environ['PATH'].split(os.pathsep)
	for sPath in lPath:
		print("<li>%s</li>"%sPath)
	print("</ul>")
	
	print("</body>\r\n</html>")
	
	return 0
