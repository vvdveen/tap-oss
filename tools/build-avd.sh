#!/bin/bash

#
# Make sure to update <android-sdk>/platforms/android-10/skins/WVGA800/hardware.ini:
# ...
# vm.heapSize=64
# hw.ramSize=1024
#

# Get our local directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# System image
SYSTEM_TARGET=$DIR/../lib/images/system.gapps_array_unpacking.img

# Target AVD name. Leave as is for use with emudroid
AVD=android.2.3.3

######################################################################################

# Create a new AVD
android create avd --target android-10 --abi armeabi --name $AVD --sdcard 256M --force

# Start the emulator with the system image
emulator -avd $AVD -system $SYSTEM_TARGET -no-window & 
pid=$!
output=''; while [[ "$output" != *package* ]]; do sleep 5; output=$(adb shell pm path android); done
sleep 30 

# Start the browser to make sure everything is working
adb shell am start -a android.intent.action.VIEW -n com.android.browser/.BrowserActivity -d about:blank
sleep 5

# Kill the emulator
kill $pid
sleep 5

# Move the AVD to a .backup so it can be used by emudroid
rm ~/.android/avd/$AVD.avd.backup -Rf
rm ~/.android/avd/$AVD.ini.backup -Rf
mv ~/.android/avd/$AVD.avd ~/.android/avd/$AVD.avd.backup
mv ~/.android/avd/$AVD.ini ~/.android/avd/$AVD.ini.backup

