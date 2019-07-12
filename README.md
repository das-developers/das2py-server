# das2-pyserver

Das2 servers typically provide data relevant to space plasma and magnetospheric
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

## Dependencies

Compilation and installation of das2-pyserver currently requires a Linux
environment.  That can change -- it's just not been tested.  Here are the build and
test steps.  In the instructions below the '$' character is used at the
beginning of a line to indicate commands to run in a shell.

1. Python 2.7, or Python >= 3.4

2. Apache2, any remotely recent version configured with at least one CGI
   directory

3. [Redis](https://redis.io), known to work with version 3.2.12, will
   likely work with older versions as well.
	
4. python-redis, the python bindings for Redis.

5. [libdas2](https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3), 
   both the base C tools and Python bindings must be built.  In the future
	libdas2 will be split into **das2c** and **das2py** and moved to
	github, for now you'll have to consult the libdas2 [INSTALL.txt](https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3/INSTALL.txt) 
	file and build from SVN sources.

Since libdas2 provides small binaries needed by das2 pyserver, and since there
are no pre-built libdas2.3 packages, installing instructions for both sets of
software are included below.

For convienience, dependent package installation commands for das2-pyserver
and libdas2.3 are provided below for CentOS 7:
```bash
$ yum install gcc subversion git                     # for source downloads
$ yum install expat-devel fftw-devel openssl-devel   # needed to build libdas2.3
$ yum install python3 python3-numpy python3-devel    # needed to bulid das2py
$ yum install --enablerepo=epel install redis        # needed by pyserver
$ yum install --enablerepo=epel install hiredis      # needed by pyserver
$ yum install --enablerepo=epel install python-redis # needed by pyserver
```
and Debian 9.1:
```bash
$ apt-get install gcc subversion git                     # for source downloads
$ apt-get install libexpat-dev libfftw3-dev libssl-dev   # needed to bulid libdas2.3
$ apt-get install python3-dev python3-distutils python3-numpy  # to build das2py
$ apt-get install redis-server                           # needed by pyserver
$ apt-get install python-hiredis                         # needed by pyserver
```

## Getting the sources

<<<<<<< HEAD
For now some of the sources are in SVN and some in git repositories, this 
well change as time permits.
```bash
$ svn co https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3
$ git clone https://github.com/das-developers/das2-pyserver.git
=======
For now some of the sources are in SVN and some in git repositories.  This 
will change as time permits.
```
svn co https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3
git clone https://github.com/das-developers/das2-pyserver.git
>>>>>>> ec24dfd0f7be4a9470a4cc8ea214086e728ddce9
```

## Building libdas2.3, and das2py
Decide where your das2 server code and configuration will live, in the example
below I chose `/usr/local/das2srv` but you can select any location you like.
```bash
$ export PREFIX=/usr/local/das2srv   # Adjust to taste
$ export PYVER=3.6                   # or 2.7, or 3.7 etc.
```

Test your `PYVER` setting by making sure the following command brings up a
python interpreter
```bash
$ python$PYVER
```




### Building das2-pyserver


The absolute path to the top-level configuration file, `das2server.conf` is
written into the top-level CGI scripts by the make commands.  To determine
where this will be installed setup the following environment varible:
```
$ export SERVER_ROOT=/root/server/data/location
```




```
$ git clone git@github.com:das-developers/das2-pyserver.git  das2-pyserver
$ cd das2-pyserver
$ 
```
[working...]



Test
----
[working...]


Server-Reader Interface
-----------------------
[working...]







