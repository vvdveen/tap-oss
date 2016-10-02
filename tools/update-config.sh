#!/bin/bash

# Get our local directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CFG=$DIR/../config.sh

rm -f $CFG

# Location of new android SDK
SDK=$(dirname $(dirname $(which android)))
echo "SDK=$SDK/"> $CFG

# Location of Android Source
locate buildspec.mk.default | while IFS= read -r line 
do 
    echo "AOSP=$(dirname $(dirname $line))/" >> $CFG
    break
done

# Location of Androguard
ANDROGUARD=$(dirname $(which androlyze.py))
echo "ANDROGUARD=$ANDROGUARD/" >> $CFG

echo 'Generated config.sh. Make sure to double check this file if you have'
echo 'multiple android source trunks or SDKs installed'



