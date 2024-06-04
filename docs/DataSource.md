# Das Catolog: HttpStreamSrc version 0.7

In the federated dat3 catalog system, an HttpStreamSrc objects defines a
source which:
1. May be contacted via an HTTP GET message
2. Is optionally supplied option via query parameters in the URL
3. Responds to a single request
4. Then closes the connection

This page descripts the HttpStreamSrc object type but is not a normative definition.
That is provided by the associated JSON schema (in work).  If anything in this 
contradicts the associated JSON schema (once released) the schema is authoritative.

For reference, the top levels of an HttpStreamSrc are represented below.  This
example is for the uncalibratiod Electron Particle Distibution data (EPD) from
the Advanced Cusp Electrons (ACE) detector on TRACERS:
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
**HttpStreamSrc** objects have the following top level elements.

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

The simple elements: `type`, `version`, `label`, `title`, and `description` are common to all
catalog objects.  Of the other sub-objects, `contacts` is rather straight forward.  Thus the focus
here will be to describe the purpose and usage of the `protocol` and `interface` objects.

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

### httpParams

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

FlagSet types are commonly used for enabling and 1-N parameters (or variables in CDF) 
from housekeeping data sources that can output many different parameters.

## Interface object

At the protocol level HTTP parameters have no particular meaning.  They are just 
a list of permissible values and formats.  Interface objects provide the end-user
presentation layer overtop of the direct server protocol, and most importantly
*tie protocol params to dataset coordinates*.   

For reference the upper sections of the example ACE IPD interface object are
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
    // An extra option group to allow for interface controls that aren't
    // tied to a particular coordinate, data parameter, or output format
  }
}
```

The top level sub-objects of interface and thier purpose are:

|Key | Value | Required | Purpose  |
|----|-------|----------|----------|
|coords | object | maybe | Ties protocol query parameters to returned dataset coordinates.  Required if HTTP params can alter the coordinates or  coordinate range of output dataset |
|data | object | maybe | Ties protocol query parameters to the returned primary data values.  Required if HTTP params can alter the primary data (not coordinate) values |
|formats | object | yes | Defines the available output formats and relates protocol query parameters to an output format |
|examples | object | yes | Provides a pre-set selections for the coordinates, data and formats that are known to produce valid data |
|options | object | no | This is a catch-all for other end-user options that don't fall into the other categories. |

### Interface Option Groups

Interface options are grouped together to control multiple options for 
as single output item or aspect.  The exact item type varies by section
as listed below:

| Interface Section | Affects | Examples |
|-------------------|---------|----------|
| coords | One group per output coordinate | time/min, time/max, time/res, angle/sum |
| data   | One group per output data varaiable | flux/enable | 
| formats | One group per output format | das/serial |
| options | Non-grouped properties, no meaning except as provided in labels | filter/apid |

When presenting options to the end user it is good to preserve the grouping. 
For example the minimum, maximum and resolution options from a "time" coordinate
group could be presented in a single line as follows:

```
                +----------+           +----------+              +----------+
Time:   Minimum |          |   Maximum |          |   Resolution |          |
                +----------+           +----------+              +----------+
```

### Individual Interface Options

Two example user interface properties from the ACE EPD datasouce follow for reference.

First the `coords/time/min` property.
```json
"min" : {
   "label" : "Minimum",
   "value" : null,
   "title" : "Minimum time value to stream",
   "set" : { "param" : "read.time.min"}
}
```
and the `format/das/version` property.
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
2. The `value` is changable because the property contains a `set` entry
3. The query parameter used to change this property on the server is `read.time.min`
4. There is no further information in `set` so the user entered value is passed through as the HTTP GET parameter value.

From the definition of the interface property, `format/das/version` we can see that:
1. The default value is `das3`
2. This value is changable because the property has the `set` member
3. We use the HTTP GET parameter `format.version` to change this value.
4. Only an enumerated set of values are allow for this parameter, `das3` and `das2'.
5. We change our value to `das2` by giving the value `2` in the HTTP GET parameter `format.version`.

Properties have the following top level entries:

| Key | Value Type | Required | Purpose |
|-----|------------|----------|---------|
| label | string | yes | Provide a short string for the property, typically used on a GUI form |
| title | string | no  | Provide a longer name for the property, typically used on a mouse tool-tip |
| type | string | no | Defaults to `string` if not specified.  The supported property types are: `string`,`bool`,`isotime`,`numeric` |
| value | string | yes | The default value of the property.  The JSON value `null` indicates no default value |
| set  | object | Makes this a settable property and ties the setting to the `protocol` section |

### Recommended GUI controls

In general interface value GUI input is an unconstrained string. Thus text boxes will often
suffice.  

Constraints on the input type can be imposed by the data type:
* `bool` - A 

The `set` member of a property may impose further constraints.  Currently defined 
constraints are:
* `enum` - Provides a fixed list of values and can be displayed as a list box
* `range` - Provides at bounding range for a value where the mininmum value is *inclusive* and the upper bound is *exclusive*.









