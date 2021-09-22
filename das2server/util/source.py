"""Producing HttpStreamSrc information, this is a standalone module and
   doesn't need the (overloaded) dsdf module.
"""




#########################################################################
#def _getInternalInterface(self, fLog, dConf, dSrc):
#	"""Get all the items needed for the internal server interface that are
#	not to be sent out to the clients.

#	"""
#	dImpl = {}


#	if 'OPTIONS' not in dSrc['QUERY_PARAMS']:
#		raise errors.ServerError("OPTIONS section missing from QUERY_PARAMS")
#	dOpts = dSrc['QUERY_PARAMS']['OPTIONS']


#	if 'readerCmd' in self.d:
#		dImpl['_reader'] = {'_cmd':self.d['readerCmd']}
#	else:
#		if 'requiresInterval' in self.d:
#			dImpl['_reader'] = {
#				'_cmd':"%s %%{time.int} %%{time.min} %%{time.max}"%self.d['reader']
#			}
#		else:
#			dImpl['_reader'] = {'_cmd':
#				"%s %%{time.min} %%{time.max}"%self.d['reader']
#			}
#			if len(dOpts) == 0:
#				dImpl['_reader']['_cmd'] += " %{params}"

#		# now add in all options...
#		for sKey in dOpts:
#			dImpl['_reader']['_cmd'] += " %%{%s}"%sKey

#	if 'reducerCmd' in self.d:
#		dImpl['_reducer'] = {'_cmd':self.d['reducerCmd']}
#	else:
#		if 'reducer' in self.d and \
#			(self.d['reducer'] not in ('not_reducable','not_reducible')):

#			dImpl['_reducer'] = {'_cmd':"%s %%{time.res}"%self.d['reducer']}

#		elif 'reducer' not in self.d:
#			# Get default reducer based on the stream type
#			if 'qstream' in self.d:
#				if 'QDS_REDUCER' in dConf:
#					dImpl['_reducer'] = {'_cmd':"%s %%{time.res}"%dConf['QDS_REDUCER']}
#			else:
#				if 'D2S_REDUCER' in dConf:
#					dImpl['_reducer'] = {'_cmd':"%s -b %%{time.min} %%{time.res}"%dConf['D2S_REDUCER']}

#	if 'cacheReader' not in self.d:
#		sCacheDir =  pjoin(dConf['CACHE_ROOT'], 'data', self.sName)
#		sCacheRdrArgs = "%s %s ${NORM_OPTIONS} %%{time.beg} %%{time.end} %%{time.res}"%(
#			self.sPath, sCacheDir)

#		if 'qstream' in self.d:
#			if 'QDS_CACHE_RDR' in dConf:
#				dImpl['_cache_reader'] = {'_cmd':"%s %s"%(dConf['QDS_CACHE_RDR'], sCacheRdrArgs)}
#		else:
#			if 'D2S_CACHE_RDR' in dConf:
#				dImpl['_cache_reader'] = {'_cmd':"%s %s"%(dConf['D2S_CACHE_RDR'], sCacheRdrArgs)}

#	else:
#		dImpl['_cache_reader'] = {'_cmd':self.d['cacheReader']}

#	# Reader command line translations
#	dTrans = self._getArgTrans(fLog, 'reader', dSrc)
#	if len(dTrans) > 0:
#		dImpl['_reader']['_translate'] = dTrans


#	# Cache control information (internal)

#	# This is hard locked for now to just be time
#	# in the future support looking this up, say for example
#	# ['lat','long']
#	# ['time','freq']
#	lCacheCoords = ['time']
#	dRawLvls = self.getCacheLevels()
#	if len(dRawLvls) > 0:
#		if 'time' not in dSrc['COORDINATES']:
#			raise errors.ServerError(
#				"Time based cache blocks defined for non-time datasource"
#			)

#		dCachInCoords = {'_block_by':lCacheCoords}
#		dLvls = {}
#		for sKey in dRawLvls:
#			dLvls[sKey] = {
#				'_resolution':dRawLvls[sKey][0],
#				'_units':dRawLvls[sKey][1],
#				'_scheme':dRawLvls[sKey][2]
#			}
#			if dRawLvls[sKey][3]:
#				dLvls[sKey]['_reader_args'] = dRawLvls[sKey][3]

#		dCachInCoords['_lines'] = dLvls
#		dImpl['_cache'] = dCachInCoords

#	# Security authorization

#	if 'readAccess' in self.d:
#		dAuth = {'_dsdf_compat':self.d['readAccess']}
#		if 'securityRealm' in self.d:
#			dAuth['_realm'] = self.d['securityRealm']

#		lMethods = [s.strip() for s in self.d['readAccess'].split('|')]
#		if len(lMethods) > 0:
#			lMethOut = []
#			for i in range(0, len(lMethods)):

#				lMeth = [s.strip() for s in lMethods[i].split(':')]
#				#fLog.write("DEBUG: auth methods %s"%lMeth)
#				if len(lMeth) < 2:
#					raise errors.ServerError(
#						"Syntax error in readAccess key value"
#					)

#				sCheckType = lMeth[0].upper().strip()

#				lMethOut.append({'_check':sCheckType, '_values': lMeth[1:]})

#			dAuth['_methods'] = lMethOut
#			dImpl['_authorization'] = dAuth


#	dImpl['_local_id'] = self.sName
#	dImpl['_local_path'] = self.sPath

#	return dImpl

def parseDsdf()


def fromDsdf(dConf, sDsdf, sBaseUrl, fLog, bInernal=False):
	"""Create an HttpStreamSrc object from a DSDF file and the given server
	configuration information.

	If bInternal is true, an aditional top level section named:

			"internal"

	is added to the dictionary which contains stuff like cache levels
	sub sources, and various commandlines.

	Output make assumptions about the query parameter interface of the 
	server and format conversion capabilities.

	Todo: Add overrides for adjacent *.json file.
	"""
	
	dRawDsdf = _loadDsdf()
