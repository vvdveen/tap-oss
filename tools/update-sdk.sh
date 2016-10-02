#!/bin/bash

# Get our local directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Include config.sh to get SDK path
source $DIR/../config.sh

# Location of updated hardware.ini
HARDWARE=$DIR/../lib/android/hardware.ini


# Test if the SDK is installed properly
output=$(android -h 2>/dev/null)
if [ -z "$output" ]; then 
    echo "Android SDK not found."
    exit
fi

diff=$(diff $SDK/platforms/android-10/skins/WVGA800/hardware.ini $HARDWARE)
if [ -n "$diff" ]; then
    read -e -p "Update hardware.ini [Y/n]? " yn
    case $yn in
        [Nn]* ) exit;;
    esac
fi
cp $HARDWARE $SDK/platforms/android-10/skins/WVGA800/hardware.ini

echo "Android SDK was updated"
    
