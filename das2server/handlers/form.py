"""
This is one of the two major endpoint handlers for the server, it provides
user interfaces for native das3 data sources.  The other is the data request
handler that provides the actual data for all data source types.

The handler assumes that:

  1. The end point ends in *.html

  2. That there is a *.json file that corresponds to the *.html file
	
  3. That the json file defines one of:
    a. A Catalog object
    b. A SourceSet object (a specalization of Catalog)
    c. An HttpStreamSrc object

"""

import os
import sys
import json
import traceback
from io import StringIO
from urllib.parse import quote_plus

from os.path import join as pjoin
from os.path import basename as bname

# ########################################################################## #
# Placeholder for the Formats module #

F = None

def loadFormats(dConf):
	global F

	# Load the webutil module
	try:
		mTmp = __import__('das2server.util', globals(), locals(), ['formats'], 0)
	except ImportError as e:
		preLoadError(
			"Error importing module 'das2server': %s\r\nsys.path is:\r\n%s\r\n"%(
			str(e), sys.path
		))
		return 19
	try:
		F = mTmp.formats
	except AttributeError:
		preLoadError('No module named das2server.util under %s'%dConf['MODULE_PATH'])
		return 20

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

def _hasElement(d, l):
	"""Return true if a nested set of dictionaries has the given key
	"""
	for i in range(len(l)):
		if l[i] not in d:
			return False

		d = d[l[i]]

	return True

def _isElTrue(d, l):
	"""Return true if a nested set of dictionaries has the given key
	and the key evaluates to true
	"""
	for i in range(len(l)):
		if l[i] not in d:
			return False

		d = d[l[i]]

	if d: return True
	else: return False


def _getElement(fLog, d, l):
	if not _hasElement(d, l):
		fLog.write("   ERROR: Could not locate dictionary element: %s"%str(l))
		return None

	for i in range(len(l)):
		if l[i] not in d:
			return False

		d = d[l[i]]

	return d

# ######################################################################### #

class UrlBldr:
	"""Given 1-N interface parameters to set, build up a set of suitable
	URLs for the get request.
	"""
	def __init__(self, fLog, dNode):
		"""
		Args:
			fLog - A file-like object for error messages
			dProto - The 'protocol' section of a catalog object
		"""
		self.dNode = None
		self.dQuery = {}
		self.fLog = fLog

		if 'interface' not in dNode:
			fLog.write("   ERROR: Source node is missing the 'interface' element")
		if 'protocol' not in dNode:
			fLog.write("   ERROR: Source node is missing the 'protocol' element")
		elif 'httpParams' not in dNode['protocol']:
			fLog.write("   ERROR: Node protocol definition is missing the 'httpParams' element.")
		elif 'baseUrls' not in dNode['protocol']:
			fLog.write("   ERROR: Node protocol definition is missing the 'baseUrls' element.")
		else:
			self.dNode = dNode

	def setProperty(self, sProperty, value):
		"""Set a single interface property

		Args:
			sProperty (string) - The path to a property item within the node's 
			   interface definition.

			value (bool|int|float|string) - The value to be set
		Returns (bool):
			true if the param value could be set
		"""
		if not self.dNode: return False
		if not sProperty or not isinstance(sProperty, str):
			fLog.write("   ERROR: Invalid property path %s"%sProperty)
			return False

		lPath = sProperty.strip('/').split('/')
		dProp = _getElement(self.fLog, self.dNode['interface'], lPath)
		if not dProp: return False

		if 'set' not in dProp:
			fLog.write("%s is not a settable interface property"%sProperty)
			return False
		
		dSet = dProp['set'] # The translation interface

		dParams = self.dNode['protocol']['httpParams']

		if 'param' not in dSet:
			fLog.write("   ERROR: key 'param' missing in settable property.")
			return False
		sParam = dSet['param']

		# Check to see that referenced param actually exists
		if sParam not in dParams:
			fLog.write("   ERROR: Invalid httpParam reference from interface '%s' "%sParam)
			return False

		# If the settable thing is an enumeration, make sure the value
		# is in the enum.
		if 'enum' in dSet:
			lAccept = []
			for dEnum in dSet['enum']:  # Enumeration is list of objects
				if 'value' not in dEnum:
					fLog.write("   ERROR: enum missing value in settable property")
					return False
				lAccept.append(dEnum['value'])
				if dEnum['value'] == value:
					break                 # Hold on to this enum
				
			if value not in lAccept:
				fLog.value("   ERROR: Value '%s' is not a member of %s"%value, lAccept)

			# Enum items can set a flag on it's own
			if 'flag' in dEnum: value = dEnum['flag']

			# Enum items can alter the pass through value
			if 'pval' in dEnum: value = dEnum['pval']
		
		else:
			sFlag = None
			if 'flag' in dSet: sFlag = dSet['flag']  # Am I setting a flag
			if 'pval' in dSet: value = dSet['pval']  # will alter the pass through value

		
		# Now I know the value and if I'm a flag or not, if regular param set it
		if sFlag == None:
			self.dQuery[sParam] = str(value)
			return True
		
		# Handle flag params
		if 'flags' not in dParams[sParam]:
			fLog.write("   ERROR: HTTP parameter '%s' has no flags to set."%sParam)
			return False
		if sFlag not in dParams[sParam]['flags']:
			fLog.write("   ERROR: Invalid flag '%s' for HTTP parameter '%s'"%(sFlag, sParam))
			return False

		dFlag = dParams[sParam]['flags'][sFlag]

		if 'prefix' in dFlag:
			sFlagVal = "%s%s"%(dFlag['prefix'], dFlag['value'])
		else:
			sFlagVal = dFlag['value']
		
		if sParam not in self.dQuery:
			self.dQuery[sParam] = sFlagVal
		else:
			sSep = " "
			if 'flagSep' in dHParam: sSep = 'flagSep'
			self.dQuery[sParam] += "%s%s"%(sSep, sFlagVal)
		
		return True


	def getUrls(self):
		if not self.dNode: return None

		lOut = []
		for sBase in self.dNode['protocol']['baseUrls']:

			if len(self.dQuery) > 0:
				if '?' in sBase: sPre = '&'
				else: sPre = '?'

				lQuery = [
					"%s=%s"%(sKey, quote_plus(str(self.dQuery[sKey])))
					for sKey in self.dQuery
				]

				lOut.append("%s%s%s"%(sBase, sPre, "&".join(lQuery)))
			else:
				lOut.append(sBase)

		return lOut


def _translateSettings(fLog, dNode, dSettings):
	"""Given a list of interface settings, generate a set of URLs

	Args:
		fLog - A file-like object for errors
		dNode - An HttpStreamSrc or WebSocSrc catalog object
		dSettings - A dictionary of interface settings to translate
	"""

	bldr = UrlBldr(fLog, dNode)

	for sSetting in dSettings:
		bldr.setProperty(sSetting, dSettings[sSetting])

	return bldr.getUrls()

#############################################################################

def _hostSimpleName(sBase):
	sLow = sBase.lower()
	if sLow.startswith('https'):  sLow = sLow[8:]
	elif sLow.startswith('http'): sLow = sLow[7:]
	elif sLow.startswith('wss'): sLow = sLow[6:]
	elif sLow.startswith('ws'): sLow = sLow[5:]

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

def _addInCtrlId(dParam, sId):
	"""Append and input control ID to an HTTP param"""
	if not '_inCtrlId' in dParam:
		dParam['_inCtrlId'] = [sId]
	elif sId not in dParam['_inCtrlId']:
		dParam['_inCtrlId'].append(sId)

def _addInIfCtrlVal(dParam, sVal):
	if not '_inIfCtrlVal' in dParam:
		dParam['_inIfCtrlVal'] = [sVal ]
	elif sVal not in dParam['_inIfCtrlVal']:
		dParam['_inIfCtrlVal'].append(sVal)


def _inputVarTextAspect(fOut, dParams, dVar, sProp, sCtrlId):
	"""Create a text entry field for a variable property such as 'minimum' or 
	'resolution'.  In addition to the given property the 'units' property is 
	inspected so this function isn't unsable for general options.

	Args:
		dParams: The httpParams dictionary.  The control ID will be listed here
			if a control is generated.
		dVar: The dictionary for the overall variable
		sProp: The dictionary key for the aspect, ex: 'maximum'
		sCtrlId: The id to use for the generated control, if any.

	Returns:
		0 if no control was created, 1 otherwise
	"""
			
	if sProp not in dVar: return 0
	dAspect = dVar[sProp]
	
	if 'set' not in dAspect: return 0
	
	dSet = dAspect['set']
				
	if 'units' in dAspect:  sUnits = dAspect['units']
	elif 'units' in dVar:   sUnits = dVar['units']['value']
	sUnitLbl = " (%s)"%sUnits
	sPropLbl = sProp[0].upper() + sProp[1:]

	sout(fOut, '<label for="%s">%s%s</label>'%(sCtrlId, sPropLbl, sUnitLbl))
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
		_addInCtrlId(dParams[ dSet['param'] ]['flags'][ dSet['flag'] ], sCtrlId)
	else:
		_addInCtrlId(dParams[ dSet['param'] ], sCtrlId)
	
	return 1 
	
def _inputItemBoolean(fOut, dParams, dItem, sMsg, sCtrlId):
	"""Create a boolean checkbox for an item with a boolean value with a 'set'
	member.

	This control generator is useful for both variables and options as it does
	not inspect the contained option group.  Typically this is used with the
	variable 'enable' aspect or for boolean options.

	Args:
		dParams: The 'httpParams' dictionary
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
		_addInCtrlId(dParams[ dSet['param'] ]['flags'][ dSet['flag'] ], sCtrlId)
		_addInIfCtrlVal(dParams[ dSet['param'] ]['flags'][ dSet['flag'] ], dSet['value'])
	else:
		_addInCtrlId( dParams[ dSet['param'] ], sCtrlId	)
		_addInIfCtrVal( dParams[ dSet['param'] ], dSet['value'])
	return 1

		
def _inputItemEnum(fOut, dParams, dItem, sMsg, sCtrlId, sDisabled):
	"""Create a select list control for an enum item with a 'set' member.
	
	This control generator is useful for both variables and options as it does
	not inspect the contained option group.  One example where this is useful is
	selecting the output units for the Voyager Spectrum Analyzer data.

	Args:
		dParms: The 'httpParams' dictionary
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
	sout(fOut, '<select id=%s %s>'%(sCtrlId, sDisabled))
	
	# If the current value is not in the enum, put it here without mapping 
	# information so it can't be sent
	bAddDefault = True
	for dMap in dSet['enum']:
		if dMap['value'] == dItem['value']: 
			bAddDefault = False
			break
	
	if bAddDefault:
		sCtrlVal = dItem['value']
		if 'label' in dItem:  sCtrlVal = dItem['label']
		sout(fOut, '   <option value="" selected>%s</option>'%sCtrlVal)
		
	for dMap in dSet['enum']:
	
		sSelected = ""
		if dMap['value'] == dItem['value']: sSelected = "selected"
		if 'pval' in dMap: sVal = dMap['pval']
		elif 'flag' in dMap: sVal = dMap['flag']
		else: sVal = dMap['value']

		sCtrlVal = dMap['value']
		if 'label' in dMap:  sCtrlVal = dMap['label']

		sout(fOut, '   <option value="%s" %s>%s</option>'%(sVal, sSelected, sCtrlVal))

		if 'param' in dMap: sParam = dMap['param']
		elif 'param' in dSet: sParam = dSet['param']
		
		# Save the control id's in the flag_set, but since we are saving the same
		# control id in multiple members also as an '_ifCtrlVal' item as well.	
		if 'flag' in dMap:
			_addInCtrlId(dParams[ dSet['param'] ]['flags'][ dMap['flag'] ], sCtrlId)
			_addInIfCtrlVal(dParams[ dSet['param'] ]['flags'][ dMap['flag'] ], sVal)
		elif 'flag' in dItem:
			_addInCtrlId(dParams[ dSet['param'] ]['flags'][ dItem['flag'] ], sCtrlId)
		else:
			_addInCtrlId(dParams[ dSet['param'] ], sCtrlId)
			_addInIfCtrlVal(dParams[ dSet['param'] ], sVal)

	sout(fOut, '</select>')
	

def _prnVarForm(fOut, sCtrlPre, dParams, sVarId, dVar):
	"""Output non-submittable HTML form controls for the configurable aspects
	of a variable and record the control IDs alongside the http get params
	they modify.

	Args:
		sCtrlPre: A prefix to add to all generated control IDs

		dParams:  The 'httpParams' dictionary from the HttpStreamSrc catalog 
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
	elif 'label' in dVar: sTitle = dVar['label']
	
	if 'label' in dVar: sName = dVar['label']
	else: sName = sVarId[0].upper() + sVarId[1:]
	
	# If this variable has text aspects, label them up front
	dProps = dVar['props']
	lProps = ('min', 'max', 'res', 'inter')
	bLabelRow = False
	for sProp in lProps:
		if (sProp in dProps) and ('set' in dProps[sProp]):
			bLabelRow = True
			break

	if bLabelRow: sout(fOut, "<p><b>%s: &nbsp;</b>"%sName)
	else: sout(fOut, '<p>')
	
	# Right now I'm assuming the type of field for each property, should look
	# at the 'set' statement to get this info
	
	for i in range(len(lAspects)):
		sCtrlId = "%s_%s_%s"%(sCtrlPre, sVarId, lProps[i])
		nCtrls += _inputVarTextAspect(fOut, dParams, dVar, lAspects[i], sCtrlId)

	if 'enabled' in dProps:
		sCtrlId = "%s_%s_enabled"%(sCtrlPre, sVarId)
		sMsg = "Enable <b>%s</b>"%sName
		if 'title' in dVar: sMsg = "%s - %s"%(sMsg, dVar['title'])
		_inputItemBoolean(fOut, dParams, dProps['enabled'], sMsg, sCtrlId)
		
	if 'units' in dProps:
		sCtrlId = "%s_%s_units"%(sCtrlPre, sVarId)
		_inputItemEnum(fOut, dParams, dProps['units'], "Set %s Units"%sName, sCtrlId)
	
	sout(fOut, "</p>")

	return nCtrls


# Helper for _prnOptGroupForm
def _startGroupDisabled(dProps):
	"""Loop through a Group's properties, if:
	   1. has property named enabled 
	   2. the enable property is part of an xorGroup
	   3. The default value of enabled is false

	return the string 'disabled' else return ''
	"""
	if 'enabled' in dProps:
		if 'xorGroup' in dProps['enabled']:
			if 'value' in dProps['enabled']:
				if dProps['enabled']['value'] == False:
					return "disabled"
	return ""


def prnOptGroupForm(
	fOut, sCtrlPre, dParams, sGroup, dGroup, sSrcUrl, bVar=False,
	bSingleGroup=False
):
	"""Run through all the options in a group making output controls for each
	settable property

	Args:
		fOut (file-like): The file-like object receive output

		sCtrlPre (str): The prefix to assign to control IDs
		
		dParams (str): The 'httpParams' dictionary
		
		sGroup (str): The name of the group ('time', 'csv', etc.)
		
		dGroup (dict): The group dictionary, must containe a sub-dict of settable
		   properties under the key 'properties'

		sSrcUrl (str): The URL to the resource that provided the input HttpStreamSrc.
		   Only used for error messages.
		
		bVar (bool): This group represents the options for a single coordinate or
			data variable.  Certian display options are enable for variable 
			groups, such a putting mix,max,resolution in a single line and looking
			around for units strings.

	Returns (int): 
		The number of HTML form controls generated.

	Notes:  If the group has a settable 'enabled' property, then all other
	   controls for the group will be enabled/disabled based on the enabled
	   setting.
	"""
	nCtrls = 0
	
	dProps = dGroup['props']
	lProps = list(dProps.keys())

	# if the property group has an property order listing, try to respect it
	if 'order' in dGroup:
		lProps = dGroup['order']
	else:
		lProps.sort()

	# This list of controls to toggle for group enable/disable, order is 
	# signaler and then signalees
	lJsToggle = [None, []] 

	# Get the group name
	sGrpName = sGroup
	if 'label' in dGroup: sGrpName = dGroup['label']
	
	# Any option name can be used, but some are recognized as having particular 
	# meanings, especially in the context of a variable.  If this is a variable
	# make sure min,max,res,int are presented in that order.
	tOneLiner = ('enabled', 'min','max','res','inter')
	sGrpUnits = None
	if bVar:
		lFirst = []
		lRest = []
		for sKey in tOneLiner:
			if sKey in lProps: lFirst.append(sKey)
		for sKey in lFirst: lProps.remove(sKey)	
		lProps = lFirst + lProps
		
		if 'units' in lProps: sGrpUnits = dProps['units']['value']
	
	# Weed out all the props that aren't settable
	lSettable = []
	for sProp in lProps:
		if isinstance(dProps[sProp], dict) and 'set' in dProps[sProp]: 
			lSettable.append(sProp)
	lProps = lSettable

	# First pass, run through controls and see if this group is disabled
	# to start with:
	sDisabled = _startGroupDisabled(dProps)

	#sys.stderr.write("Settable props for %s: %s\n"%(sGrpName, lSettable))

	for iProp in range(len(lProps)):
		sProp = lProps[iProp]
		dProp = dProps[sProp]
		curval = None
		
		sPropUnits = None
		if 'units' in dProp: sPropUnits = dProp['units']
		elif sGrpUnits: sPropUnits = sGrpUnits
		
		# Note: The type of curval is unknown at this point
		if 'value' in dProp: curval = dProp['value']
		else:
			_missingKeyError(fOut, '%s:%s:value'%(sGroup, sProp), sSrcUrl)
			return 0
		
		if ('set' not in dProp) or ('param') not in dProp['set']:
			#sout(fOut, "%s: %s &nbsp"%(sProp, curval))
			continue
			
		# make a row prefix
		#if not bVar:
		#	if iProp == 0: sout(fOut, "<p>")
		#	else: sout(fOut, "</p>\n<p>")
		#else:
		if (bSingleGroup):
			if (iProp > 0): sout(fOut, "<br>")
		else:
			if (iProp == 0): sout(fOut, "<p><b>%s: &nbsp;</b>"%sGrpName)
			
			# if this isn't a classical one-liner, start a new row 
			if sProp not in tOneLiner: sout(fOut, "<br> &nbsp; ")
		
		# Get the target param (or param flag) to recive a link to the fake 
		# controls
		dSet = dProp['set']
		if 'flag' in dSet:
			dTargParam = dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]
		else:
			dTargParam = dParams[ dSet['param'] ]

			
		if 'label' in dProp: sName = dProp['label']
		else: sName = sProp[0].upper() + sProp[1:]

		sCtrlId = "%s_%s_%s"%(sCtrlPre, sGroup, sProp)
		lJsToggle[1].append(sCtrlId)
		
		if 'flag' in dSet: sCtrlVal = dSet['flag']
		elif 'pval' in dSet: sCtrlVal = dSet['pval']
		else: sCtrlVal = "%s"%curval
		
		# There are four basic types of controls: 
		#
		#  radio buttons, check boxes, text boxes, select boxes.  
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
			if bVar or (sProp == "enabled"):
				sName = "Output"
				if 'title' in dGroup: sInfo = dGroup['title']
				elif 'label' in dGroup: sInfo = dGroup['label']
				else: sInfo = sGroup
			else:
				if 'title' in dProp: sInfo = dProp['title']
				elif 'label' in dProp: sInfo = dProp['label']
			
			sChecked = ""
			if curval == True: sChecked = "checked"
			
			# Some boolean options are part of a radio group	
			if 'xorGroup' in dProp:
				# If we're used xor groups, the in control ID must be the xor group
				# name, not the section or the property.
				sXorGroup = "%s_%s"%(sCtrlPre, dProp['xorGroup'])

				sout(fOut, 
					'<input type="radio" name="%s" id="%s" value="%s" %s><b>%s</b> - %s'%(
			     	sXorGroup, sCtrlId, sCtrlVal, sChecked, sName, sInfo)
				)
				lJsToggle[0] = sCtrlId

			else:
				sout(fOut, '<input type="checkbox" id="%s" value="%s" %s %s><b>%s</b> - %s'%(
			     	sCtrlId, sCtrlVal, sChecked, sDisabled, sName, sInfo)
				)

			#print('dParams.keys()  = ', list(dParams.keys()))
			
			# Save off the control information
			if 'flag' in dSet:
				_addInCtrlId(dTargParam, sCtrlId)
			else:
				_addInCtrlId(dTargParam, sCtrlId)

		elif sType == 'select':
			if 'title'  in dProp: sMsg = dProp['title']
			elif 'label' in dProp: sMsg = dProp['label']
			else:                 sMsg = sProp[0].upper() + sProp[1:]
			
			if 'enum' in dSet:  # True enums... 
				_inputItemEnum(fOut, dParams, dProp, sMsg, sCtrlId, sDisabled)
				
			else:
				# Effective enum, binary choice
				sout(fOut, sMsg)
				sout(fOut, '<select id=%s %s>'%(sCtrlId, sDisabled))
				sout(fOut, '  <option value="%s">%s</option>'%curval)
				
				if 'pval' in dSet: sVal = dSet['pval']
				elif 'flag' in dSet: sVal = dSet['flag']
				else: sVal = dSet['value']
				
				sout(fOut, '  <option value="%s">%s</option>'%(sVal, dSet['value']))
				sout(fOut, '</select>')
				
				# Save off the control information, with an if check for the
				# select value
				if 'flag' in dSet:
					_addInCtrlId( dTargParam, sCtrlId)
					_addInIfCtrlVal(dTargParam, sVal)
				else:
					_addInCtrlId(dTargParam, sCtrlId)
					_addInIfCtrlVal(dTargParam, sVal)

		else:		
			if bVar:
				if sPropUnits: sout(fOut, '%s (%s)'%(sName, sPropUnits))
				else: sout(fOut, '%s '%sName)
			else:
				if 'title' in dProp:
					sout(fOut, '<label for="%s">%s</label>'%(sCtrlId, dProp['title']))
				else:
					sout(fOut, '<label for="%s">%s</label>'%(sCtrlId, sName))
				
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
			
			sout(fOut, '<input type="text" id="%s" size="%d" value="%s" %s %s>'%(
				sCtrlId, nSize, sCtrlVal, sReq, sDisabled))
			
			# Save off the control information
			if 'flag' in dSet:
				_addInCtrlId( dTargParam, sCtrlId)
			else:
				_addInCtrlId(dTargParam, sCtrlId)
			
		nCtrls += 1
		
	
	sout(fOut, "</p>")

	# Emitt a little group enable, disable javascript if needed
	if lJsToggle[0]:
		sSignaler = lJsToggle[0]
		if sSignaler in lJsToggle[1]:
			lJsToggle[1].pop(lJsToggle[1].index(sSignaler))
		if len(lJsToggle[1]) > 0:
			sout(fOut, '''<script>
var el_%s = document.getElementById('%s');
el_%s.onchange = function(bPropagate = true) {'''%(sSignaler, sSignaler, sSignaler)
			)
			for sDest in lJsToggle[1]:
				sout(fOut, "   var el_%s = document.getElementById('%s');"%(sDest, sDest))
				sout(fOut, "   el_%s.disabled = !Boolean(this.checked);"%sDest)

			# Browsers won't auto-fire the onchange event for deselected items 
			# (I have no freaking idea why) so we need to find everything else
			# in our group and fire it's onchange manually.  At this point we 
			# have no way to know what else might be created in our signaler's 
			# button group so we'll have to do the lookup at run-time
			sout(fOut, """
   if(bPropagate){
      var siblings = document.getElementsByName( this.name )
      for(i=0; i < siblings.length; i++){
         if(!(siblings[i] === this))
            siblings[i].onchange(false);
      }
   }
}
</script>""")
	
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
		# Assume it's enabled if no properties 
		if 'props' not in dTmp:
			dFmt = dTmp
			sType = sFmt
			break
		else:
			dProps = dTmp['props']
			if ('enabled' in dProps) and ('value' in dProps['enabled']):
				if dProps['enabled']['value']:
					dFmt = dTmp
					sType = sFmt
					break

	if not dFmt: return None

	sVer = None
	if _hasElement(dFmt, ('props','version','value')):
		sVer = dFmt['props']['version']['value']

	sSerial = None
	if _hasElement(dFmt, ('props','serial', 'value')):
		sSerial = dFmt['props']['serial']['value']
		
	return F.getMime(sType, sVer, sSerial)

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
	'parameters').  So in addition, we have to have a way to remove the 'name'
	attribute from parameters that would otherwise get kicked out the door.
	
	If these protocols (and others) were created in the spirit of HTML this
	wouldn't be needed, but alas, not everyone wants to make life easy for
	browser client developers, so here's the plan...
	
	Basic form handling works like this

	1. 'examples', 'coordinates', 'data', 'options', 'formats' are parsed.
	   All controls are generated without a name so they cannot be transmitted.
	   (With the exception of radio controls, see step 5 below)

	2. For any option group (aka "coordinates.time", or "formats.das") if the
	   enabled property (aka 'coordinates.time.enabled') is set to false, then
	   everything but the enable/disable control is disabled and an event
	   handler is emitted to toggle the disabled state as needed.
	
	3. All controls are generated with an ID, that has the form:
	  
	      prefix + "_" + [coord|data|options|...] + "_" + 
	      [optGroup] + "_" + [property_setting ]
	
	   This insures all controls have a unique ID even if multiple http get
	   sources are combined into a single page.
	
	4. As each control is created it adds it's control ID to the relavent 
	   parameter in 'httpParams'.  If the parameter is a FLAG_SET, then the
	   control ID is added to the flag entry instead of the top level. 
	
	5. After all fake controls are generated, 'httpParams' is parsed and all
	   'httpParams' with a control ID attached are created as hidden text 
	   entry forms that are themselves nameless.  The to-potentially-be-submitted
	   controls are created with the following ids:
	
     	   prefix + httpParams name
	
	6. An onSubmit function is generated for the form with the following 
	   name:
	
	      prefix + "_OnSubmit"
	
	   and the httpParmas element is added as a variable.  When called 
	   onSubmit inspects the controls registered in 'httpParams' and sets
	   new control values.  Finnally the output controls that have data 
	   values are given a name so that they can be submitted, and the 
	   input radio controls have thier names removed.

	...whew

	--cwp
	"""
	
	sSrcUrl = dSrc['_url']

	if 'contacts' in dSrc:
		sout(fOut, "<p>Technical problems using this data source should be "
		     "directed to: <b>")
		lTmp = [d['name'].strip() for d in dSrc['contacts']]
		sout(fOut, ", ".join(lTmp))
		sout(fOut, "</b>.</p>")

	for sKey in ('protocol','interface'):
		if sKey not in dSrc:
			return _missingKeyError(fOut, sKey, sSrcUrl)
		else:
			dProto = dSrc['protocol']
			dIface = dSrc['interface']

	if 'authentication' in dProto:
		if _isTrue(dProto['authentication'], 'required'):
			sout(fOut, '<p><i><span class="error">Restricted data source</span>.</i>')
			if 'REALM' in dProto['authentication']:
				 sout(fOut, 'You will be asked to authentication to the realm "' +\
				      '<b>%s</b>" on submit.</p>'%dProto['authentication']['realm'])
			else:
				sout(fOut, "You will be asked to authentication on submit.</p>")

	# Print the examples
	if 'examples' in dIface:
		sout(fOut, "<p>Example queries:")
		lExamples = dIface['examples']
		iTmp = 0
		for dExample in lExamples:
			iTmp += 1
			sTmpTxt = "Example %d"%iTmp
			if 'label' in dExample:	sTmpTxt = dExample['label']
			elif 'title' in dExample: sTmpTxt = dExample['title']
			lTmpUrl = _translateSettings(fLog, dSrc, dExample['settings'])
			if lTmpUrl:
				sout(fOut, '<a href="%s">%s</a> &nbsp;'%(lTmpUrl[0], sTmpTxt))
		sout(fOut, "</p>")

	# Leave the form action blank, we'll set it depending on which submit
	# button is used.

	sBaseUri = bname(dSrc['_url']).replace('.json','')
	sFormId = "%s_download"%sBaseUri
	sout(fOut, '<form id="%s">'%sFormId)

	# Go through the base URLs see if they have any keys already set, if so
	# we'll need hidden form parameters to cover those as well
	if 'baseUrls' not in dProto:
		return _missingKeyError(fOut, 'protocol:baseUrls', dSrc['_url'])
	
	_setHidden(fOut, dProto['baseUrls'])

	dParams = None
	if 'httpParams' in dProto: dParams = dProto['httpParams']
	nSettables = 0
	
	# Handle setting coord options, always do time first if it's present
	if dParams and ('coords' in dIface):
		# Find out if any coordinates provide subselect
		dCoords = dIface['coords']
		bSubSet = False
		bEnable = False
		lMod = []

		# Gather all settable coordinates
		for sCoord in dCoords:
			if 'props' in dCoords[sCoord]:
				for sProp in dCoords[sCoord]['props']:
					if 'set' in dCoords[sCoord]['props'][sProp]:
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
			sout(fOut, '<br>')
	
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
			for sProp in dData[sVar]['props']:
				if 'set' in dData[sVar]['props'][sProp]:
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
			sout(fOut, '<br>')
		
		for sVar in dData:
			for sProp in ('units','enabled'):
				if sProp in dData[sVar]['props']:
					if 'set' in dData[sVar]['props'][sProp]:
						if sProp == 'enabled':	bEnable = True
						else: bUnits = True
						if sVar not in lMod: lMod.append(sVar)
					
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
			for sVar in lMod:
				nSettables += _prnVarForm(fOut, sBaseUri, dParams, sVar, dData[sVar])
				
			sout(fOut, "</div>")
			sout(fOut, "</fieldset>")
	
	# Handle setting general options, these are handled as a single property
	# group
	if dParams and ('options' in dIface) and ('props' in dIface['options']):
		dProps = dIface['options']['props']

		lOptions = list(dProps.keys())
		
		lMod = []
		for sProperty in dProps:
			if 'set' in dProps[sProperty]:
				if sProperty not in lMod: lMod.append(sProperty)

		# Don't allow enable, disable in the generic options group
		if 'enabled' in dProps:
			fLog.write("   WARNING: Ignoring 'enabled' property in general options.")
			dProps.pop('enabled')

		if len(lMod) > 0:				
			sout(fOut, "<fieldset><legend><b>Options:</b></legend>")
				
			nSettables += prnOptGroupForm(fOut,
				sBaseUri, dParams, 'options', dIface['options'], sSrcUrl, False, True
			)
	
			sout(fOut, "</fieldset>\n<br>")

	# Handle setting format options
	if dParams and ('formats' in dIface):
		dFormats = dIface['formats']
		fLog.write('   Inspecting formats: %s'%str(list(dFormats.keys())))
		bEnable = False
		
		# See if any of the formats have settable properties
		nFmtOpts = 0
		lModFmts = []
		for sFmt in dFormats:
			dFmt = dFormats[sFmt]
			if 'props' in dFmt:
				for sProp in dFmt['props']:
					if 'set' in dFmt['props'][sProp]:
						if sFmt not in lModFmts: 
							# Put enabled stuff in before disabled stuff
							if (sProp == 'enabled') and \
								_isElTrue(dFmt, ['props','enabled','value']):
								lModFmts = [sFmt] + lModFmts
							else:
								lModFmts.append(sFmt)
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

			#lModFmts.sort()
			for sFmt in lModFmts:
				nSettables += prnOptGroupForm(fOut, 
					sBaseUri, dParams, sFmt, dFormats[sFmt], sSrcUrl, False
				)

			sout(fOut, "</div>")
			sout(fOut, "</fieldset>")
			sout(fOut, '<br>')
	else:
		fLog.write('INFO: Output format is not selectable.')


	# Stage 4, inspect httpParams and output hidden controls with no name.
	if dParams and (nSettables > 0):
		nSettables = 0
		for sParam in dParams:
			dParam = dParams[sParam]
			if 'type' not in dParam: continue

			bOut = False
			if dParam['type'] == 'FlagSet':
				if 'flags' not in dParam: continue
				
				for sFlag in dParam['flags']:
					dFlag = dParam['flags'][sFlag]
					if '_inCtrlId' in dFlag:
						bOut = True
						break
			
			# If one boolean UI control set's a particular enum value then it needs
			# to record that pval in it's interface description
			#elif dParam['type'] == 'enum':
			#	if 'enum' not in dParam: continue
			#	
			#	for sItem in dParam['enum']:
			#		dItem = dParam['enum'][sItem]
			#		if '_inCtrlId' in dItem:
			#			bOut = True
			#			break
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
	var lKeep = [];

	for(let sParam in dParams){
		dParam = dParams[sParam]
		
		if(!("_outCtrlId" in dParam)) continue;
		var ctrlOut = document.getElementById(dParam["_outCtrlId"]);
		var sOutName = dParam["_outCtrlId"].replace(sNamePre, "");
		lKeep.push(sOutName);
		
		// Flagset parameters, the most complicated ones
		if( ('type' in dParam) && (dParam['type'] == 'flag_set')){
		
			if( !('flags' in dParam) ) continue;
			
			var dFlags = dParams[sParam]['flags'];
			var sOutVal = "";
			var sOutSep = " ";
			if( 'flagSep' in dParam) sOutSep = dParam['flagSep'];
			
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

			// Multiple controls might be trying to set my value, but I only care
			// about ones that are currently enabled
			var ctrlIn = null;
			for(let i = 0; i < dParam['_inCtrlId'].length; i++ ){
				var sInId = dParam["_inCtrlId"][i];
				ctrlIn = document.getElementById(sInId);
				if(!ctrlIn.disabled ) break;
				else ctrlIn = null;
			}
			if(ctrlIn === null) continue; 
			
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

	// To finalize, iterate over all values to be submitted by the form.  If 
	// they ain't one of my output values, disable them.
	elForm = document.getElementById('%s');
	for(let i in elForm.elements){
		let sName = elForm.elements[i].name;
		if((sName != "") && (! lKeep.includes(sName)))
			elForm.elements[i].name = "";
	}

	elForm.action = sActionUrl;
}
</script>
	"""%(sFuncName, sJson, sNamePrefix, sFormId))
		
		# Make one submit function per base url that starts with https
		for sBase in dProto['baseUrls']:

			if sBase.startswith('ws'): continue  # Ignore websocket sources for regular browsers

			sLabel = "Download"
			if len(dProto['baseUrls'])	> 1:
				sLabel = "Download from %s"%_hostSimpleName(sBase)

			sout(fOut, '<input type="submit" value="%s" onclick=\'%s("%s");\'>'%(
				sLabel, sFuncName, _getAction(sBase) 
			))

	sout(fOut, '</form>\n<br>')

	sout(fOut, '<div class="identifers">')
	#sout(fOut, '<br><br>Catalog Path: %s &nbsp; <br>'%dSrc['_path'])
	sout(fOut, '<span class="minor">Source definition: &nbsp; <a href="%s">%s</a></a></span>'%(
		dSrc['_url'], dSrc['_url']
	))
	
	if 'uris' in dSrc and len(dSrc['uris']) > 0:
		sout(fOut, '<br>Permanent IDs:')
		dSrc['uris'].sort()
		for sUri in dSrc['uris']: sout(fOut, " &nbsp; <i>%s</i>"%sUri)
	
	sout(fOut, '</div>')	

# ########################################################################## #
def _loadJson(fLog, sInPath):
	"""The missing 1-liner from the json module"""

	fLog.write("   Loading: %s"%sInPath)
	with open(sInPath) as fIn:
		dObj = json.load(fIn)
	return dObj

def _urlToCatPath(U, dConf, sUrl):
	"""Convert a URL back to a local catalog object path, or return None
	"""
	sScriptUrl = U.webio.getScriptUrl(dConf)
	if not sUrl.startswith(sScriptUrl): return None

	sUrlRoot     = "%s/source"%sScriptUrl
	sFileSysRoot = pjoin(dConf['DATASRC_ROOT'], 'root')

	sPath = sUrl.replace(sUrlRoot, sFileSysRoot).replace('/', os.sep)

	return sPath

	
# ########################################################################## #
def handleReq(U, sReqType, dConf, fLog, form, sPathInfo):
	
	fLog.write("\nLocal catalog node GUI handler")

	loadFormats(dConf)

	# Find the corresponding json object and load it
	sPathInfo = os.getenv("PATH_INFO")
	if not sPathInfo.startswith('/source/'):
		return U.webio.serverError(fLog, "PATH_INFO did not start with /source/")

	if not sPathInfo.endswith('.html'):
		return U.webio.serverError(fLog, "PATH_INFO did not end with .html")

	sFormUrl = "%s%s"%(U.webio.getScriptUrl(dConf), sPathInfo)
	sCatUrl  = sFormUrl.replace(".html",'.json')

	sLocalId = sPathInfo[len('/source/'):].strip('/')
	sRelPath = sLocalId.replace('/', os.sep).replace('.html','.json')
	
	sPath = pjoin(dConf['DATASRC_ROOT'], 'root', sRelPath)

	if not os.path.isfile(sPath):
		return U.webio.notFoundError(fLog, "PATH_INFO did not end with /form.html")

	try:
		dNode = _loadJson(fLog, sPath)
	except U.errors.QueryError as e:
		return U.webio.queryError(fLog, str(e))
		return 17
	except U.errors.ServerError as e:
		return U.webio.serverError(fLog, str(e));
		return 17

	# Slide in the json data location in case they want to look at it
	dNode["_url"] = sCatUrl

	if ('type' not in dNode) or ('catalog' not in dNode):
		return U.webio.serverError(fLog, "Unknown file at %s"%dNode['_url'])
	if dNode['type'] not in ('Catalog','SourceSet'):
		return U.webio.serverError(fLog, "Unknown object type %s in %s"%(
			dNode['type'], dNode['_url']
		))

	# If this is a source set, then pull up the HttpStreamSrc
	if dNode['type'] == 'SourceSet':
		# Now overlay the node
		sSrcPath = None
		sSrcUrl  = None
		for sSource in dNode['catalog']:
			if ('type' in dNode['catalog'][sSource]) and \
				(dNode['catalog'][sSource]['type'] == 'HttpStreamSrc'):
				sSrcUrl = dNode['catalog'][sSource]['urls'][0]
				sSrcPath = _urlToCatPath(U, dConf, sSrcUrl)
				break
		if not sSrcPath:
			return U.webio.notFoundError(
				fLog, "%s %s does not have an HttpStreamSrc node"%(
				dNode['type'], sPath 
			))

		try:
			dSrcNode = _loadJson(fLog, sSrcPath)
		except U.errors.ServerError as e:
			return U.webio.serverError(fLog, str(e))

		# Update the url, and swap-in
		dSrcNode['_url'] = sSrcUrl
		dNode = dSrcNode

	# ...okay should output something 
	sScriptUrl = U.webio.getScriptUrl(dConf)

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

	#U.page.header(dConf, fLog)
	
	# Add side navigation bar to top level categories, need to put this in a
	# libray call
	pout('<div class="main">')
	
	U.page.sidenav(dConf, fLog, True)
	
	pout('<div class="article">')

	# ####################################################################### #
	# The main show #

	U.page.navheader(dConf, fLog, sPathInfo)
	if ('label' in dNode) or ('title' in dNode):
		pout("<h1>")
		if 'label' in dNode:
			pout('<b>%s</b> - '%dNode['label'])
		if 'title' in dNode:
			pout(dNode['title'])
		pout("</h1>")
	else:
		pout("<h1>Untitled Data Source</h2>")

	if 'description' in dNode:
		pout("<p>\n%s\n</p>")%dNode['description']

	try:
		fOut = StringIO()

		if dNode['type'] == 'Catalog':
			prnCatalog(fLog, dNode, fOut)
		else:
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
	
	#U.page.footer(dConf, fLog)

	pout('''</body>
</html>''')
	
	return 0
