##############################################################################
# Generic definitions for: Server specific programs + hosted python

ifeq ($(PREFIX),)
ifeq ($(HOME),)
PREFIX=$(USERPROFILE)
else
PREFIX=$(HOME)
endif
endif

ifeq ($(SERVER_ROOT),)
SERVER_ROOT=$(PREFIX)/servers/$(SERVER_ID)
endif

ifeq ($(SERVER_DATA),)
SERVER_DATA=$(SERVER_ROOT)/datasets
endif

ifeq ($(SERVER_CACHE),)
SERVER_CACHE=$(SERVER_ROOT)/cache
endif


ifeq ($(SERVER_ETC),)
SERVER_ETC=$(SERVER_ROOT)/etc
endif

ifeq ($(SERVER_RES),)
SERVER_RES=$(SERVER_ROOT)/resources
endif

ifeq ($(SERVER_BIN),)
SERVER_BIN=$(SERVER_ROOT)/bin
endif

ifeq ($(H_ARCH),)
ifeq ($(PYVER),)
PYVER=$(shell python -c "import sys; print '.'.join( sys.version.split()[0].split('.')[:2] )")
endif
H_ARCH=python$(PYVER)
endif

# These aren't needed by the das2 server itself, but help to provide 
# suggestions for the example configuration file.
ifeq ($(N_ARCH),)
N_ARCH=$(shell uname -s).$(shell uname -p)
endif

ifeq ($(INST_INC),)
INST_INC=$(PREFIX)/include/$(N_ARCH)
endif

# This python module is not site specific and goes in a generic place
ifeq ($(INST_HOST_LIB),)
INST_HOST_LIB=$(PREFIX)/lib/$(H_ARCH)
endif

ifeq ($(INST_EXT_LIB),)
INST_EXT_LIB=$(PREFIX)/lib/$(N_ARCH)/$(H_ARCH)
endif

ifeq ($(INST_NAT_BIN),)
INST_NAT_BIN=$(PREFIX)/bin/$(N_ARCH)
endif

ifeq ($(INST_NAT_LIB),)
INST_NAT_LIB=$(PREFIX)/lib/$(N_ARCH)
endif


# export vars so they can be included in the example config
export SERVER_ETC
export SERVER_DATA
export SERVER_CACHE
export SERVER_RES
export SERVER_BIN

export INST_NAT_LIB
export INST_HOST_LIB
export INST_EXT_LIB
export INST_NAT_BIN

SERVER_BUILD:=build.$(SERVER_ID)
BUILD_DIR:=build.$(N_ARCH)

# Source Definitions #########################################################

# On linux both sets of server customized programs install into the same place
# location and symlinks are used to make the CGI programs appear the CGI dir
# Not sure if this strategy will work on Windows so the program types are 
# tracked separately
SERVER_PROGS=das2_srv_passwd das2_srv_arbiter das2_srv_todo  das2_srv_dsdf2json
CGI_PROGS=das2_srvcgi_logrdr das2_srvcgi_main 
GEN_PROGS=das2_cache_rdr


RESOURCES=das2server.xsl das2server.css magnetosphere.jpg \
 das2logo.png das2logo_rv.png
CONFS=das2server.conf.in das2peers.ini.in

##############################################################################
# Explicit Rules

UNAME = $(shell uname)

include $(UNAME).mak

