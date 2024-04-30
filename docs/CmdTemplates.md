# das2-pyserver command templates

The most important job of the dasflex server is to convert URLs into data
streams.  Since actual data file reading is handled by sub-programs, the
means URLs must be converted to command pipe lines. 
```
        +----------+                      +-------+
URL --> |  server  | --> command line --> | Shell | --> data stream
        +----------+                      +-------+
```

For the das v3.0 API, the path component of the URL selects the data source.
When data are requested, the URL GET parameters define how the source
should operate.

In older versions of the server there was a rather fixed translation between
URL parameters and command lines.  The v3.0 server makes the translation
between HTTP GET parameters and command lines more flexible by defining each
command to be run via a template.

There are default templates for:

  * Fourier transforms
  * Binning in one coordinate dimension
  * Data coverage in one coordate dimension
  * Translating streams to various output formats

The default templates are located in the `etc/commands.json` file in your
server root install directory.  Most of the default stream manipulation 
commands in default templates are provided by the [das2C](https://github.com/das-developers/das2C) 
module, as these stream processes are fast C programs with low memory
overhead.

**Note** The command templates defined here do not form a complete text
transformation language.  An arbitrary set of query keyword value pairs
cannot be translated into an arbitrary set of output text, and that's
okay.  Here das2 developers are providing a template tool that's sufficently
flexible to handle the many data streaming cases encountered over the years,
without going overboard.


## Command Template Format

Each command template specifies how to convert http query parameters into
command line text.  Since the point of command templates is to output 
sub-sections of a command line given a set of query parameters, the command
syntax was selected to avoid colliding with **bash** shell syntax as much as
possible.  All substitutions start with a `#` character which rather safely
translates to a comment if it escapes into a shell environment.  Furthermore
the other special tokens, `[` and `]` are deprecated special characters and 
can be avoided in shell scripts.

The basic format of a replacement template is:

```
    #[ PARAM_SELECTOR # output if selector matches  # output if selector does not match ]
```
where the `PARAM_SELECTOR` is one of:

  * An HTTP query parameter key
  * An HTTP query parameter key and flag

The special character `@` may be used to reference the parameter value in the
replacement text.

### Example Set 1: Translation of simple query parameters

In the following example the PARAM_SELECTOR is only triggered on the presence or absence 
of an HTTP GET parameter.

The template:
```
#[read.time.min # -beg @ # -beg 2020-01-14 ]
```
would reduce as follows if "read.time.min" were among the given GET parameters:
```
HTTP GET:         read.time.min = 2022-01-14T12:00
Template Output:  -beg 2022-01-14T12:00
```
and as follows if the HTTP GET parameter was not present:
```
HTTP GET:         (read.time.min not given)
Template Output:  -beg 2020-01-14
```

### Example Set 2: Translation of a query parameter values with sub-parameters

Query sub-parameters bare explaination.  Though it wasn't the original intent of
the HTTP query interface, it's all too common for protocols to pack many different
individual settings into the value of a single HTTP query parameter, with each one
acting as it's own sub-parameter. Take for example the following URL snippit:
```
  ?read=Epoch,Bx,By&...
```
The tokens `Epoch`, `Bx`, `By` are acting as flags, where each flag is separated by
a comma.

For an even more extreme case, observe the following URL snippit from the Cassini
RPWS data source:
```
   ?params=lfdr:ExEw,mfdr:ExEw,mfr:13ExEw,hfr:ABC12EuEvExEw
```
which has *values* for each flag.  Obviously each flag in this example should be
it's own query parameter.

To deal with this all too common situation, the PARAM_SELECTOR may denote:
   1. a parameter keyword  (required)
   2. a sub-parameter keyword
   3. a separator for sub-parameters
   4. a separator for sub-parameters and thier values

Here's the full syntax for a PARAM_SELECTOR:
```
#[ PARAM(SUB_SEP | SUB_PARAM | SUB_VAL_SEP) #  Replacement if present  #  Replacement if absent]
```
The SUB_SEP defaults to comma `,`.  By default the SUB_VAL_SEP is not defined and 
everything between two sub-seperators is taken to be the parameter name.  Thus for 
sub-parameters acting as flags, only the SUB_PARAM is needed.

Here's a few examples demonstrating flag values of increasing complexity.

Flag values separated by commas
```
HTTP GET:   bands=ExBy

Templates:  #[bands(|By) # --magnetic # ]  #[bands(,|Ex) # --electric # ]

Output:     --magnetic --electric
```

Flag values separated by spaces
```
HTTP GET:   bands=Ex By

Templates:  #[bands( |By) # --magnetic # ]  #[bands( |Ex) # --electric # ]

Output:     --magnetic --electric
```

Full sub-parameters pushed into a single query param:
```
HTTP GET:   params=lfdr=ExEw mfr=13ExEw hfr=ABC12EuEvExEw

Template:   #[params( |mfr|=) # -mfr @ # ]

Output:     -mfr 13ExEw
```

## Required Parameters

To denote a required parameter leave off the third section of the template.  With the
third section of the template missing, there is no information provided on what text
to output if a parameter is not given, and thus the template cannot handle the
translation.  This means *required* parameters have the following form:

```
   #[ PARAM_SELECTOR # output when selector matches ]
```

A very common pattern for required parameters is to output the value of the parameter
if detected.
```
#[ PARAM_SELECTOR # @ ]
```

Since this is so common, an even shorter template form is recognized:
```
#[ PARAM_SELECTOR ]
```

which is equivalent to `#[ PARAM_SELECTOR # @ ]` above.


## Predefined Parameters

When templates are evaluated by dasflex server, the following "parameters" are aways
defined and may be thus may always be used:

   * `_SERVER_` - The URL to the das2-pyserver root URL, for example https://jupiter.physics.uiowa.edu/das/server

   * `_LOCAL_ID_` - The local ID of the datasource, for example Juno/WAV/Survey

   * `_FILENAME_` - The automatically calculated output filename in case the attachment
      disposititon should be used

     
