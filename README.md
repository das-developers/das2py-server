# das2-pyserver

[Das2](https://das2.org) servers typically provide data relevant to space
plasma and magnetospheric physics research.  To retrieve data, an HTTP GET
request is posted to a das2 server by a client program and a self-describing
stream of data values covering the requested time range, at the requested time
resolution, is provided in the response body.  This software, *das2-pyserver*
provides a caching middleware layer between server-side das2 readers, which
stream data at full resolution to standard out, and remote client programs
such as [Autoplot](https://autoplot.org) or custom programs written in Python
([das2py](https://anaconda.org/DasDevelopers/das2py)), IDL
([das2pro](https://github.com/das-developers/das2pro) ) or 
C ([das2C](https://github.com/das-developers/das2C) ).

When a request for data is received, das2-pyserver inspects the HTTP GET URL
and checks to see if its local cache contains the required data, at the desired
time resolution or better.  If the request is already cached, an HTTP response
body is generated from cache blocks.  If not, the associated reader program and
data reducer listed in the DSDF (Data Source Description File) are invoked on
the server and the standard output stream from the  `"reader_prog | reducer_prog"`
pipeline is delivered as the response body.

Das2-pyserver itself is released under the GPL, but we have intentionally
separated the core server software from the data readers so that programs
written in **any** programming language, released under almost **any** license,
can plug into the system.

## Installation Prequisites

Compilation and installation of das2-pyserver has only been tested in Linux
environments and depends on the following tools:

1. Python >= 2.6, or Python >= 3.4
2. Apache2, any remotely recent version
3. [Redis](https://redis.io), known to work with version 3.2 or higher
4. [redis-py](https://redislabs.com/lp/python-redis/), known to work with version 2.10 or higher
5. [libdas2](https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3), latest version
   recommended

Since libdas2 provides small binaries needed by das2-pyserver, and since there
are no pre-built libdas2.3 packages, installation instructions for both libdas2
and das2-pyserver are included below.  In these instructions the '$' character
is used at the beginning of a line to indicate commands that you'll need to run
in a bourne compatible shell (bash, ksh, etc.).

Example prerequisite package installation commands are provided below for CentOS 7 \.\.\.
```bash
$ sudo yum install gcc subversion git                               
$ sudo yum install expat-devel fftw-devel openssl-devel             
$ sudo yum install python3 python3-numpy python3-devel              # or python2 equivalents
$ sudo yum install redis                    
$ sudo pip3 install redis                                           # if using python3
# --or--
$ sudo yum install python2-redis                                    # if using python2
```
\.\.\. and Debian 9:
```bash
$ sudo apt-get install gcc subversion git                           
$ sudo apt-get install libexpat-dev libfftw3-dev libssl-dev          
$ sudo apt-get install python3-dev python3-distutils python3-numpy  # or python2 equivalents
$ sudo apt-get install redis-server                                 
$ sudo apt-get install python3-redis                                # or python2 equivalent
```

## Get the Source

For now, some of the sources are in a University of Iowa SVN server and
some are on github.com.  All sources will be moved to github.com as time
permits.

```bash
$ svn co https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3
$ git clone https://github.com/das-developers/das2-pyserver.git
```

## Build and Install

Decide where your das2-pyserver code and configuration information will reside. 
In the example below I've  selected `/usr/local/das2srv` but you can choose
any location you like.  These environment variables will be used through out
the setup, so leaving your terminal window open though the testing stage will
save time.

```bash
$ export PREFIX=/usr/local/das2srv   # Adjust to taste
$ export PYVER=3.6                   # or 2.7, or 3.7 etc.
$ export SERVER_ID=solar_orbiter_2   # for example.  ID should not contain whitespace
```

Test your `PYVER` setting by making sure the following command brings up a
python interpreter:

```bash
$ python$PYVER
```

Build and install commands can run without `sudo` if the install directory
is created manually.  The following will make the install directory and set
it's ownership to the current account.  We will lock it down after install.
```bash
$ sudo mkdir $PREFIX
$ sudo chown $LOGNAME $PREFIX
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
Set `--install-lib` and `--prefix` as indicated, unless you want to hand
edit das2server.conf after installation.  There is no need to run `build`
before this step.

```bash
$ cd ../das2-pyserver
$ python${PYVER} setup.py install --prefix=${PREFIX} --install-lib=${PREFIX}/lib/python${PYVER}
```

Copy over the example configuration file:

```bash
$ cd $PREFIX/etc
$ cp das2server.conf.example das2server.conf
```

We are done with server software installation, lock down the install area (if desired). 
The `cache` subdirectory shoud be owned by the account that runs asynchronous 
data-reduction processing.  The cache subdirectory should not be owned by the
webserver account, or root, but any other account is fine.
```bash
$ sudo chown -R root:root $PREFIX
$ sudo chown $LOGNAME $PREFIX/cache         # i.e. any non-apache, non-root account
```

## Configure Apache

Apache configurations vary widely by Linux distribution and personal taste.
The following procedure is provided as an example and has been tested on
CentOS 7.

First determine which directory on your server maps to an Apache HTTPS CGI
directory.  To do this inspect `/etc/httpd/conf/httpd.conf` (or similar).
The default is `/var/www/cgi-bin`.  To provide better URLs for your site add
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
inside the `/etc/httpd/conf.d/ssl.conf` file.  We're editing the *ssl.conf*
instead of httpd.conf because das2 clients may transmit passwords. 


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

By default, authorization headers are not made available to CGI scripts.
The re-write rule above allows the `Authorization` header to be passed down
to the `das2_srvcgi_main` script.  This is needed to allow your server to
support password protected datasets.

Now symlink the top level CGI scripts into your new CGI directory.  Choose
the name of the symlink carefully as it will be part of the public URL for
your site:

```bash
$ cd /var/www/cgi-das
$ sudo ln -s $PREFIX/bin/das2_srvcgi_main server
$ sudo ln -s $PREFIX/bin/das2_srvcgi_logrdr log
```

Set the permissions of the log directory so that Apache can write logging
information:

```bash
$ chmod 0777 $PREFIX/log   # Or change the directory ownership
```

Finally, trigger a re-read of the Apache's configuration data:

```bash
$ sudo systemctl restart httpd.service
$ sudo systemctl status httpd.service
```

## Test the server

Test the server by pointing your web browser at:

```
https://localhost/das/server
https://localhost/das/log
```
If this works, try browsing your new server with Autoplot.  To do so, copy the
following URI into the Autoplot address bar and hit the green "Go" button:

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

**Das2-pyserver** is a caching and web-transport layer for das2 readers.  Readers
are the programs that generate the initial full resolution data streams.  The
entire purpose of das2-pyserver and das2 clients is to leverage the output of
your reader programs to produce efficient, interactive science data displays.
Example readers are included in the `$PREFIX/examples` directory to assist you
with the task of creating readers for your own data.  These examples happen to
be written in python, however there is no requirement to use python for your
programs, in fact much more efficent compiled languages such as Java,
[D](https://dlang.org/) and C++ are more suitable for the task.  Any language
may be used so long as:

  1) all data are written to standard output
  2) all error messages are written to standard error

For further information on your das2-pyserver instance, including:

  * reader programs
  * authentication 
  * request caching
  * automatic [HAPI](https://github.com/hapi-server/data-specification) conversion
  * [federated catalog](https://das2.org/browse) integration
  * [EPN-TAP](http://www.europlanet-vespa.eu/standards.shtml) integration
  
consult the users guide document  `das2_pyserver_ug.pdf` included in the docs
directory of the repository.

## Examples License

All code in the examples directory (not including the temporary pycdf subdirectory)
is release under the UNLICENSE and may be used without restrictions of any kind.
