#!/bin/bash

# Get our local directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Include config.ini to get AOSP path
source $DIR/../config.sh

# Location of the Google Maps API files
MAPS_XML=$DIR/../lib/android/com.google.android.maps.xml
MAPS_JAR=$DIR/../lib/android/com.google.android.maps.jar

# Location of the new SU binary
SU=$DIR/../lib/apps/android_system_su/su

# mkfs.yaffs2.arm must be in here
MKFS_DIR=$DIR/

# Target system image file
SYSTEM_TARGET=$DIR/../lib/images/system.gapps_array_unpacking.img

# Target AVD name. 
AVD=android.2.3.3

######################################################################################

# Create a new AVD
android create avd --target android-10 --abi armeabi --name $AVD --sdcard 256M --force

# Start the AVD with the latest compiled system image and wait for it to become ready
emulator -avd $AVD -system $AOSP/out/target/product/generic/system.img &
pid=$!
output=''; while [[ "$output" != *package* ]]; do sleep 5; output=$(adb shell pm path android); done
sleep 30

# Push the Google Maps API to the system
adb shell mount -o rw,remount /system /system
adb push $MAPS_XML /system/etc/permissions
adb push $MAPS_JAR /system/framework
adb shell mount -o ro,remount /system /system

# Push the SU binary to the system
adb shell mount -o rw,remount /system /system
adb push $SU /system/xbin/su
adb shell chmod 6755 /system/xbin/su
adb shell mount -o ro,remount /system /system

# Build a new system image
adb push $MKFS_DIR/mkfs.yaffs2.arm /data
adb shell chmod 777 /data/mkfs.yaffs2.arm
adb shell /data/mkfs.yaffs2.arm /system /data/system.img
adb pull /data/system.img $SYSTEM_TARGET

# Kill the emulator
kill $pid

sleep 2

# Remove the AVD
rm ~/.android/avd/$AVD.avd -Rf
rm ~/.android/avd/$AVD.ini -Rf

