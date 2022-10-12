#!/usr/bin/env bash

# Define or re-define example datasources.  Run this *after* your define:
#
#   SERVER_URL
#
# and optionally:
#
#   WEBSOCKET_URI
#
# Re-run it if you change the variables above

THIS_FILE=$(realpath -s "${BASH_SOURCE[0]}")
PREFIX=$(dirname "$THIS_FILE")
PREFIX=$(dirname "$PREFIX")

$PREFIX/bin/das_srv_sdef -i random/source.dsdf
$PREFIX/bin/das_srv_sdef -i waveform/source.dsdf
$PREFIX/bin/das_srv_sdef -i spectra/source.dsdf
$PREFIX/bin/das_srv_sdef -i params/source.dsdf
$PREFIX/bin/das_srv_sdef -i auth/source.dsdf
#$PREFIX/bin/das_srv_cdef catinfo.dsdf



