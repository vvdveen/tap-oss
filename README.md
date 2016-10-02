daap-platform
=============

Requirements
------------

- Androguard-1.9: http://code.google.com/p/androguard/
- Android SDK: http://developer.android.com/sdk/index.html
- Android 2.3.3 (API 10) using the Android SDK manager

Installation
------------

    # Generate a config.sh file containing paths to the Android SDK, Androguard
    # and AOSP (if any)
    ./tools/update-config.sh

    # Update the Androguard 1.9 source files
    ./tools/update-androguard.sh

    # Update the Android SDK (add a modified hardware.ini)
    ./tools/update-sdk.sh

    # Setup PATH and PYTHONPATH
    source ./tools/update-paths.sh

    # Generate a new Android Virtual Device (AVD). Hit no if asked if you want
    # to create a custom hardware profile.
    ./tools/build-avd.sh


Instructions
------------
Executables are stored in the ./src/ directory.

You can se the platform to analyze a Android APK file. The platform is
implemented by analyze.py which is responsible for running the necessary static
analysis steps, followed by running the dynamic analysis. Post-analysis plugins
found in the post-analysis/ directory are after dynamic analysis finished.

    cd src
    ./analyze --input INPUT

optional arguments:
  --output OUTPUT  Parent directory for the log directory (default is current directory)
  --nowindow       Hide the emulator window
  --breakdown      Compute code coverage per simulation technique
  --manual         Run manual analysis

When analysis is completed, you can have a look at the output files in the log
directory called INPUT.TIMESTAMP:

- analysis.log              Logfile of the main analysis program.

- static.log                Static analysis output.

- logcat.log                Logcat output   (as captured during analysis).

- traffic.pcap              Network traffic (as captured during analysis).

- features.log              List of features (may be used by a machine learning
                            algorithm to identify malicious behavior).

- coverage.TIMESTAMP.log    Logfile of the code coverage computation script.

- dump.PID.TID              Trace file for Process/Thread with process-id PID
                            and thread-id TID
 
There are currently three post-analysis scripts installed:
- code coverage
    This script computes the code coverage that was obtained during dynamic
    analysis. It outputs both a conservative and a naive estimate. The main
    difference between the two is that for naive code coverage, popular API classes
    are included in the search space, so that calls to AdMob.x for example are not
    take into consideration.
- features
    This script parses the trace files and generates a list of features that may
    indicate malicious behavior. These features may be used by a machine learning
    algorithm to learn about malicious apps.
- database
    This scripts pushes all the information found during analysis into a sqlite3
    database.
You can run the post-analysis scripts also as stand-alone programs by using the
symbolic links in the ./src/ directory:
- ./get-coverage.py
- ./put-database.py
- ./get-features.py

You can also run static analysis on a Android package by using the ./static.py
symbolic link.

If you'd like to analyse the trace output in more detail, you can use the
./trace.py symbolic link.








Optional: compile your own TraceDroid image
-------------------------------------------

If you have the Android sources installed, you can download the TraceDroid
sources and compile your own system image. The TraceDroid sources are based on
Android 2.3.4, so you'll have to switch to this branch. Assuming the Android
source is in /android-source:
    
    cd /android-source
    repo init -u https://android.googlesource.com/platform/manifest -b android-2.3.4_r1
    repo sync

    # Make sure that you are able to build the Android sources:
    . build/envsetup
    make

    # Branch into TraceDroid:
    cd dalvik
    git remote add tracedroid git@github.com:vvdveen/daap-dalvik.git
    git fetch tracedroid
    git checkout tracedroid/trace
    cd ..

    cd frameworks/base/
    git remote add tracedroid git@github.com:vvdveen/daap-frameworks-base.git
    git fetch tracedroid
    git checkout tracedroid/trace
    cd ../..

    # Build the TraceDroid system image:
    make

You can now use the build-avd-gapps.sh script to build a TraceDroid system
image with the Google Maps API and a modified SU binary:

    # Hit no if asked if you want to create a custom hardware profile.
    ./tools/build-avd-gapps.sh
 
