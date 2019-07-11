BUILD_SERVER_PROGS=$(patsubst %, $(SERVER_BUILD)/%, $(SERVER_PROGS) $(CGI_PROGS))
BUILD_GEN_PROGS=$(patsubst %, $(BUILD_DIR)/%, $(GEN_PROGS))

INSTALL_SERVER_PROGS=$(patsubst %, $(SERVER_BIN)/%, $(SERVER_PROGS) $(CGI_PROGS))
INSTALL_GEN_PROGS=$(patsubst %, $(INST_NAT_BIN)/%, $(GEN_PROGS))

BUILD_ETC=$(patsubst %.in, $(SERVER_BUILD)/%.example, $(CONFS))
INSTALL_ETC=$(patsubst %.in, $(SERVER_ETC)/%.example, $(CONFS)) 

INSTALL_RES=$(patsubst %, $(SERVER_RES)/%, $(RESOURCES))

# Example data sources
EX_DSDFS=_dirinfo_.dsdf Random.dsdf Waveform.dsdf Spectra.dsdf
INSTALL_EX_DSDFS=$(patsubst %.dsdf, $(SERVER_DATA)/Examples/%.dsdf, $(EX_DSDFS))

# Compiler Setup ############################################################

# Locale is placed here so that it is easy to change.  The software assumes
# UTF-8 internally, so if your system locale is not a UTF-8 setting, uncomment
# and change the following line. 
#  For example, on Windows use:
#DLOCALE=-DLOCALE=english_us.65001

CC=gcc
CFLAGS=-Wall -ggdb -std=c99 -I$(INST_INC) $(DLOCALE)
#CFLAGS=-Wall -O2 -std=c99 -I$(INST_INC) $(DLOCALE)
# Make sure we use static libs since we're GNU source anyawy
LFLAGS= $(INST_NAT_LIB)/libdas2.3.a -L$(INST_NAT_LIB) -lfftw3 -lssl -lcrypto -lexpat -lz -lm -lpthread

# Pattern Rules #############################################################

.SUFFIXES:
.SUFFIXES: .c .o .h .py
	
# Pattern rule for making programs from single source files
$(SERVER_BUILD)/%:src/%.c
	$(CC) $(CFLAGS) $< -o $@ $(LFLAGS)
	
$(BUILD_DIR)/%:src/%.c
	$(CC) $(CFLAGS) $< -o $@ $(LFLAGS)

# Pattern rule for make programs from single script files
$(SERVER_BUILD)/%:scripts/%.in
	./addconf.py $< $@	
	
# Pattern rule for subbing in values in config files
$(SERVER_BUILD)/%.example:etc/%.in
	./envsubst.py $< $@

# Pattern Rule for installing general programs
$(INST_NAT_BIN)/%:$(BUILD_DIR)/%
	install -D -m 775 $< $@

# Pattern Rule for installing site specific programs
$(SERVER_BIN)/%:$(SERVER_BUILD)/%
	install -D -m 775 $< $@
	
# Pattern Rule for installing static web files
$(SERVER_RES)/%:resources/%
	@if [ ! -e $@ ] ; then install -D -m 664 $< $@ ; else install -D -m 664 $< $@.new ; fi
	
# Pattern Rule for intstalling configuration files
$(SERVER_ETC)/%:$(SERVER_BUILD)/%
	install -D -m 664 $< $@


# Pattern Rule for building example DSDF files
$(SERVER_BUILD)/%.dsdf:examples/%.dsdf.in
	./envsubst.py $< $@

# Pattern Rule for installing example DSDF files with substitutions
$(SERVER_DATA)/Examples/%.dsdf:$(SERVER_BUILD)/%.dsdf
	install -D -m 664 $< $@

# Pattern rule for installing example DSDF files without substitutions
$(SERVER_DATA)/Examples/%.dsdf:examples/%.dsdf 
	install -D -m 664 $< $@ 

	
# EXPLICIT RULES #############################################################

#show:
#	@echo $(INSTALL_ETC)
#	@echo $(BUILD_DIR)
#	@echo $(BUILD_CGI)
#	@echo $(INSTALL_CGI)
#	@echo $(INSTALL_XLS)


build:check_env $(BUILD_DIR) $(SERVER_BUILD) $(BUILD_GEN_PROGS) \
 $(BUILD_SERVER_PROGS) $(BUILD_ETC) build_pylib
  

check_env:
	@if [ "" = "$(SERVER_ID)" ]; then echo "Define SERVER_ID= before building"; exit 13; fi

$(BUILD_DIR):
	@if [ ! -e "$(BUILD_DIR)" ]; then mkdir $(BUILD_DIR); fi

$(SERVER_BUILD):
	@if [ ! -e "$(SERVER_BUILD)" ]; then mkdir $(SERVER_BUILD); fi
	
build_pylib:
	python$(PYVER) setup.py build -b $(BUILD_DIR)

install:check_env $(INSTALL_SERVER_PROGS) $(INSTALL_GEN_PROGS) $(INSTALL_ETC) \
  $(INSTALL_RES) install_pylib
  
	if [ ! -e $(SERVER_DATA) ]; then mkdir -p $(SERVER_DATA); fi
	if [ ! -e $(SERVER_CACHE) ]; then mkdir -p $(SERVER_CACHE); fi

install_pylib:
	python$(PYVER) setup.py install_lib --skip-build -b $(BUILD_DIR)/lib* -d $(INST_HOST_LIB)


# Install the autoplot image creator adaptor
apimg: $(BUILD_DIR)/autoplot_url2png.py

$(BUILD_DIR)/autoplot_url2png.py:scripts/autoplot_url2png.py.in	
	env INST_HOST_BIN=${PREFIX}/bin/java`javac platver.java && java -cp . platver 2>/dev/null` ./envsubst.py $< $@

install_apimg:$(INST_NAT_BIN)/autoplot_url2png.py.example

$(INST_NAT_BIN)/autoplot_url2png.py.example:$(BUILD_DIR)/autoplot_url2png.py
	install -D -m 775 $< $@

# Build and install the example data sources
examples:$(INSTALL_EX_DSDFS)
  
distclean: check_env 
	rm -r $(BUILD_DIR) $(SERVER_BUILD)

clean: check_env
	rm -r $(BUILD_DIR) $(SERVER_BUILD)
