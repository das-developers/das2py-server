# Das Catolog: HttpStreamSrc version 0.7

In the federated dat3 catalog system, an HttpStreamSrc objects defines a
sources which 
1. May be contacted via an HTTP GET message
2. Responds to a single request
3. Then closes the connection

This page descripts the HttpStreamSrc object type but it is not a normative definition.  That is provided by the associated JSON schema (in work).  If this narrative contradicts the associated schema, the schema is authoritative.

**HttpStreamSrc** objects have the following top level elements:

| Key | Value  | Required | Purpose |
|-----|--------|---------|-----------
|type    | `HttpStreamSrc`  | yes |Identifies the catalog object type |
|version | string | yes | Identifies the version of the type definition, highest is currently 0.7 as of 2024-05-30 |
|label   | string | no | A very short description, or token typically less then 20 chars |
|title   | string | no | A longer description typically less then 50 chars |
|description | list[string], string | A short narrative about this data source. May be a simple string or a list of strings if the description is multiple 
paragraphs long | 
| contacts | list[objects] | no | The contact list for this data source.  May be used by GUIs to send messages to the maintainer |
| interface | object | yes | Defines recommended user interface for interacting with this data source |
| protocol | object | yes | Defines the GET API for interacting with this data source  |


The simple elements: `type`, `version`, `label`, `title`, and `description`
are common to all catalog objects.  In addition contacts itself is rather straight forward.  Thus the focus here will be to describe the purpose and 
usage of the `protocol` and `interface` sections.

For reference the top levels of an HttpStreamSrc are represented below.  This
example is for the uncalibratiod Electron Particle Distibution data (EPD) from
the Advanced Cusp Electrons (ACE) detector on TRACERS:
```json
{
  "label" : "ACE_fm1_EPD",
  "title" : "ACE FM-1: Electron Distribution Level 1",
  "type" : "HttpStreamSrc",
  "version" : "0.7",
  "contacts" : [
    // ...
  ],
  "protocol" : {
    // ...
  },
  "interface" : {
    // ...
	}
}
```

## Protocol object

The protocol object defines the HTTP GET method query keys understood by
this data source.  It has the following sub-items

|Key | Value | Required | Purpose  |
|----|-------|----------|----------|
|method | `GET` | yes | Merely documents that HTTP GET requests are expected |
|baseUrls | list[string] | yes | provides 1-N *fully qualified* access URLs for this data source. |
|authorization | object | yes | provides the HTTP Auth Realm if authorization is required for the data source |
|httpParams | list[object] | yes* | If this data source has query parameters these are listed here. |

For reference the upper sections of a protocol object for ACE IPD continues below:
```json
{
  "method" : "GET",
  "baseUrls" : [
    "https://tracers-dev.physics.uiowa.edu/stream/source/preflight/l1/ace/fm-1/epd/flex"
  ],
  "authorization" : {   "required":false },
  "httpParams" : {
    "read.time.min" : { "required":true, "type":"isotime" },
    "read.time.max" : { "required":true, "type":"isotime" },
    "read.apid" : {     
    	"required":false, "type":"enum",  "enum":["x2a2", "x2a3", "x2af", "x2b2", "x2b3" ]
    },
    "format.version" :{  "required" : false, "type" : "string" },
    "format.sigdigit" : {
      "required":false, "type":"integer", "range":[2, 17]
    }
    // ...
  }
}
```

### httpParams

For each HTTP GET parameter there is a key in the httpParams object that has 
same name as the associated GET parameter.  Each value under http params is 
an object defining:
1. If a parameter is required
2. The data type of the parameter's value
3. Extended information based on the data type.

*TODO: List all value types here*


## Interface object

At the protocol level HTTP parameters have no particular meaning.  They are just 
a list of permissible values and formats.  Interface objects provide the end-user
presentation layer overtop of the direct server protocol, and most importantly
**tie protocol params to dataset coordinates**.   

For reference the upper sections of the example ACE IPD interface object are
given below.

```json
{
  "coords" : {
    "time" : {
      // Provides information on the "time" coordinate group and associated options
      "props" : {
        "min" : {
        	 "label" : "Minimum"
        	 // ... more information on coordinate property "coords/time/min"
        	}
        },
        "max" : {
        	  "label": "Maximum"
        	   // ... more information on coordinate property "coords/time/max"
          }
        },
        "res" : {
          "label" : "Resolution"
          // ... more information on coordinate property "coords/time/res"
        }
      },
      "validRange" : [
        // ... optional valid range for this coordinate
      ]
    }
  },
  ,
  "data" : {
    "flux" : {
      "label" : "counts",
      "props" : {
        "enabled" : {
        	// ... more information on property "data/flux/enabled" 
        }
      }
    }
  }
  "options" : {
    "label" : "Options",
    "props" : {
      "filter" : {
        "label" : "AppID Filter",
        "title" : "Filter output data by CCSDS AppID",
        // ... more information on general property 'options/filter'
      }  
    }
  },
  "examples" : [
    {
      "settings" : {
        "coords/time/props/min" : "2024-05-23T23:05",
        "coords/time/props/max" : "2024-05-23T23:16"
      },
      "label" : "Most Recent 10 minutes"
    }
  ],
  "formats" : {
  	 // There is one object here for each format type that can be emitted
    "das" : {
      "label" : "das stream",
      "title" : "Streaming format for plots",
      "mimeTypes" : [
        "application/vnd.das2.das2stream",
        "application/vnd.das.stream",
        "text/vnd.das2.das2stream"
      ],
      "props" : {
        "enabled" : {
          // More information on the formats/das/enabled property
          }
        },
        "version" : {
          "label" : "Stream Version",
          // more information on the formats/das/version property
        }
      }
    }
  }
}
```

The top level sub-objects of interface and thier purpose are:

|Key | Value | Required | Purpose  |
|----|-------|----------|----------|
|coords | object | conditional | Ties protocol parameters to returned
dataset coordinates.  Required if HTTP params can alter the coordinates or coordinate
range of output dataset |
|data | object | conditional | Ties protocol parameters to the returned
primary data values.  Required if HTTP params can alter the primary data
(not coordinate) values |
|formats | object | yes | Defines the service output format and relates
HTTP parameters to selectable output formats |
|examples | object | yes | Provides a pre-set selections for
the coordinates, data and formats that are know to produce valid data |
|options | object | no | This is a catch-all for other end-user options that don't fall 
into the other categories. |

### Displaying Property Groups

Interface options are grouped together to control multiple properties of a single 
output item.  This varies by section as listed below:

| Interface Section | Affects | Example|
|-------------------|---------|--------|
| coords | Properties of one output coordinate | time/min, time/max, time/res, angle/sum |
| data   | Properties of one output data variable | flux/enable | 
| formats | Properties of one output format | das/serial |
| options | Non-grouped properties, no meaning except to human user | filter/apid |


When presenting options to the end user it is good to preserve the grouping. 
For example the minimum, maximum and resolution groups from time could be presented
in a single line as follows:

```
               +----------+           +----------+              +----------+
Time   Minimum |          |   Maximum |          |   Resolution |          |
               +----------+           +----------+              +----------+
```

### Interface Properties

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

From this definition we can see that the first interface property, `coords/time/min`:
1. Has no default value because `value` is null.
2. The value is changable because it has a `set` entry
3. We can use the HTTP GET param `read.time.min` to change the value


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
From this definition we can see that the second interface property, `format/das/version`:
1. Has the default value `das3`
2. This value is changable because it has the `set` member
3. We use the HTTP parameter `format.version` to change this value.
4. We change our value to `das2` by giving the value `2` to format.version.  
   Consulting the Protocol section above, we see that this would appear as:
   ```
   format.version=2
   ```
   in the HTTP GET query string.

Properties have the following top level entries:

| Key | Value Type | Purpose |
|-----|------------|---------|
| label | string | Provide a short string for the property, typically used on a GUI form |
| title | string | Provide a longer name for the property, typically used on a mouse tool-tip |
| value | string | The default value of the property |
| set  | object | Makes this a settable property and ties the setting to the `protocol` section |











