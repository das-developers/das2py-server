#!/usr/bin/env python
from distutils.core import setup

lPkg = ['das2server','das2server.util','das2server.defhandlers', 
        'das2server.deftasks', 'das2server.h_api']

lScripts = []

setup(
   name="das2server",
	version="2.2",
	description="Das2 pyserver - das2 stream caching middleware",
	author="Chris Piker",
	packages=lPkg,
	scripts=lScripts
)
