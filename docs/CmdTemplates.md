# das2-pyserver command templates

The most important job of the das2py-server is to convert URLs into data
streams.  Since actual data file reading is handled by sub-programs, the
means URLs must be converted to command pipe lines. 
```
        +----------+                      +-------+
URL --> |  server  | --> command line --> | Shell | --> data stream
        +----------+                      +-------+
```

For the das2/v2.3 protocol, the URL path defines the data source.  And the
URL GET parameters define how the source should select and process data 
prior to output.

In older versions of the server there was a rather fixed translation between
URL parameters and command lines.  The v2.3 server makes the translation
between HTTP GET parameters and command lines more flexible by defining each
command to be run via a template.

There are default templates for:

  * Fourier transforms
  * Binning in one coordinate dimension
  * Data coverage in one coordate dimension
  * Translating streams to various output formats

The default templates are located in the `etc/commands.json` file in your
server root install directory.  Most of the commands used by the default 
templates are provided by the [das2C](https://github.com/das-developers/das2C)
module.  These stream processes are written in C for efficency.

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

The special character `@` may be used to reference the query value in the
replacement text.

### Example 1: Translation of a Query Parameter 

In the following example the PARAM_SELECTOR is only triggered on the presence or absence 
of an HTTP GET parameter.

The template:
```
#[read.time.min # -beg @ # -beg 2020-01-14 ]#
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

### Example 2: Translation of a Query Parameter and Flag

Query flags bare explaination.  Though it wasn't the original intent of the
HTTP query interface, it's all too common for protocols to pack many different
individual settings into the value of a single HTTP query parameter, with each one
acting as it's own sub-parameter. Take for example the following URL snipit:
```
  ?parameters=Epoch,Bx,By&
```
The tokens `Epoch`, `Bx`, `By` are acting as flags, where each flag is separated by
a comma.

For an even more extreme case, observe the following URL snipit from the Cassini
RPWS data source:
```
   ?params=lfdr:ExEw,mfdr:ExEw,mfr:13ExEw,hfr:ABC12EuEvExEw
```
which has *values* for each flag.  Obviously each flag in this example should be
it's own query parameter.

To deal with this all too common situation, the PARAM_SELECTOR may denote a flag
value, the separator for the flags, and even the separator between a flag and it's value!
```
#[ PARAM[FLAG_NAME][FLAG_SEP][SUB_SEP] #  Replacement if present  #  Replacement if absent]
```

Here's and example template for extracting the `mfr` value from a flag.  Given the 
template:
```
#[params[ ][mfr][=] # -mfr @ # ]
```
the following translations would occur:
```
HTTP GET:         ?params=lfdr=ExEw mfr=13ExEw hfr=ABC12EuEvExEw&
Template Output:  -mfr 13ExEw
```

## Required Parameters

To denote a required parameter leave off the third section of the template.  Since there is
no information on what to do if a parameter is not given, then the template cannot handle
the translation.  Thus *required* parameters have the following form:

```
   #[ PARAM_SELECTOR # output when selector matches ]
```

Since it's common to directly output the value of an HTTP keyword a short form of the
required parameter template may also be used:

```
   #[ PARAM_SELECTOR ]
```






