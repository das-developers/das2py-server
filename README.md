# das2-pyserver

Das2 servers typically provide data relavent to space plasma and magnetospheric
physics research.  To retrieve data, an HTTP GET request is posted to a das2 
server by a client program and a self-describing stream of data values covering
the requested time range, at the requested time resolution, is provided in the
response body.  This software provides a caching middleware layer between 
server-side das2 readers, which stream data at full resolution to standard out, and
remote client programs such as [Autoplot](https://autoplot.org) or custom
programs written in Python ([das2py](https://anaconda.org/DasDevelopers/das2py))
or IDL ([das2pro](https://github.com/das-developers/das2pro) ).

*das2-pyserver* consists of python scripts that run external programs, called
readers, which provide the full resolution data streams.  Being external
programs, readers may be written in **any** desired programming language and
have **any** desired software license.  When a request for data received,
das2-pyserver inspects the HTTP GET URL and checks to see if it's local cache
contains the required data, at the desired time resolution, or better.  If 
the request as already cached, an HTTP request body is generated from cache
blocks,  If not, the associated reader program and data reducer are invoked on
the server and the standard output stream from this pipeline is delivered as 
the request body.

## Dependencies

Compilation and installation of das2-pyserver currently requires a linux
environment.  That can change, it's just not been tested.  Here's the build and
test steps.  In the instructions below the '$' character is used at the
beginning of a line to indicate commands to run in a shell.

1. Python 2.7, or Python >= 3.4

2. Apache2, any remotely recent version configured with at least one CGI
   directory

3. [Redis](https://redis.io), known to work with version 3.2.12, will
   like work with older versions as well.
	
4. python-redis, the python bindings for Redis.

5. [libdas2](https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3), 
   both the base C tools and Python bindings must be built.  In the future
	libdas2 will be split into **das2c** and **das2py** and moved to
	github, for now you'll have to consult the included [INSTALL.txt](https://saturn.physics.uiowa.edu/svn/das2/core/stable/libdas2_3/INSTALL.txt) 
	file and build from SVN sources.
	
For convienience dependency package install command are provided below for
CentOS 7:
```
yum install python-devel
yum install --enablerepo=epel install redis
yum install --enablerepo=epel install hiredis
yum install --enablerepo=epel install python-redis
```
and Debian 9.1:
```
apt-get install python-dev
apt-get install redis-server
apt-get install python-hiredis
```

## Building

The absolute path to the top-level configuration file, `das2server.conf` is
written into the top-level CGI scripts by the make commands.  To determine
where these are installed setup the following environment varibles:
```
$ export PREFIX=/root/server/code/location
$ export N_ARCH=/
$ export SERVER_ID=one-word-server-name
$ export SERVER_ROOT=/root/server/data/location
```

```
$ git clone git@github.com:das-developers/das2-pyserver.git  das2-pyserver
$ cd das2-pyserver
$ 


Test
----
[add]


Server-Reader Interface
-----------------------
[add]






