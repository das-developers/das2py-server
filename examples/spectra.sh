#!/usr/bin/env bash

##############################################################################
function prnHelp {
	echo "$1 - Generate power spectral density values from waveform.py" 1>&2
	echo " "  1>&2
	echo "Usage: $1 EXAMPLE_DIR BEGIN END [LENGTH] [SLIDE]"  1>&2
	echo "       $1 [-h | --help]"  1>&2
	echo "       $1 [-v | --version]"  1>&2
	echo " "  1>&2
	echo "Output power spectral density by essentially running the pipeline" 1>&2
	echo " "  1>&2
	echo "   waveform.py EXAMPLE_DIR BEG END | das2_psd LEN SLIDE" 1>&2
	echo " " 1>&2
	echo "The last three arguments may be in any order.  The first integer" 1>&2
	echo "argument is taken to the be fourier transform length, by default" 1>&2
	echo "800 points are transformed at a time.  The second integer argument " 1>&2
	echo "is the denominator of the fraction of the length to slide over " 1>&2
	echo "between subsequent transforms.  The default is 2, for a slide " 1>&2
	echo "fraction of 1/2." 1>&2
	echo " " 1>&2
	return 0
}

##############################################################################
function main {

	typeset sExDir=""
	typeset nLen="0"
	typeset nDenom="0"
	
	for sArg in "$@"; do 
		if [ "$sArg" = "-h" -o "$sArg" = "--help" ] ; then
			prnHelp $(basename $0)
			return 0
		fi
		if [ "$sArg" = "-v" -o "$sArg" = "--version" ] ; then
			echo 'SVN Info: $Id$'
			echo 'SVN URL: $URL$'
			return 0
		fi
	done
	
	if [[ "$#" < "2" ]] ; then
		echo "Usage: " $(basename $0) " EXAMPLE_DIR BEGIN END [LENGTH] [SLIDE]"  1>&2
		echo "        or use -h for help" 1>&2
		return 13
	fi
	
	sExDir="$1"
	sBeg="$2"
	sEnd="$3"
	
	#Treat last argument as just a string pile
	
	for sArg in $(echo ${@:4}); do 		
		
		if [[ ${sArg} =~ ^[0-9]+$ ]] ; then
		
			if [ "$nLen" = "0" ] ; then
				nLen=$sArg
				continue
			else
				if [ "$nDenom" = "0" ] ; then
					nDenom=$sArg
					continue
				fi
			fi
		else
			if [ "$sExDir" = "" ] ; then
				sExDir=$sArg
				continue
			fi
		fi
		
		echo "Unknown command line parameter: $sArg" 1>&2
		return 13
	done
	
	if [ "$nLen" = "0" ] ; then
		nLen=1584
	fi
	if [ "$nDenom" = "0" ] ; then
		nDenom=2
	fi
	
	echo "exec: ${sExDir}/waveform.py $sExDir $sBeg $sEnd | das2_psd -c 2s $nLen $nDenom " 1>&2
	${sExDir}/waveform.py $sExDir $sBeg $sEnd | das2_psd -c 2s $nLen $nDenom
	return $?
}

##############################################################################
# Kicker Stub

main "$@"
nRet=$?
exit $nRet

