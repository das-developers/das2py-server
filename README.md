# das2-pyserver

[Das2](https://das2.org) servers typically provide data relevant to space plasma and magnetospheric
physics research.  To retrieve data, an HTTP GET request is posted to a das2 
server by a client program and a self-describing stream of data values covering
the requested time range, at the requested time resolution, is provided in the
response body.  This software provides a caching middleware layer between 
server-side das2 readers, which stream data at full resolution to standard out, and
remote client programs such as [Autoplot](https://autoplot.org) or custom
programs written in Python ([das2py](https://anaconda.org/DasDevelopers/das2py))
or IDL ([das2pro](https://github.com/das-developers/das2pro) ).

*das2-pyserver* consists of python scripts that run external programs, called
readers, which provide the full resolution data streams.  Since they are
external programs, readers may be written in **any** desired programming
language and have **any** desired software license.  When a request for data is
received, das2-pyserver inspects the HTTP GET URL and checks to see if its
local cache contains the required data, at the desired time resolution or
better.  If the request is already cached, an HTTP request body is generated
from cache blocks.  If not, the associated reader program and data reducer are
invoked on the server and the standard output stream from the 
`"reader_prog | reducer_prog"` pipeline is delivered as the request body.

## Installation Prequisites

Compilation and installation of das2-pyserver has only been tested in Linux
environments and depends on the following tools:

1. Python >= 2.6, or Python >= 3.4
2. Apache2, any remotely recent version configured with at least one CGI
   directory
3. [Redis](https://redis.io), known to work with version 3.2.12, will
   likely work with older versions as well.
4. python-redis - the python bindings for Redis
5. [libdas2](https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3) - efficent
   das2 stream processors written in C and their python bindings

Since libdas2 provides small binaries needed by das2-pyserver, and since there
are no pre-built libdas2.3 packages, installing instructions for both sets of
software are included below.  In these instructions the '$' character is used
at the beginning of a line to indicate commands that you'll need to run in a 
bourne compatible shell (bash, ksh, etc.).

For convienience, package installation commands for das2-pyserver and libdas2.3
are provided below for CentOS 7:
```bash
$ sudo yum install gcc subversion git                     # for source downloads
$ sudo yum install expat-devel fftw-devel openssl-devel   # needed to build libdas2.3
$ sudo yum install python3 python3-numpy python3-devel    # needed to bulid das2py
$ sudo yum install --enablerepo=epel install redis        # needed for caching

$ sudo yum install --enablerepo=epel install python2-redis 
# -- or --
$ sudo pip3 install redis                                   
```
and Debian 9.1:
```bash
$ sudo apt-get install gcc subversion git                     # for source downloads
$ sudo apt-get install libexpat-dev libfftw3-dev libssl-dev   # needed to bulid libdas2.3
$ sudo apt-get install python3-dev python3-distutils python3-numpy  # to build das2py
$ sudo apt-get install redis-server                           # needed for cacheing

$ sudo apt-get install python-redis
# -- or --
$ sudo apt-get install python3-redis
```

## Getting the sources

For now some of the sources are in a University of Iowa SVN and some are on
github.com.  All sources will be moved to github.com as time permits.

```bash
$ svn co https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3
$ git clone https://github.com/das-developers/das2-pyserver.git
```

## Build and install libdas2.3, das2py, and das2-pyserver

Decide where your das2-pyserver code and configuration information will reside. 
In the example below I've  selected `/usr/local/das2srv` but you can choose
any location you like.  These environment variables will be used through out
the setup, so leaving your terminal window open though the testing stage will
save time.

```bash
$ export PREFIX=/usr/local/das2srv   # Adjust to taste
$ export PYVER=3.6                   # or 2.7, or 3.7 etc.
$ export N_ARCH=/                    # no need for per-OS directories
$ export SERVER_ID=solar_orbiter     # for example. no whitespace
```

Test your `PYVER` setting by making sure the following command brings up a
python interpreter:

```bash
$ python$PYVER
```

The following sequence will build, test, and install libdas2.3 and das2py
if you have all prerequisite libraries installed:

```bash
$ cd libdas2_3
$ make
$ make test
$ make pylib
$ make pylib_test
$ make install
$ make pylib_install
```

Now build and install the python module and example configuration files.
The commands below will also setup a example data sources that you can
delete later.

```bash
$ cd ../das2-pyserver
$ python${PYVER} setup.py install --prefix=${PREFIX} --install-lib=${PREFIX}/lib/python${PYVER}
```

Finally, copy over the example configuration file:

```bash
$ cd $PREFIX/etc
$ cp das2server.conf.example das2server.conf
```

## Configure Apache

Apache configurations vary widely by Linux distribution and personal taste.
The following procedure is provided as an example and has been tested on
CentOS 7.

First determine which directory on your server maps to an Apache HTTPS CGI
directory.  To do this inspect `/etc/httpd/conf/httpd.conf` (or similar).
The default is `/var/www/cgi-bin`.  To provide a better URLs for your site add
the line:

```apache
ScriptAlias /das/ "/var/www/cgi-das/"
```

directly under the line:

```apache
ScriptAlias /cgi-bin/ "/var/www/cgi-bin/"
```

inside the `<IfModule alias_module>` section of httpd.conf.  

Then provide configuration information for your `/var/www/cgi-das` directory
inside the `/etc/httpd/conf.d/ssl.conf` file.  We're editing the ssl.conf 
instead of the httpd.conf file because das2 clients may transmit passwords. 


```apache
<Directory "/var/www/cgi-das">
  Options ExecCGI FollowSymLinks

  # Make sure Authorization HTTP header is available to Das CGI scripts
  RewriteRule ^ - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
  RewriteEngine on

  AllowOverride None
  Allow from all
  Order allow,deny
</Directory>
```

By default, authorization headers are not made available to CGI scripts.  The
re-write rule above allows the `Authorization` header to be based down to the
`das2_srvcgi_main` script.  This is needed to allow your das2 server to
support password protected datasets.  

Now symlink the \*_srvcgi_\* scripts into your new CGI directory.  Choose the
name of the symlink carefully as it will be part of the public URL for your
site:

```bash
cd /var/www/cgi-das
sudo ln -s $PREFIX/bin/das2_srvcgi_main server
sudo ln -s $PREFIX/bin/das2_srvcgi_main log
```

Set the permissions of the log directory set in the `LOG_PATH` variable 
in `das2server.conf` so that Apache can write log data.

```bash
chmod 0777 $PREFIX/log   # Or change the ownership
```

Finally trigger a re-read of the Apache configuration data:

```bash
sudo systemctl restart httpd.service
sudo systemctl status httpd.service
```

## Test the server

Test the server by pointing your web browser at:

```
https://localhost/das/server
https://localhost/das/log
```
If this works try browsing your new server with Autoplot.  To do so, copy the
following URI in to the Autoplot address bar and hit the green "Go" button:

```
vap+das2server:https://localhost/das/server
```

## Next steps

The CGI scripts and worker programs read thier configuration data from the
file:

```bash
$PREFIX/etc/das2server.conf
```

Take time to customize a few items in your config file such as the 
`site_name` and the `contact_email`.   You may also want change the file
`${PREFIX}/static/logo.png` or even the style sheet at 
`${PREFIX}/static/das2server.css` to something a little nicer.

Das2-pyserver is a caching and web-transport layer for das2 readers.  Readers
are the programs that generate the initial full resolution data streams.  The
entire purpose of das2-pyserver and das2 clients is to leverage the output of
your reader programs to produce efficient, interactive science data displays.
To assist you with the task of creating readers for your own data, examples
are included in the `$PREFIX/examples` directory.  These examples happen to be
written in python, however there is no requirement to use python for your
programs, in fact much more efficent compiled languages such as Java,
[D](https://dlang.org/) and C++ are more suitable for the task.  Any language
may be used so long as:

  1) all data are written to standard output
  2) all error messages are written to standard error

For further information on your das2-pyserver instance, including:

  * reader programs
  * authentication 
  * request caching
  * [federated catalog](https://das2.org/browse) integration
  * automatic [HAPI](https://github.com/hapi-server/data-specification) conversion

consult the users guide document  `das2_pyserver_ug.odt` included in the root
of the repository.


