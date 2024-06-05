# Das Catolog: HttpStreamSrc version 0.7

The most common das3 end-point is a streaming data service that accessed
using the GET method of the HTTP protocol.  The details of each streaming
service is defined by an HttpStreamSrc node in the das3 federated catalog
system.  This nodes information is formatted in JSON and it defines a
source which:

1. May be contacted via an HTTP GET message
2. Is optionally supplied option via query parameters in the URL
3. Responds to a single request
4. Then closes the connection

This page descripts the HttpStreamSrc object type, version 0.7 but it is not
a normative definition.  That is provided by the associated JSON schema (in work).
If anything in this description contradicts the associated JSON schema (once
released) the schema is authoritative.

Overviews and individual snippets of JSON files are described here.  To help
put everything in context two example node files are include along with 
screenshots of GUIs generated from the nodes.  It may be helpful to refer to
them while reading each section.  Firefox is recommended for viewing example
JSON files.

|Example Name | Node File | Rendered GUI |
|-------------|-----------|--------------|
| Housekeeping | [ex01_node_hsk-analog.json](example_nodes/ex01_node_hsk-analog.json) | [ex01_node_hsk-analog.png](example_nodes/ex01_node_hsk-analog.png) |
| Particle Distribution | [ex02_node_sci-epd.json](example_nodes/ex02_node_sci-epd.json) | [ex02_node_sci-epd.png](example_nodes/ex02_node_sci-epd.png) |

## HttpStreamSrc Root-Level Objects

**HttpStreamSrc** objects have the following top level items.

| Key | Value  | Required | Purpose |
|-----|--------|---------|-----------
|type    | `HttpStreamSrc`  | yes | Identifies the catalog object type |
|version | string | yes | Identifies the version of the type definition, highest is currently 0.7 as of 2024-05-30 |
|label   | string | no | A token or short description, typically less then 20 chars |
|title   | string | no | A longer description typically less then 50 chars |
|description | list[string] or string | no | A short narrative about this data source. May be a simple string or a list of strings if the description is multiple paragraphs long | 
| contacts | list[objects] | no | The contact list for this data source.  May be used by GUIs to send messages to the maintainer |
| interface | object[objects] | yes | Defines recommended user interface for interacting with this data source |
| protocol | object[objects] | yes | Defines the GET API for interacting with this data source  |

To put this in a more familiar form, heres the top levels of the HttpStreamSrc
for the uncalibratiod Electron Particle Distibution data (EPD) from the Advanced
Cusp Electrons (ACE) detector on TRACERS:
```json5
{
  "type" : "HttpStreamSrc",
  "version" : "0.7",
  "label" : "ACE_fm1_EPD",
  "title" : "ACE FM-1: Electron Distribution Level 1",
  "contacts" :  [   ],  
  "protocol" :  {   },  // Value described in the Protocol section below
  "interface" : {   }   // Value described in the Interface section below
}
```

The simple elements: `type`, `version`, `label`, `title`, and `description` are common 
to all catalog objects.  Of the other sub-objects, `contacts` is rather straight forward.
Thus the focus here will be to describe the purpose and usage of the `protocol` and 
`interface` objects.

## The Protocol Object

The protocol object defines the HTTP GET method query keys understood by this data source.
For reference the upper sections of the protocol object for ACE instrument IPD data source
continues below.
```json5
{
  "method" : "GET",
  "baseUrls" : [
    "https://tracers-dev.physics.uiowa.edu/stream/source/preflight/l1/ace/fm-1/epd/flex"
  ],
  "authorization" : {  "required":false },
  "httpParams" : {
    "read.time.min" :   { "required":true,  "type":"isotime" },
    "read.time.max" :   { "required":true,  "type":"isotime" },
    "bin.time.max"  :   { "required":false, "type":"real",    "units":"s" },
    "read.apid" :       { "required":false, "type":"enum",    "enum":["x2a2", "x2a3", "x2af", "x2b2", "x2b3" ] },
    "format.sigdigit" : { "required":false, "type":"integer", "range":[2, 17] },
    "format.delim" :    { "required":false, "type":"string" }
    // other HTTP GET keys defined here
  }
}
```

Protocol objects have the following top-level sub-items.

|Key | Value | Required | Purpose  |
|----|-------|----------|----------|
|method | `GET` | yes | Merely documents that HTTP GET requests are expected |
|baseUrls | list[string] | yes | provides 1-N *fully qualified* access URLs for this data source. |
|authorization | object | yes | provides the HTTP Auth Realm if authorization is required for the data source |
|httpParams | list[object] | maybe | If this data source supports query parameters they are listed here. |

### HTTP GET Parameters

For each HTTP GET parameter there is a key in the httpParams object that has same name
as the associated GET parameter.  Each value under http params is an object defining:
1. If the query parameter required
2. The data type of the query parameter's value
3. Extended information based on the data type.

The possible data types for httpParams.`KEY`.type are detailed below:
| Type  | Description | Usage Example |
|-------|-------------|---------------|
|string |arbitrary input | `format.delim=,` |
|isotime|ISO-8601 String, UTC assumed | `read.time.min=2024-01-01T14:03` |
|integer|An integer, optionally signed | `format.sigdigit=4` |
|enum   |One of a list of strings | `read.apid=x2a3` |
|FlagSet|1-N strings combined via a separator | `read.data=mcp_hv,reg_33dv` |

The FlagSet type is commonly used for enabling 1-N parameters (called variables in CDF) 
from data sources that provide many individual output channels.

## The Interface Object

At the protocol level HTTP parameters have no particular meaning.  They are just 
a list of permissible values and formats.  Interface objects provide the end-user
presentation layer overtop of the direct server protocol, and most importantly
*tie protocol params to dataset coordinates*.

The interface object defines a set of source *properties*.  Most properties are
listed because they are changable, though it is possible to list properties 
merely as documentation of the output data stream.

For reference, the upper sections of the example ACE IPD interface object are
given below.

```json5
{
  "coords":{
    // This is the coordinates option category.  Any option that affects
    // a particular coordinate may be placed here.  The most common case
    // is sub-setting data streams in a "time" coordinate.
    "time":{
      // This option group is associated with the "time" coordinate in the associate data stream
    },
    "energy":{
      // This option group is associated with the "energy" coordinate in the associated data stream
    }
  },
  "data" : {
    "flux" : {
      // This option group is for "flux" data values in the associated data stream
    }
  },
  "formats" : {
    // There is one option group here for each format type that can be emitted.
    // There are no pre-ordained output formats.  Any type may be listed.
    // It's the client's job to ignore user controls for formats that the can
    // not use.
    "das" : {
      // Option group for das stream formatted output 
    },
    "ccsds" : {
      // Option group for CCSDS packet stream formatted output
    }
  },
  "examples" : [
    // The examples list provides named presets of other options.  Every datas
    // source is required to provide at least one example.  The example below
    // provides min and max time coordinate properties, and a label for the
    // end user.
    {
      "settings" : {
        "coords/time/props/min" : "2024-05-23T23:05",
        "coords/time/props/max" : "2024-05-23T23:16"
      },
      "label" : "Most Recent 10 minutes"
    }
  ],
  "options" : {
    // An extra property group to allow for interface controls that aren't
    // tied to a particular coordinate, data parameter, or output format
  }
}
```

The top level sub-objects of `interface` and thier purposes are:

|Key | Value | Required | Purpose  |
|----|-------|----------|----------|
|coords | object | maybe | Ties protocol query parameters to returned dataset coordinates.  Required if HTTP params can alter the coordinates or  coordinate range of output dataset |
|data | object | maybe | Ties protocol query parameters to the returned primary data values.  Required if HTTP params can alter the primary data (not coordinate) values |
|formats | object | yes | Defines the available output formats and relates protocol query parameters to an output format |
|examples | object | yes | Provides a pre-set selections for the coordinates, data and formats that are known to produce valid data |
|options | object | no | This is a catch-all for other end-user options that don't fall into the other categories. |

### Interface Property Groups

Interface properties are grouped together to control multiple aspects of
as single output item.  *What* is being controlled varies by section as
listed below:

| Interface Section | Contains | Examples |
|-------------------|---------|----------|
| coords | One group per output coordinate | time/min, time/max, time/res, angle/sum |
| data   | One group per output data varaiable | flux/enable | 
| formats | One group per output format | das/serial |
| options | Non-grouped properties, no meaning except as provided in labels | filter/apid |

When presenting options to the end user it is good to preserve the grouping. 
For example the minimum, maximum and resolution properties from a "time" coordinate
group could be presented in a single line as follows:
```
                +----------+           +----------+              +----------+
Time:   Minimum |          |   Maximum |          |   Resolution |          |
                +----------+           +----------+              +----------+
```
Preservation of a coordinate property groups can be seen in the
[ex02_node_sci-epd](example_nodes/ex02_node_sci-epd.png) example.

### Individual Interface Properties

Two example user interface properties from the ACE EPD datasouce follow for reference.

First the `coords/time/min` option.
```json
"min" : {
   "label" : "Minimum",
   "value" : null,
   "title" : "Minimum time value to stream",
   "set" : { "param" : "read.time.min"}
}
```
and the `format/das/version` option.
```json
"version" : {
  "label" : "Stream Version",
  "value" : "das3",
  "type" : "enum",
  "set" : {
    "param" : "format.version",
    "enum" : [ 
    	{ "value" : "das3", "pval" : "3" },
        { "value" : "das2", "pval" : "2" }
    ]
  }
}
```
From the definition of the interface property, `coords/time/min` we can see that:
1. Has no default value because `value` is null.
2. The `value` is changable because it contains a `set` entry.
3. The query parameter used to change this option on the server is `read.time.min`
4. There is no further information in `set` so the user entered value is passed through
   as the HTTP GET parameter value.

From the definition of the interface property, `format/das/version` we can see that:
1. The default value is `das3`
2. This value is changable because the property has the `set` member
3. We use the HTTP GET parameter `format.version` to change this value.
4. Only an enumerated set of values are allow for this parameter, `das3` and `das2'.
5. We change our value to `das2` by giving the value `2` in the HTTP GET parameter `format.version`.

Individual properties have the following top level entries:

| Key | Value Type | Required | Purpose |
|-----|------------|----------|---------|
| label | string | yes | Provide a short string for the property, typically used on a GUI form |
| title | string | no  | Provide a longer name for the property, typically used on a mouse tool-tip |
| type | string | no | Identifies formation rules for the property value, the default is `string` which has no constraints. The supported property types are: `string`, `boolean`, `isotime`, `integer`, `real` and `enum` |
| value | string or null | yes | The default value of the property.  The JSON value `null` indicates no default value |
| set   | object | no  | Makes this a settable property and ties the setting to the `protocol` section |

### Recommended GUI controls by Value Type

Clients are of course free to interpret the intent of an HttpStreamSrc catalog node
as they see best.  The following GUI controls are merely suggestions.  As always,
the client developer knows thier audiance best and can implement any interface as
they see fit.

* `boolean` - Provide a single check-box for the end user
* `isotime` - Provide a text entry field that validates input as ISO-8601 style strings
   with UTC timezone assumed (examples: 2024-06-05, 2024-06-05T18:05, 20204-06-05T18:05:33.456 )
* `integer` - Provide a text entry field, possibly with constraints if the `range` constraint is given
* `real` - A text entry field, possibly with constraints as above
* `enum` - A drop list of selectable items, with more then one level if there many items are in the enumeration
* `string` - A text box with no validation.

As a secondard consideration, if most of the properties for an entire section,
such as `data` are just simple booleans, putting a group indicator around the 
entire section is reasonable.

### Set Objects, the Interface to Protocol Gateway

Once the user has selected all values from the GUI, those selections must be communicated
to the server to produce the desired output.  The front-end Interface may be quite different
from the back-end protocol.  The objects that tie interface choices to protocol parameters
lives under the key named `set`.  Any property with a `set` sub-object is a "settable".  Set
object can have the following keys:

| Key   |  Required | Purpose |
|-------|----------|----------|
| param | yes | The Protocol HTTP parameter that communicates the new value to the server |
| flag  | maybe | If the Protocol HTTP parameter is a `FlagSet` then the particular flag entry is provided here | 
| value | no  | This provides the new interface property value if set. It replaces the default property value |
| pval  | no  | The actual value to send to the server, which may be different from `value` | 
| enum  | no  | Can be used in place of `value` above.  This provides an enumerated list of `value` and `pval` pairs. |

The following exmaple uses the Microchannel Plate Current housekeeping parameter from the
ACE analog housekeeing data source.  The relavent Protocol and Interface section of the 
catalog file are reproduced below:
```json5
{
  "interface":{
    "data":{
      "mcp_i":{
        "label":"MCP I", "title":"Micro-channel Plate, Current",
        "props":{
           "enabled":{
             "type":"boolean",
             "value":false,
             "set":{ "value":true, "param":"read.data", "flag":"mcp_i" }
           }
         }
      },
      "stack_hv": {
        "label": "STACK V", "title": "Stack High Voltage"
        "props": {
          "enabled": {
            "type": "boolean",
            "value": false,
            "set": { "value": true, "param": "read.data", "flag": "stack_hv"  }
          }
        }   
      },
      // ...other data property groups follow
    }
  },
  "protocol":{
    "read.data": {
      "type": "FlagSet",
      "required": false,
      "flagSep": ",",
      "flags": {
        "mcp_i": {     "value": "mcp_i" },      
        "stack_hv": {  "value": "stack_hv" }
        // ...other flags follow
      }
    }    
  }
}
```
If the user were to select a couple checkbox indicating that micro-channel plate currents are
desired.  Then the client would:
1. Look up the indicated parameter `read.data` in the Protocol section.
2. Find the entry for the flag named `mcp_i`.
3. See that setting this flag requires that the string `mcp_i` be emitted for the parameter
   value.  Since only on flag was set, the `flagSep` string is not needed.
4. Add the following string to the HTTP GET request:
   `read.data=mcp_i`

As you can see in the JSON snippit above, multiple UI options may map down to a single
backend protocol parameter.

