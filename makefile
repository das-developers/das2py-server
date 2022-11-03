# Just pushes commands down to setup.py

ifeq ($(PREFIX),)
	PREFIX:=/var/www/dasflex
endif

ifeq ($(N_ARCH),)  # Default to no sub-dir for architecture dependent files
	N_ARCH:=/   
endif

ifeq ($(PYVER),)
	PYVER=$(shell python3 -c "import sys; print('.'.join( sys.version.split()[0].split('.')[:2] ))")
endif

export PREFIX
export PYVER

build:
	python${PYVER} setup.py build

install:
	python${PYVER} setup.py install --prefix=${PREFIX} \
	   --install-lib=${PREFIX}/lib/python${PYVER}

#python${PYVER} setup.py install --prefix=${PREFIX} \
#   --install-lib=${PREFIX}/lib/python${PYVER} --no-examples


distclean:
	rm -r build
