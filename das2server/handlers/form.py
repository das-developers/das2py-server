"""Intermediate navigation pages in the data source tree"""

import os
import sys
import json
import traceback
from io import StringIO

from os.path import basename as bname

# ########################################################################## #
# Functions pulled up from the util module, see 'global' in handleReq        #

getMime = None

##############################################################################
def pout(sOut):
	sys.stdout.write(sOut)
	sys.stdout.write('\n')

def sout(fOut, sOut):
	"""Write to a file-like object"""
	fOut.write(sOut)
	fOut.write('\n')

#############################################################################
def _missingKeyError(fOut, sKey, sUrl):
	sout(fOut, 
'''<p class="error">Schema error in node from <a href="%s">%s</a>, 
key <b>%s</b> is missing.</p>
'''%(sUrl, sUrl, sKey))
	return None

#############################################################################
def _isTrue(d, key):
	if key not in d: return False

	if d[key] == True: return True
	if d[key] == False: return False

	if d[key].lower() in ('true','1','yes'):
		return True
	return False

#############################################################################

def _hostSimpleName(sBase):
	sLow = sBase.lower()
	if sLow.startswith('https'):  sLow = sLow[8:]
	elif sLow.startswith('http'): sLow = sLow[7:]

	sLow = sLow[0].upper() + sLow[1:]

	n = sLow.find('.')
	if n != -1: return sLow[:n]
	n = sLow.find('/')
	if n != -1: return sLow[:n]
	n = sLow.find('?')
	if n != -1: return sLow[:n]
	return sLow

def _setHidden(fOut, dBaseUrls):
	"""Go through the base URLs see if they have any keys already set, if so
		we'll need hidden form parameters to cover those as well
	"""
	dHidden = {}
	for sUrl in dBaseUrls:
		n = sUrl.find('?')
		if n == -1: continue

		lQuery = sUrl[n+1:].split('&')
		for sPair in lQuery:
			lPair = [s.strip() for s in sPair.split("=")]
			if (len(lPair) > 1) and lPair[0] not in dHidden:
				dHidden[lPair[0]] = lPair[1]

	for sKey in dHidden:
		sout(fOut, '<input type="hidden" name="%s" value="%s">'%(sKey, dHidden[sKey]))


def _inputVarTextAspect(fOut, dParams, dVar, sAspect, sCtrlId):
	"""Create a text entry field for a variable aspect such as 'minimum' or 
	'resolution'.  In addition to the given aspect the 'units' aspect is 
	inspected so this function isn't unsable for general options.

	Args:
		dParams: The http_params dictionary.  The control ID will be listed here
			if a control is generated.
		dVar: The dictionary for the overall variable
		sAspect: The dictionary key for the aspect, ex: 'maximum'
		sCtrlId: The id to use for the generated control, if any.

	Returns:
		0 if no control was created, 1 otherwise
	"""
			
	if sAspect not in dVar: return 0
	dAspect = dVar[sAspect]
	
	if 'set' not in dAspect: return 0
	
	dSet = dAspect['set']
				
	if 'units' in dAspect:  sUnits = dAspect['units']
	elif 'units' in dVar:   sUnits = dVar['units']['value']
	sUnitLbl = " (%s)"%sUnits
	sAspectLbl = sAspect[0].upper() + sAspect[1:]

	sout(fOut, '<label for="%s">%s%s</label>'%(sCtrlId, sAspectLbl, sUnitLbl))
	sReq = ""
	if ('required' in dSet) and dSet['required']: sReq = 'required'
	sValue = ""
	if 'value' in dAspect: sValue = dAspect['value']
	
	# Guess a good input size based off the units
	nSize=8
	if sUnits.lower() == 'utc': nSize=18

	sout(fOut, '<input size="%d" id="%s" type="text" value="%s" %s>'%(
		nSize, sCtrlId, sValue, sReq)
	)
	
	if 'flag' in dSet:
		dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
	else:
		dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
	
	return 1 
	
def _inputItemBoolean(fOut, dParams, dItem, sMsg, sCtrlId):
	"""Create a boolean checkbox for an item with a boolean value with a 'set'
	member.

	This control generator is useful for both variables and options as it does
	not inspect the contained option group.  Typically this is used with the
	variable 'enable' aspect or for boolean options.

	Args:
		dParams: The 'http_params' dictionary
		dItem: The dictionary describing the boolean property to set
		sMsg: The message to use to lable the check box
		sCtrlId: The control ID to assign if a control is made

	Returns:
		0 if a control was not created, 1 otherwise
	"""

	if 'set' not in dItem: return 0
	
	sChecked = ""
	if ('value' in dItem) and dItem['value'] == True: sChecked = "checked"
	
	sout(fOut, '<input type="checkbox" id="%s" %s>'%(sCtrlId, sChecked))
	sout(fOut, '<label for="%s">%s</label>'%(sCtrlId, sMsg))
	
	# If the default is 
	
	dSet = dItem['set']
	if 'flag' in dSet:
		dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
		dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inIfCtrlVal'] = dSet['value']
	else:
		dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId	
		dParams[ dSet['param'] ]['_inIfCtrlVal'] = dSet['value']
	return 1

		
def _inputItemEnum(fOut, dParams, dItem, sMsg, sCtrlId):
	"""Create a select list control for an enum item with a 'set' member.
	
	This control generator is useful for both variables and options as it does
	not inspect the contained option group.  One example where this is useful is
	selecting the output units for the Voyager Spectrum Analyzer data.

	Args:
		dParms: The 'http_params' dictionary
		dItem: The dictionary describing the item to set.  The set method for
			this item must have an 'enum' sub-member.
	
	The flag to set cascades.  If it's in the root of 'set', then all entries
	in the enum set the same flag.  If it's in an individual item listing then
	each selection can set a different flag.

	"""
	if 'set' not in dItem: return 0
	dSet = dItem['set']
	if 'enum' not in dSet: return 0

	# We save the field ID in the value but display the new value.  
	# Case example follows from voyager.
	#
	# The input option control selects among different flag values.
	#
	# "units" : {
	#   "value": "V/m",
	#   "set": {
	#      "param":"read.options",
	#      "enum":[
	#          {"value":"raw", "flag":"00"},
	#          {"value":"V**2 m**-2 Hz**-1", "flag":"01"},
	#          /* or if setting whole value */
	#          {"value":"V**2 m**-2 Hz**-1", "pval":"SD"},
	#      ]
	#   }
	# }
	#
	# The input option control puts a value directly in the flag,
	# so _inIfCtrlVal is not set.  Instead _inIfNotCtrlVal is set.
	# 
	# "channel" : {
	#			"title": "Spectrum analyzer channel to output",
	#			"value": "all",
	#			"set" : { 
	#				"param":"read.options", 
	#				"flag":"07",
	#				"enum" : [
	#					{"value":"10.0Hz"},
	#					{"value":"17.8Hz"},
	#					{"value":"31.1Hz"},
	#					{"value":"56.2Hz"},
	#					{"value":"100Hz"},
	#					{"value":"178Hz"},
	#					{"value":"311Hz"},
	#					{"value":"562Hz"},
	#					{"value":"1.00kHz"},
	#					{"value":"1.78kHz"},
	#					{"value":"3.11kHz"},
	#					{"value":"5.62kHz"},
	#					{"value":"10.0kHz"},
	#					{"value":"17.8kHz"},
	#					{"value":"31.1kHz"},
	#					{"value":"56.2kHz"}
	#				]
	#			}
	#		}
   #   }
	
	sout(fOut, sMsg)
	sout(fOut, '<select id=%s>'%sCtrlId)


	#program begin end other_stuff

   #program #[key/flag |  @ | stuff if don't   ]
	
	
	# If the current value is not in the enum, put it here without mapping 
	# information so it can't be sent
	bAddDefault = True
	for dMap in dSet['enum']:
		if dMap['value'] == dItem['value']: 
			bAddDefault = False
			break
	
	if bAddDefault:
		sCtrlVal = dItem['value']
		if 'name' in dItem:  sCtrlVal = dItem['name']
		sout(fOut, '   <option value="" selected>%s</option>'%sCtrlVal)
		
	for dMap in dSet['enum']:
	
		sSelected = ""
		if dMap['value'] == dItem['value']: sSelected = "selected"
		if 'pval' in dMap: sVal = dMap['pval']
		elif 'flag' in dMap: sVal = dMap['flag']
		else: sVal = dMap['value']

		sCtrlVal = dMap['value']
		if 'name' in dMap:  sCtrlVal = dMap['name']

		sout(fOut, '   <option value="%s" %s>%s</option>'%(sVal, sSelected, sCtrlVal))

		if 'param' in dMap: sParam = dMap['param']
		elif 'param' in dSet: sParam = dSet['param']
		
		# Save the control id's in the flag_set, but since we are saving the same
		# control id in multiple members also as an '_ifCtrlVal' item as well.	
		if 'flag' in dMap:
			dParams[ dSet['param'] ]['flags'][ dMap['flag'] ]['_inCtrlId'] = sCtrlId
			dParams[ dSet['param'] ]['flags'][ dMap['flag'] ]['_inIfCtrlVal'] = sVal
		elif 'flag' in dItem:
			dParams[ dSet['param'] ]['flags'][ dItem['flag'] ]['_inCtrlId'] = sCtrlId
		else:
			dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
			dParams[ dSet['param'] ]['_inIfCtrlVal'] = sVal

	sout(fOut, '</select>')
	
	
def _prnVarForm(fOut, sCtrlPre, dParams, sVarId, dVar):
	"""Output non-submittable HTML form controls for the configurable aspects
	of a variable and record the control IDs alongside the http get params
	they modify.

	Args:
		sCtrlPre: A prefix to add to all generated control IDs

		dParams:  The 'http_params' dictionary from the HttpStreamSrc catalog 
			object.  Control IDs will be inserted into parameter dictionaries
			under the key 'ctrl_id'.  Note that parameters with the type 'enum'
			or 'flag_set' will have 'ctrl_id' added into the individual flags
			or items.
		
		sVarId: The object id for this variable in the 'coordinates' or 'data'
			dictionaries

		dVar: The variable dictionary

	Returns:
		The number of non-sumbittable controls created.
	"""
	nCtrls = 0

	if 'title' in dVar:  sTitle = dVar['title']
	elif 'name' in dVar: sTitle = dVar['name']
	
	if 'name' in dVar: sName = dVar['name']
	else: sName = sVarId[0].upper() + sVarId[1:]
	
	# If this variable has text aspects, label them up front
	lAspects = ('min', 'max', 'res', 'int')
	bLabelRow = False
	for sAspect in lAspects:
		if (sAspect in dVar) and ('set' in dVar[sAspect]):
			bLabelRow = True
			break

	if bLabelRow: sout(fOut, "<p><b>%s: &nbsp;</b>"%sName)
	else: sout(fOut, '<p>')
	
	# Right now I'm assuming the type of field for each aspect, should look
	# at the 'set' statement to get this info
	
	for i in range(len(lAspects)):
		sCtrlId = "%s_%s_%s"%(sCtrlPre, sVarId, lAspects[i])
		nCtrls += _inputVarTextAspect(fOut, dParams, dVar, lAspects[i], sCtrlId)

	if 'enabled' in dVar:
		sCtrlId = "%s_%s_enabled"%(sCtrlPre, sVarId)
		sMsg = "Enable <b>%s</b>"%sName
		if 'title' in dVar: sMsg = "%s - %s"%(sMsg, dVar['title'])
		_inputItemBoolean(fOut, dParams, dVar['enabled'], sMsg, sCtrlId)
		
	if 'units' in dVar:
		sCtrlId = "%s_%s_units"%(sCtrlPre, sVarId)
		_inputItemEnum(fOut, dParams, dVar['units'], "Set %s Units"%sName, sCtrlId)
	
	sout(fOut, "</p>")

	return nCtrls

def prnOptGroupForm(fOut, sCtrlPre, dParams, sGroup, dGroup, sSrcUrl, bVar=False):
	"""Run through all the options in a group making output controls for each
	settable property

	Args:
		sCtrlPre (str): The prefix to assign to control IDs
		
		dParams (str): The 'http_params' dictionary
		
		sGroup (str): The name of the group
		
		dGroup (dict): The group dictionary
		
		bVar (bool): This group represents the options for a single coordinate or
			data variable.  Certian display options are enable for variable 
			groups, such a putting mix,max,resolution in a single line and looking
			around for units strings.
	"""
	nCtrls = 0
	
	lProps = list(dGroup.keys())
	lProps.sort()

	# Get the group name
	sGrpName = sGroup
	if 'name' in dGroup: sGrpName = dGroup['name']
	
	# Any option name can be used, but some are recognized as having particular 
	# meanings, especially in the context of a variable.  If this is a variable
	# make sure min,max,res,int are presented in that order.
	tOneLiner = ('enabled','minimum','maximum','resolution','interval')
	sGrpUnits = None
	if bVar:
		lFirst = []
		lRest = []
		for sKey in tOneLiner:
			if sKey in lProps: lFirst.append(sKey)
		for sKey in lFirst: lProps.remove(sKey)	
		lProps = lFirst + lProps
		
		if 'units' in lProps: sGrpUnits = dGroup['units']['value']
	
	# Weed out all the props that aren't settable
	lSettable = []
	for sProp in lProps:
		if isinstance(dGroup[sProp], dict) and 'set' in dGroup[sProp]: 
			lSettable.append(sProp)
	lProps = lSettable

	#sys.stderr.write("Settable props for %s: %s\n"%(sGrpName, lSettable))

	for iProp in range(len(lProps)):
		sProp = lProps[iProp]
		dProp = dGroup[sProp]
		curval = None
		
		sPropUnits = None
		if 'units' in dProp: sPropUnits = dProp['units']
		elif sGrpUnits: sPropUnits = sGrpUnits
		
		# Note: The type of curval is unknown at this point
		if 'value' in dProp: curval = dProp['value']
		else:
			_missingKeyError(fOut, '%s:%s:value'%(sGroup, sProp), sSrcUrl)
			return 0
		
		if 'set' not in dProp:
			#sout(fOut, "%s: %s &nbsp"%(sProp, curval))
			continue
			
		# make a row prefix
		if not bVar:
			if iProp == 0: sout(fOut, "<p>")
			else: sout(fOut, "</p>\n<p>")
		else:
			if iProp == 0: sout(fOut, "<p><b>%s: &nbsp;</b>"%sGrpName)
			
			# if this isn't a classical one-liner, start a new row 
			if sProp not in tOneLiner: sout(fOut, "<br> &nbsp; ")
			
		dSet = dProp['set']
			
		if 'name' in dProp: sName = dProp['name']
		else: sName = sProp[0].upper() + sProp[1:]
			

		sCtrlId = "%s_%s_%s"%(sCtrlPre, sGroup, sProp)
		
		if 'flag' in dSet: sCtrlVal = dSet['flag']
		elif 'pval' in dSet: sCtrlVal = dSet['pval']
		else: sCtrlVal = "%s"%curval
		
		# There are three basic types of controls: 
		#
		#     check boxes, text boxes, select boxes.  
		# 
		# Determine what kind to make here.  Instances where there are only two
		# values that can be selected (the initial value, and the set) use
		# select boxes.
		
		sType = 'unk'
		if isinstance(curval, bool): sType = 'bool'
		elif 'enum' in dSet:  sType = 'select'
		elif 'value' in dSet: sType = 'select'
		else: sType = 'text'
		
		if sType == 'bool':
			sInfo = sProp
			if bVar and (sProp == "enabled"):
				sName = "Output"
				if 'title' in dGroup: sInfo = dGroup['title']
				elif 'name' in dGroup: sInfo = dGroup['name']
				else: sInfo = sGroup
			else:
				if 'title' in dProp: sInfo = dProp['title']
				elif 'name' in dProp: sInfo = dProp['name']
			
			sChecked = ""
			if curval == True: sChecked = "checked"
				
			sout(fOut, '<input type="checkbox" id="%s" value="%s" %s><b>%s</b> - %s'%(
			     sCtrlId, sCtrlVal, sChecked, sName, sInfo)
			)

			#print('dParams.keys()  = ', list(dParams.keys()))
			
			# Save off the control information
			if 'flag' in dSet:
				dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
			else:
				dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
	
			
		elif sType == 'select':
			if 'title'  in dProp: sMsg = dProp['title']
			elif 'name' in dProp: sMsg = dProp['name']
			else:                 sMsg = sProp[0].upper() + sProp[1:]
			
			if 'enum' in dSet:  # True enums... 
				_inputItemEnum(fOut, dParams, dProp, sMsg, sCtrlId)
				
			else:
				# Effective enum, binary choice
				sout(fOut, sMsg)
				sout(fOut, '<select id=%s>'%sCtrlId)
				sout(fOut, '  <option value="" selected>%s</option>'%curval)
				
				if 'pval' in dSet: sVal = dSet['pval']
				elif 'flag' in dSet: sVal = dSet['flag']
				else: sVal = dSet['value']
				
				sout(fOut, '  <option value="%s">%s</option>'%(sVal, dSet['value']))
				sout(fOut, '</select>')
				
				# Save off the control information, with an if check for the
				# select value
				if 'flag' in dSet:
					dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
					dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inIfCtrlVal'] = sVal
				else:
					dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
					dParams[ dSet['param'] ]['_inIfCtrlVal'] = sVal
								
		else:		
			if bVar:
				if sPropUnits: sout(fOut, '%s (%s)'%(sName, sPropUnits))
				else: sout(fOut, '%s '%sName)
			else:
				sout(fOut, '<b>%s</b>: '%sName)
			
			
			if 'title' in dProp:
				sout(fOut, '<label for="%s">%s</label>'%(sCtrlId, dProp['title']))
				
			if 'description' in dProp:
				lDesc = dProp['description'].split('\n')
				sDesc = '<br>\n'.join(lDesc)
				sout(fOut, '<p>%s</p>'%sDesc)
				
			nSize = 8
			if sPropUnits and sPropUnits.lower() == 'utc': nSize = 16
			elif len(sCtrlVal) > 90: nSize = 75
			else: nSize = int( len(sCtrlVal)*0.7)
			if nSize < 2: nSize = 2
			
			sReq = ""
			if ('required' in dSet) and dSet['required']: sReq = 'required'
			
			sout(fOut, '<input type="text" id="%s" size="%d" value="%s" %s>'%(
				sCtrlId, nSize, sCtrlVal, sReq))
			
			# Save off the control information
			if 'flag' in dSet:
				dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
			else:
				dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
			
		nCtrls += 1
		
	
	sout(fOut, "</p>")
	
	return nCtrls

def _getDefaultMime(dFormats):
	"""Given a standard formats section, return the default mime types if nothing
	is changed.

	Returns:
		(sMime, sExt, sTitle)
	"""
	sType = None
	dFmt = None
	for sFmt in dFormats:
		dTmp = dFormats[sFmt]
		if ('enabled' in dTmp) and ('value' in dTmp['enabled']):
			if dTmp['enabled']['value']:
				dFmt = dTmp
				sType = sFmt
				break

	if not dFmt: return None

	sVer = None
	if 'version' in dFmt and ('value' in dFmt['version']):
		sVer = dFmt['version']['value']

	sSerial = None
	if 'serial' in dFmt and ('value' in dFmt['serial']):
		sSerial = dFmt['serial']['value']
		
	return getMime(sType, sVer, sSerial)


def _getAction(sBase):
	"""Get action from base url.  Basically return the URL with no GET params"""
	n = sBase.find('?')
	if n != -1: return sBase[:n]
	else: return sBase


def prnHttpSource(fLog, dSrc, fOut):
	""" Print an http source, this is complicated

	Handling input forms.
	
	This would be reativily straight forward, except we need form controls that
	generate partial get values.  (I'm looking at you das2 'params' and hapi
	'parameters'.)  To make life even *more* fun, sometimes servers screw up if
	an empty parameter is sent (I'm looking at you das2 'resolution' and hapi 
	'parameters').  So in addition we have to have a way to remove the 'name'
	attribute from parameters that otherwise would get kicked out the door.
	
	If these protocols (and others) were created in the spirit of HTML this
	wouldn't be needed, but alas, not everyone wants to make life easy for
	browser client developers, so here's the plan...
	
	Basic form handling works like this

	1. 'examples', 'coordinates', 'data', 'options', 'formats' are parsed.
	   All controls are generated without a name so they cannot be transmitted.
	
	2. All controls are generated with an ID, that has the form:
	  
	   basename(_path) + "_" + [coord|data|opt ] + "_" + [varID|optCat] + 
	                       "_" + [var_aspect|opt_setting ]
	
	   This insures all controls have a unique ID even if multiple http get
	   sources are combined into a single page.
	
	3. As each control is created it adds it's control ID to the relavent 
	   parameter in 'http_params'.  If the parameter is a FLAG_SET, or ENUM
	   then the control ID is added to the flag entry instead of the top level. 
	
	4. After all fake controls are generated, 'http_params' is parsed and all
	   'http_params' with a control ID attached are created as hidden text 
	   entry forms that are themselves fake (have no name).  The 
	   to-potentially-be-submitted controls are created with the following
	   ids:
	
     	basename(_path) + http_params name
	
	5. An onSubmit function is generated for the form with the following 
	   name:
	
	     basename(_path) + "_OnSubmit"
	
	   and the http_parmas element is added as a variable.  When called 
	   onSubmit inspects the controls registered in 'http_params' and sets
	   new control values.  Finnally the output controls that have data 
	   values are given a name so that they can be submitted.

	--cwp
	"""
	
	sSrcUrl = dSrc['_url']

	if 'contacts' in dSrc:
		sout(fOut, "<p>Technical problems using this data source should be "
		     "directed to: <b>")
		lTmp = [d['name'].strip() for d in dSrc['contacts']]
		sout(fOut, ", ".join(lTmp))
		sout(fOut, "</b>.</p>")

	if 'protocol' not in dSrc:
		return _missingKeyError(fOut, 'protocol', sSrcUrl)
	else:
		dProto = dSrc['protocol']

	if 'authentication' in dProto:
		if _isTrue(dProto['authentication'], 'required'):
			sout(fOut, '<p><i><span class="error">Restricted data source</span>.</i>')
			if 'REALM' in dProto['authentication']:
				 sout(fOut, 'You will be asked to authentication to the realm "' +\
				      '<b>%s</b>" on submit.</p>'%dProto['authentication']['realm'])
			else:
				sout(fOut, "You will be asked to authentication on submit.</p>")

	# Print the examples
	if 'examples' in dProto:
		sout(fOut, "<p>Example queries:")
		lExamples = list(dProto['examples'].keys())
		lExamples.sort()
		for sExample in lExamples:
			dExample = dProto['examples'][sExample]
			sTmp = sExample
			if 'name' in dExample:	sTmp = dExample['name']
			if 'title' in dExample: sTmp = dExample['title']
			sout(fOut, '<a href="%s">%s</a> &nbsp;'%(dExample['url'], sTmp))
		sout(fOut, "</p>")

	# Leave the form action blank, we'll set it depending on which submit
	# button is used.
	sBaseUri = bname(dSrc['_path'])
	sFormId = "%s_download"%sBaseUri
	sout(fOut, '<form id="%s">'%sFormId)

	# Go through the base URLs see if they have any keys already set, if so
	# we'll need hidden form parameters to cover those as well
	if 'base_urls' not in dProto:
		return _missingKeyError(fOut, 'protocol:base_urls', dSrc['_url'])
	
	_setHidden(fOut, dProto['base_urls'])

	dParams = None
	if 'http_params' in dProto: dParams = dProto['http_params']
	nSettables = 0
	
	if 'interface' not in dSrc:
		return _missingKeyError(fOut, 'interface', dSrc['_url'])
	else:
		dIface = dSrc['interface']
	
	# Handle setting coord options, always do time first if it's present
	if dParams and ('coordinates' in dIface):
		# Find out if any coordinates provide subselect
		dCoords = dIface['coordinates']
		bSubSet = False
		bEnable = False
		lMod = []
		
		# Gather all settable coordinates
		for sCoord in dCoords:
			for sAspect in dCoords[sCoord]:
				if sAspect in ('name','title','description'): continue
				for sKey in dCoords[sCoord][sAspect]:
					if sKey.startswith('set'):
						if sCoord not in lMod: lMod.append(sCoord)
							
		# If the data are sub-settable by at least one property make the fieldset
		# indicate that
		if len(lMod) > 0:
			sout(fOut, '<fieldset><legend><b>Coordinate Options:</b></legend>')
			
			sStyle = ''
			if len(lMod) > 12: sStyle = 'class="srcopts_scroll_div"'
			sout(fOut, '<div %s>'%sStyle)

			lMod.sort()
			if 'time' in lMod:
				lMod.remove('time')
				lMod.sort()
				lMod = ['time'] + lMod
			for sCoord in lMod:
				# Function below writes control IDs into dParams
				nSettables += prnOptGroupForm(fOut, 
					sBaseUri, dParams, sCoord, dCoords[sCoord], sSrcUrl, True
				)

			sout(fOut, "</div>")
			sout(fOut, '</fieldset>')
	
	# Handle setting data options.  There's no limit to these, but try to 
	# inteligently group them.  If a particular data var has a lot of 
	# options then group by data var.  Otherwise throw everything in one
	# group.
	
	if dParams and ('data' in dIface):
		dData = dIface['data']
		bEnable = False
		bUnits = False
		lMod = []
		
		# See if the any of the data items have settable parameters
		nDatOpts = 0
		lModVars = []
		for sVar in dData:
			for sAspect in dData[sVar]:
				for sKey in dData[sVar][sAspect]:
					if sKey.startswith('set'):
						if sVar not in lModVars: lModVars.append(sVar)
						nDatOpts += 1
						break
				
		if nDatOpts > 0:
			sout(fOut, '<fieldset><legend><b>Data Options:</b></legend>')
			
			sStyle = ''
			if nDatOpts > 12: sStyle = 'class="srcopts_scroll_div"'
			sout(fOut, '<div %s>'%sStyle)
			
			lModVars.sort()
			for sVar in lModVars:
				nSettables += prnOptGroupForm(fOut,
					sBaseUri, dParams, sVar, dData[sVar], sSrcUrl, True
				)

			sout(fOut, "</div>")
			sout(fOut, "</fieldset>")
		
		for sData in dData:
			for sAspect in ('units','enabled'):
				if sAspect in dData[sData]:
					for sKey in dData[sData][sAspect]:
						if sKey.startswith('set'):
							if sAspect == 'enabled':	bEnable = True
							else: bUnits = True
							if sData not in lMod: lMod.append(sData)
					
		if bEnable or bUnits:
		
			if bEnable:
				sout(fOut, '<fieldset><legend><b>Toggle Data Output:</b></legend>')
			else:
				sout(fOut, '<fieldset><legend><b>Set Data Units:</b></legend>')
			
			sStyle = ''
			if len(lMod) > 12: sStyle = 'class="srcopts_scroll_div"'
			sout(fOut, '<div %s>'%sStyle)
		
			# Probably need to return id's to use in javascript here
			lMod.sort()
			for sData in lMod:
				nSettables += _prnVarForm(fOut, sBaseUri, dParams, sData, dData[sData])
				
			sout(fOut, "</div>")
			sout(fOut, "</fieldset>")
	
	# Handle setting general options
	if dParams and ('options' in dIface):
		dOptions = dIface['options']

		lOptions = list(dOptions.keys())
		
		lMod = []
		for sProperty in lOptions:
			if 'set' in dOptions[sProperty]:
				if sProperty not in lMod: lMod.append(sProperty)

		if len(lMod) > 0:				
			sout(fOut, "<fieldset><legend><b>Additional Options:</b></legend>")
				
			nSettables += prnOptGroupForm(fOut,
				sBaseUri, dParams, 'options', dOptions, sSrcUrl, 
			)
	
			sout(fOut, "</fieldset>")

	# Handle setting format options
	if dParams and ('formats' in dIface):
		dFmt = dIface['formats']
		fLog.write('INFO: Inspecting formats %s'%str(dFmt.keys()))
		bEnable = False
		
		# See if any of the formats have settable parameters
		nFmtOpts = 0
		lModFmts = []
		for sFmt in dFmt:
			#if sFmt == 'default': continue
			for sAspect in dFmt[sFmt]:
				for sKey in dFmt[sFmt][sAspect]:
					if sKey.startswith('set'):
						if sFmt not in lModFmts: lModFmts.append(sFmt)
						nFmtOpts += 1
						break

		if nFmtOpts > 0:
			# TODO: Handle undo and revert back to the default
			sout(fOut, '<fieldset><legend><b>Format Options:</b></legend>')
			
			(sMime, sExt, sName) = _getDefaultMime(dFmt)
			sout(fOut, 
				"<p>Output will be <b>%s</b> (<tt>%s</tt>) unless set below.</p>"%(
				sName, sMime
			))

			sStyle = ''
			if nFmtOpts > 10: sStyle = 'class="srcopts_scroll_div"'
			sout(fOut, '<div %s>'%sStyle)

			lModFmts.sort()
			for sFmt in lModFmts:
				nSettables += prnOptGroupForm(fOut, 
					sBaseUri, dParams, sFmt, dFmt[sFmt], sSrcUrl, True
				)

			sout(fOut, "</div>")
			sout(fOut, "</fieldset>")
	else:
		fLog.write('INFO: Output format is not selectable.')


	# Stage 4, inspect http_params and output hidden controls with no name.
	if dParams and (nSettables > 0):
		nSettables = 0
		for sParam in dParams:
			dParam = dParams[sParam]
			if 'type' not in dParam: continue

			bOut = False
			if dParam['type'] == 'flag_set':
				if 'flags' not in dParam: continue
				
				for sFlag in dParam['flags']:
					dFlag = dParam['flags'][sFlag]
					if '_inCtrlId' in dFlag:
						bOut = True
						break
			elif dParam['type'] == 'enum':
				if 'items' not in dParam: continue
				
				for sItem in dParam['items']:
					dItem = dParam['items'][sItem]
					if '_inCtrlId' in dItem:
						bOut = True
						break
			else:
				if '_inCtrlId' in dParam: bOut = True

			if bOut:
				sCtrlId = "%s_%s"%(sBaseUri, sParam)
				sout(fOut, '<input type="hidden" id="%s">'%sCtrlId)
				dParam['_outCtrlId'] = sCtrlId


		# Stage 5, write the javascript that will be used on submit
		sFuncName = "%s_onSubmit"%sBaseUri
		sJson = json.dumps(dParams, ensure_ascii=False, indent=2, sort_keys=True)
		sNamePrefix = "%s_"%sBaseUri
		sout(fOut, """
<script>
function %s(sActionUrl) {
	var dParams = %s;
	
	// Strip this from outgoing control id's, to get the output control
	// name.  It was added to keep out controls from different forms separate.
	var sNamePre = "%s";

	for(var sParam in dParams){
		dParam = dParams[sParam]
		
		if(!("_outCtrlId" in dParam)) continue;
		var ctrlOut = document.getElementById(dParam["_outCtrlId"]);
		var sOutName = dParam["_outCtrlId"].replace(sNamePre, "");
		
		// Flagset parameters, the most complicated ones
		if( ('type' in dParam) && (dParam['type'] == 'flag_set')){
		
			if( !('flags' in dParam) ) continue;
			
			var dFlags = dParams[sParam]['flags'];
			var sOutVal = "";
			var sOutSep = " ";
			if( 'flag_sep' in dParam) sOutSep = dParam['flag_sep'];
			
			for(var sFlag in dFlags){
				var dFlag = dFlags[sFlag];
				if( !('_inCtrlId' in dFlag) ) continue;
				
				var ctrlIn = document.getElementById(dFlag["_inCtrlId"]);
				
				// Check to see if we only add the output flag when the input
				// has a certian value
				if( '_inIfCtrlVal' in dFlag ){
					if(ctrlIn.type == 'checkbox'){
					
						// If the state of the checkbox matches the send state then add the
						// parameter.  This might mean than NOT checked sends a value.
						if(dFlag['_inIfCtrlVal'] ==  ctrlIn.checked){
							if((sOutSep.length > 0)&&(sOutVal.length > 0)) sOutVal += sOutSep;
							sOutVal += dFlag['value'];
						}
					}
					else{
						if( ctrlIn.value == dFlag['_inIfCtrlVal']){
							if((sOutSep.length > 0)&&(sOutVal.length > 0)) sOutVal += sOutSep;
							sOutVal += dFlag['value'];
						}
					}
				}
				else{
					// So the input sets the whole flag only set the output if something
					// has changed.
					if(ctrlIn.type == 'checkbox'){
						if( ctrlIn.checked == true){
							if((sOutSep.length > 0)&&(sOutVal.length > 0)) sOutVal += sOutSep;
							if('prefix' in dFlag) sOutVal += dFlag['prefix'];
							sOutVal += dFlag['value'];
						}
					}
					else{
						if( ctrlIn.value.length > 0){
							if((sOutSep.length > 0)&&(sOutVal.length > 0)) sOutVal += sOutSep;
							if('prefix' in dFlag) sOutVal += dFlag['prefix'];
							sOutVal += ctrlIn.value;					
						} 
					}
				}
			}
			
			// Set control name and value if value changed
			if(sOutVal.length > 0){
				ctrlOut.name = sOutName;
				ctrlOut.value = sOutVal;
			}
		}
		
		// TODO: Enum parameters
		//else if ('type' in dParam) and (dParam['type'] == 'enum')){
		//
		//
		//
		//}
		
		// Generic parameters
		else {
			
			if(!("_inCtrlId" in dParam)) continue;
			var ctrlIn = document.getElementById(dParam["_inCtrlId"]);
			
			// Check boxes...
			if(ctrlIn.getAttribute("type") == "checkbox"){
				if(ctrlIn.checked == true){
					// Text fields
					ctrlOut.value = ctrlIn.value;
					ctrlOut.name = sOutName;
				}
			} 
			else {
				if(ctrlIn.value.length > 0){
					// Text fields
					ctrlOut.value = ctrlIn.value;
					ctrlOut.name = sOutName;
				}
			}
		}
	}

	document.getElementById("%s").action = sActionUrl;
}
</script>
	"""%(sFuncName, sJson, sNamePrefix, sFormId))
		
		# Make one submit function per base url that starts with https				
		for sBase in dProto['base_urls']:
			sout(fOut, '<input type="submit" value="Get from %s"'%_hostSimpleName(sBase) +\
		     	' onclick=\'%s("%s");\'>'%(sFuncName, _getAction(sBase) ))

	sout(fOut, '</form>')

	sout(fOut, '<div class="identifers">')
	sout(fOut, '<br><br>Catalog Path: %s &nbsp; <br>'%dSrc['_path'])
	sout(fOut, 'Read From: &nbsp; <a href="%s">%s</a></a>'%(dSrc['_url'], dSrc['_url']))
	
	if 'uris' in dSrc and len(dSrc['uris']) > 0:
		sout(fOut, '<br>Permanent IDs:')
		dSrc['uris'].sort()
		for sUri in dSrc['uris']: sout(fOut, " &nbsp; <i>%s</i>"%sUri)
	
	sout(fOut, '</div>')	

	
##############################################################################
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	
	global getMime
	getMime = U.output.getMime

	fLog.write("\nDas2 HttpStreamSrc definition Handler")
	
	sScriptUrl = U.webio.getScriptUrl().strip('/')

	sSource = os.getenv("PATH_INFO")  # Knock off leading '/source'
	if sSource.startswith('/source/'):
		sSource = sSource[len('/source/'):]
	else:
		U.webio.serverError(fLog, u"PATH_INFO did not start with /source/")

	if sSource.endswith('/form.html'):
		sSource = sSource.replace("/form.html", '.dsdf')
	else:
		U.webio.notFoundError(fLog, u"PATH_INFO did not end with /form.html")

	try:
		dNode = U.source.external(fLog, dConf, sSource)
	except U.errors.QueryError as e:
		U.webio.queryError(fLog, str(e))
		return 17
	except U.errors.ServerError as e:
		U.webio.serverError(fLog, str(e));
		return 17
	
	# Slide in the json data location in case they want to look at it
	dNode["_url"] = "%s%s"%(sScriptUrl, 
		os.getenv("PATH_INFO").replace('form.html','api.json')
	)
	dNode["_path"] = "%s:/%s/%s"%(
		dConf['SITE_CATALOG_TAG'], dConf['SERVER_ID'].lower(),
		sSource.replace('.dsdf','').lower()
	)

	# ...okay should output something 
	sys.stdout.write('Content-Type: text/html; charset=utf-8\r\n\r\n')
	
	dReplace = {"script":sScriptUrl}

	if 'STYLE_SHEET' in dConf:
		sCssLink = "%s/static/%s"%(sScriptUrl, dConf['STYLE_SHEET'])
	else:
		sCssLink = "%s/static/das2server.css"%sScriptUrl

	if 'SITE_TITLE' in dConf:
		sSiteId = dConf['SITE_TITLE']
	else:
		sSiteId = "Set SITE_TITLE in %s"%dConf['__file__']

	pout('''<!DOCTYPE html>
<html>
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

	#pout('<h1>TODO: Data Download Page</h1>')

	U.page.navheader(dConf, fLog, sPathInfo.replace('form.html','download'))

	try:
		fOut = StringIO()
		prnHttpSource(fLog, dNode, fOut)
		fOut.seek(0)
		pout(fOut.read())
	except Exception:
		pout('<h2>Error in data source</h2>')
		pout('''<pre>
%s
</pre>
'''%traceback.format_exc())


	pout('<h2>Source definition is</h2>')
	pout('''<pre>
%s
</pre>
'''%json.dumps(dNode, indent=2))


	# END Article Div, and Main DIV ######################################### #
	pout('  </div>\n</div>\n') 
	
	U.page.footer(dConf, fLog)

	pout('''</body>
</html>''')
	
	return 0
