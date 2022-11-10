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

$PREFIX/bin/dasflex_sdef -i \
  $PREFIX/examples/random/source.dsdf $PREFIX/examples/waveform/source.dsdf \
  $PREFIX/examples/spectra/source.dsdf $PREFIX/examples/params/source.dsdf \
  $PREFIX/examples/auth/source.dsdf $PREFIX/examples/_dirinfo_.dsdf
