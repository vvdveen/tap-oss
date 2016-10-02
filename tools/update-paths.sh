#!/bin/bash

# Get the root dir of our platform
ROOTDIR="$(dirname $( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd ))"
source $ROOTDIR/config.sh

SDK_TOOLS="${SDK%/}/tools"
SDK_PTOOLS="${SDK%/}/platform-tools"
ANDROGUARD="${ANDROGUARD%/}"

# Library directory
LIB=$ROOTDIR/src/lib/

echo "Consider adding the following lines to your .bashrc or .profile, followed by 'export PATH':"

echo $PATH | grep -q "$SDK_TOOLS"
if [ $? -ne 0 ] ; then echo "PATH=\$PATH:$SDK_TOOLS" ; PATH=$PATH:$SDK_TOOLS ; fi

echo $PATH | grep -q "$SDK_PTOOLS"
if [ $? -ne 0 ] ; then echo "PATH=\$PATH:$SDK_PTOOLS"; PATH=$PATH:$SDK_PTOOLS; fi

echo $PATH | grep -q "$ANDROGUARD"
if [ $? -ne 0 ] ; then echo "PATH=\$PATH:$ANDROGUARD"; PATH=$PATH:$ANDROGUARD; fi

echo ""
echo "Consider adding the following lines to your .bashrc or .profile, followed by 'export PYTHONPATH':"

echo $PYTHONPATH | grep -q "$ANDROGUARD"
if [ $? -ne 0 ] ; then echo "PYTHONPATH=\$PYTHONPATH:$ANDROGUARD"; PYTHONPATH=$PYTHONPATH:$ANDROGUARD ; fi

echo $PYTHONPATH | grep -q "$LIB"
if [ $? -ne 0 ] ; then echo "PYTHONPATH=\$PYTHONPATH:$LIB";        PYTHONPATH=$PYTHONPATH:$LIB ; fi

echo $PYTHONPATH

export PATH
export PYTHONPATH

echo ""
echo "Paths included for this session."

