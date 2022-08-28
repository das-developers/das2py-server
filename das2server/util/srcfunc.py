"""Automatic source definition section generation based on server configuration

All source generating functions have the same signiture:

fLog  - A logger object, aka something with a .write method.

dConf - The server configuration data

dSrc  - The top level dictionary representing the entire source file *without*
        generated sections.

lArgs - A list of arguments defined by the caller in the data source definition
"""

from . import webio

# ########################################################################### #
def extProtoGetStream(fLog, dConf, dSrc, lArgs):
	"""Emits the following:

		"authentication":{"required":False},
		"baseUrls":[ a list ],
		"convention":"das",
		"method":"get_stream",
	"""

	sServer = webio.getScriptUrl(dConf).strip('/')
	sId = dSrc['__path__'].replace(dConf['DATASRC_ROOT'], '')
	if sId.startswith('/'):
		sId = sId[1:]
	sId = sId.replace('.json','').replace('.dsdf','').lower()

	fLog.write('Source path: %s, DATASRC_ROOT: %s, sID %s'%(
		dSrc['__path__'], dConf['DATASRC_ROOT'], sId
	))

	dProto = {
		"authentication":False,
		"convention":"das/3.0",
		"method":"GET",
		"return":"stream",
		"baseUrls":['%s/source/%s/data'%(sServer, sId)]
	}

	if ('WEBSOCKET_URI' in dConf) and (len(dConf['WEBSOCKET_URI']) > 6):
		dProto['baseUrls'].append(
			"%s/%s/data"%(dConf['WEBSOCKET_URI'], sId)
		)

	return dProto

# ########################################################################### #

def extIface_Fmt(fLog, dConf, dSrc, lArgs):
	"""Using the format of the command output, determine the possible output
	formatting commands.
	"""

	return {"derp":"doggy_format_section"}


# ########################################################################### #

def extProtoParams_Fmt(fLog, dConf, dSrc, lArgs):
	"""Using the format of the command output, determine the possible output
	formatting commands.
	"""

	return {"derp":"doggy_protocol_params"}


# ########################################################################### #

def intCmds_Fmt(fLog, dConf, dSrc, lArgs):
	"""Using the format of the command output, determine the possible output
	formatting commands.
	"""

	return {"derp":"doggy_format_stuff"}


# ########################################################################### #
# Simple registry, just have the functions named the same as thier name in 
# the data source definitions #

g_dRegistry = {
	'extIface_Fmt':       extIface_Fmt,
	'extProtoGetStream':  extProtoGetStream,
	'extProtoParams_Fmt': extProtoParams_Fmt,
	'intCmds_Fmt':        intCmds_Fmt,
}
