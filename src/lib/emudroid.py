#!/usr/bin/python

import subprocess
import os
import time
import logging
import re
import socket
import tempfile
import shutil
import signal
import random

#
# This class assumes that AVDs (Android Virtual Devices) have been created
# before and are located in ~/.android/avd/ (this is the default directory for
# AVDs). Knowing that an AVD consists of one .ini configuration file and one
# according .avd directory containing the VM images, it assumes that these
# filenames are named:
# - android.<version>.avd.backup
# - android.<version>.ini.backup
# So for an AVD for version 2.3.1, the following files should be available:
# - ~/.android/avd/android.2.3.1.avd.backup/        (directory)
# - ~/.android/avd/android.2.3.1.ini.backup         (configuration)
#
# During initialization, the function fresh_copy() is called. This function
# will copy the requested version of the AVD to a temporary location.
#
#

# Emulator defaults:
MIN_PORT = 5000
MAX_PORT = 6000

BOOTWAITTIME_MAX = 180      # Emulator should be up and running within this number of seconds
BOOTWAITTIME     = 120      # Number of seconds to wait for boot completion if checks failed
EXECWAITTIME     = 120      # When executing an ADB command, it should be completed within this
                            # number of seconds. Some commands may take quite some time to
                            # finish. Pulling the strace log files for one of the samples, for
                            # example, took almost 90s to complete.

# Android Key Codes: http://source.android.com/tech/input/keyboard-devices.html
KEY_DIGIT  = 0x07  #  digit starting offset (0)
KEY_LETTER = 0x1d  # letter starting offset (a)
KEY_SPACE  = 0x3e  # spacebar
KEY_ENTER  = 0x42  # return key
KEY_HOME   = 0x03  # home-screen button
KEY_BACK   = 0x04  # back button
KEY_CALL   = 0x05  # call button
KEY_DOWN   = 0x14  # down button
KEY_RIGHT  = 0x16  # right button
KEY_CENTER = 0x17  # center button
KEY_MENU   = 0x52  # menu button

ROOTDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..')
DIR_APP = os.path.join(ROOTDIR, 'lib', 'apps')
DIR_IMG = os.path.join(ROOTDIR, 'lib', 'images')
DIR_AND = os.path.join(ROOTDIR, 'lib', 'android')

SCREENSHOT = os.path.join(DIR_APP, 'screenshot', 'screenshot.jar')


# Default Error class which we will extend.
class Error(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

# Errors thrown.
class EmulatorError(Error):
    pass

class emudroid:

    # Return two TCP ports that can be used to communicate with the emulator.
    def getPorts(self):
        while True:
            s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            port = random.randint(MIN_PORT, MAX_PORT)

            try:
                self.logger.debug("Trying port %d and %d" % (port,port+1))
                s1.bind(("localhost", port))
                s2.bind(("localhost", port+1))
                return port, port+1
            except socket.error as exception:
                if exception.strerror == "Address already in use":
                    continue
                raise exception
            finally:
                del s1
                del s2

    # Setup a TCP connection with the emulator.
    def tcp_connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect(("localhost", self.consoleport))
        self.socket.recv(1024)

    # Send a command via the TCP connection.
    def tcp_send(self,cmd):
        self.logger.debug("Sending command: " + cmd)
        self.socket.send(cmd + "\n")
        received = self.socket.recv(1024)
        self.logger.debug("Received: " + received.rstrip())
        return received

    def waitfor(self, cmd, result):
        while True:
            # Perform requested check.
            out, err = self.adb(cmd)
            if re.search(result, out):
                break
            time.sleep(1)

            # Check if emulator process has terminated. This should not happen.
            self.p.poll()
            if self.p.returncode != None:
                out, err = self.p.communicate()
                raise EmulatorError("emulator process terminated\nout: " + out + "\nerr: " + err)


    # Wait until the emulator is booted
    def completeboot(self):
        self.waitfor(["devices"], "emulator-" + str(self.consoleport) + "\s*device")
        self.waitfor(["shell", "getprop", "dev.bootcomplete"], "1")
        self.waitfor(["shell", "getprop", "sys.boot_completed"], "1")                       # not implemented on API level <= 8
        self.waitfor(["shell", "getprop", "init.svc.bootanim"], "stopped")
        self.waitfor(["shell", "pm", "path", "android"], "package")

    # Start logcat
    def log(self, filename):
        f = open(filename,"w")
        return subprocess.Popen(["adb", "-s", "emulator-" + str(self.consoleport), "logcat", "-v", "threadtime"], stdout = f, stderr = subprocess.PIPE), f

    # Make a screenshot
    def screenshot(self, outputfile):
        p = subprocess.Popen(["java", "-jar", SCREENSHOT, "-s", "emulator-" + str(self.consoleport), outputfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return p.communicate()


    def adb_handler(self, signum, frame):
        # Restore to default signal handler
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        raise EmulatorError("Could not execute adb command: timeout")

    # Execute an adb command
    def adb(self, args):
        cmd = ["adb", "-s", "emulator-" + str(self.consoleport)]
        cmd.extend(args)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        signalset = False
        # Install an alarm if there was no one installed yet.
        if signal.getsignal(signal.SIGALRM) == signal.SIG_DFL:
            signal.signal(signal.SIGALRM, self.adb_handler)
            signal.alarm(EXECWAITTIME)
            signalset = True

        # Try to communicate with the process...
        try:
            out, err = p.communicate()
            # Reset the alarm.
            if signalset:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, signal.SIG_DFL)

        # ...or, if a timeout occurred, kill the process:
        except EmulatorError:
            p.terminate()
            raise EmulatorError("Could not execute adb command " + str(cmd) + ": timeout")

        #print "cmd: %s\nout: %s\nerr: %s\n" % (cmd, out, err)
        return out, err



    # Execute an adb command using os.system(). This makes it easier to use
    # piped commando's.
    def adb_sys(self, args):
        cmd = "adb -s emulator-" + str(self.consoleport) + " " + args
        return os.system(cmd)


    # Install a google maps api.
    def install_maps_api(self):
        self.adb(["shell", "mount", "-o", "rw,remount", "/system", "/system"])
        self.adb(['push', os.path.join(DIR_AND, 'com.google.android.maps.xml'), '/system/etc/permissions'])
        self.adb(['push', os.path.join(DIR_AND, 'com.google.android.maps.jar'), '/system/framework'])
        self.adb(["shell", "mount", "-o", "ro,remount", "/system", "/system"])

    def install_su(self):
        self.adb(["shell", "mount", "-o", "rw,remount", "/system", "/system"])
        self.adb(["push",  os.path.join(DIR_APP, 'su-binary', 'su'), "/system/xbin/su"])
        self.adb(["shell", "chmod", "6755", "/system/xbin/su"])
        self.adb(["shell", "mount", "-o", "ro,remount", "/system", "/system"])

    # Kill a package.
    def kil(self, package):
        args = "shell ps | grep " + package + " | awk '{print $2}' | xargs adb -s emulator-" + str(self.consoleport) + " shell kill -9 > /dev/null"
        return self.adb_sys(args)

    # Start stracing zygote.
    def zyg(self, logfile):
        args = "shell ps | grep zygote | awk '{print $2}' | xargs adb -s emulator-" + str(self.consoleport) + " shell strace -ff -tt -s 100 -o " + logfile + " -p > /dev/null &"
        return self.adb_sys(args)

    # Pull trace files
    def pull_dump(self, logdir):
        args = "shell ls /sdcard/dump.* | tr --delete '\r' | xargs -I % -n1 adb -s emulator-" + str(self.consoleport) + " pull % " + logdir + " > /dev/null 2>&1"
        return self.adb_sys(args)

    # Remove trace files from sdcard
    def remv_dump(self):
        args = 'shell rm /sdcard/dump.* > /dev/null 2>&1'
        return self.adb_sys(args)



    def boot_completed(self, package):
        self.adb(["shell", "am", "broadcast", "-a", "android.intent.action.BOOT_COMPLETED"])

    def start_activity(self, package, activity, action = None):
        if action: self.adb(["shell", "am", "start", "-n", package + "/" + activity, "-a", action])
        else:      self.adb(["shell", "am", "start", "-n", package + "/" + activity])

    def start_main_activity(self, package, activity):
        self.start_activity(package, activity, 'android.intent.action.MAIN')

    def start_service(self, package, service):
        self.adb(["shell", "am", "startservice", "-n", package + "/" + service])

    def start_capturing(self, filename):
        self.adb(["emu", "network", "capture", "start", filename])

    def stop_capturing(self):
        self.adb(["emu", "network", "capture", "stop"])

    def start_monkey(self, filename = None, package = None, categories = None):

        cmd = ["adb", "-s", "emulator-" + str(self.consoleport)]
        cmd.extend(["shell", "monkey",
                    "-vvv",
                    "-s",               "1337",           # seed, so we always gain the same output
#                   "--throttle",       "10",             # slow down
                    "--pct-syskeys",    "0",              # percentage of system keys events
                    "--pct-anyevent",   "0",              # percentage of other types of events
                    "--ignore-crashes",
                    "--ignore-timeouts",
                    "--ignore-security-exceptions"])

        if package:                     cmd.extend(["-p", package])         # only target app
        if categories:
            for category in categories: cmd.extend(['-c', category])        # only these categories
        cmd.append("5000000")                                               # event count

        if filename:
            f = open(filename, 'w')
            return subprocess.Popen(cmd, stdout = f,               stderr = subprocess.PIPE), f
        else:
            return subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)

    def stop_monkey(self):
        self.kil('com.android.commands.monkey')

    def browse(self, url):
        self.adb(['shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-n', 'com.android.browser/.BrowserActivity', '-d', url])

    def set_android_id(self):
        self.adb(["shell", '''echo "insert into secure('name', 'value') values ('android_id', 'deadbeef4badcafe');" | sqlite3 /data/data/com.android.providers.settings/databases/settings.db'''])

    def press(self,key):
        self.adb(["shell", "input", "keyevent", str(key)])

    def get_installed_packages(self):
        out, err = self.adb(["shell", "cat", "/data/system/packages.list"])
        return out.strip().split('\r\n')


    # Find uid of package.
    def find_uid(self, package):
        out, err = self.adb(["shell", "cat", "/data/system/packages.list"])
        uid_group = re.search('^' + package + ' (\d+) ', out, re.MULTILINE)
        if not uid_group: return 0
        return uid_group.group(1)

    # Install a package
    def install(self, filename):
        # Try again a couple of times before giving up.
        for i in [1, 2, 3]:
            start = time.time()
            out, err = self.adb(["install", "-r", filename])
            if 'Success' in out: return (time.time() - start)

        if 'INSTALL_FAILED_MISSING_SHARED_LIBRARY' in out: raise EmulatorError("Missing shared library")
        if 'INSTALL_PARSE_FAILED_NOT_APK'          in out: raise EmulatorError("Not an APK file")
        if 'INSTALL_PARSE_FAILED_NO_CERTIFICATES'  in out: raise EmulatorError("No certificates")
        if 'INSTALL_FAILED_DEXOPT'                 in out: raise EmulatorError("Dexopt error")
        if 'is not a valid zip file'               in err: raise EmulatorError("Invalid package")
        if 'does not contain AndroidManifest.xml'  in err: raise EmulatorError("AndroidManifest.xml missing")

        raise EmulatorError("Unknown error: \nstdout: " + out + "\nstderr: " + err)

    def uninstall(self, package):
        out, err = self.adb(["uninstall", package])

    # start tracing a package
    def enable_trace(self, package):
        uid = self.find_uid(package)
        if uid == 0: raise EmulatorError("Could not find uid for package " + package)
        self.adb(["shell", "rm /sdcard/*"])
        self.adb(["shell", "echo " + str(uid) +  " > /sdcard/uid"])

    def disable_trace(self, package):
        args = "shell ps | grep " + package + " | awk '{print $2}' | xargs -I % adb -s emulator-" + str(self.consoleport) + " shell am profile % stop 1>/dev/null 2>&1"
        return self.adb_sys(args)

    def get_timing(self):
        host = int(time.time())
        out, err = self.adb(['shell', 'date +%s'])
        guest = int(out)

        return host - guest






# START #########################################################

    # Signal handler in case emulator did not start in time.
    def emu_handler(self, signum, frame):
        # Restore to default signal handler
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        self.stop()
        raise EmulatorError("Could not start emulator: timeout")

    def start(self):
        # Only start if we're not running yet.
        if self.running:
            self.logger.error("Emulator is already running")
            raise EmulatorError("Emulator is already running")

        # Create a fresh copy if it was somehow removed.
        if not self.copied:
            self.fresh_copy()

        self.logger.debug("Searching for two available TCP ports")
        try:
            self.consoleport, self.adbport = self.getPorts()
        except socket.error as exception:
            self.logger.error("Could not search for TCP ports: " + str(exception))
            raise EmulatorError("Could not search for TCP ports: " + str(exception))

        # Setup the emulator command and its arguments.
        cmd = [self.emulator, "-ports",    str(self.consoleport) + "," + str(self.adbport),
                              "-avd",      self.tmp_name,
                              "-system",   self.system,
                              "-no-audio"]

        if self.nowindow:   cmd.extend(["-no-window"])
        if self.scale:      cmd.extend(["-scale", "0.5"])
        if self.extra_opts: cmd.extend(["-prop", "dalvik.vm.extra-opts=" + self.extra_opts])
        if self.snapshot:   cmd.extend(["-snapshot", "clean", "-no-snapshot-save"])

        # If we're not up and running within X minutes, we should raise an EmulatorError.
        signal.signal(signal.SIGALRM, self.emu_handler)
        signal.alarm(BOOTWAITTIME_MAX)

        # Start the emulator by executing <cmd>. If this fails, raise an
        # EmulatorError.
        self.logger.debug("Starting the emulator with arguments: " + str(cmd))
        try:
            self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as exception:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
            self.logger.error("Could not start emulator: " + str(exception))
            raise EmulatorError("Could not start emulator: " + str(exception))

        # Wait for the emulator to becoming ready by performing some checks.
        # Wait for a fixed number of seconds if these checks fail.
        self.logger.debug("Waiting for the emulator to complete boot procedure")
        try:
            self.completeboot()
        except OSError as exception:
            self.logger.warning("Waiting for boot completion failed: " + str(exception))
            time.sleep(BOOTWAITTIME)

        # Setup a TCP connection with the emulator, so that we can send
        # commands to it. If this fails, we raise an EmulatorError and the
        # caller should try again.
        self.logger.debug("Connecting via TCP")
        try:
            self.tcp_connect()
        except socket.error as exception:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
            self.logger.error("Could not connect to emulator: " + str(exception))
            raise EmulatorError("Could not connect to emulator: " + str(exception))

        # Unlock the home screen. Raise an error if this fails, as we need to
        # be able to press some keys later on.
        self.logger.debug("Unlocking the home screen")
        try:
            self.press(KEY_MENU)
        except OSError as exception:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, signal.SIG_DFL)
            self.logger.error("Could not unlock home screen: " + str(exception))
            raise EmulatorError("Could not unlock home screen: " + str(exception))

        # We should be up and running now.
        self.running = True

        # Turn off the alarm and restore to default handler.
        signal.alarm(0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)


# TRY_START #####################################################
    def try_start(self):

        for i in [1, 2, 3]:
            try:
                self.start()
                return
            except EmulatorError as exception:
                self.logger.warning("Could not boot emulator: " + str(exception))

        raise EmulatorError("Could not boot emulator, reached max tries")

# STOP ##########################################################
    def stop(self):

        # Terminate our process, if any.
        if self.p:
            try:
                self.p.terminate()
                self.p.wait()
            except OSError as exception:
                # Do not raise an exception if there's no such process to kill.
                if exception.errno != 3: raise exception

            self.p = None

        # Close our TCP connection, if any.
        if self.socket:
            self.socket.close()
            self.socket = None

        # We are no longer running.
        self.running = False

# RESTART #######################################################
    def restart(self):
        self.stop()
        self.start()

# FRESH_COPY ####################################################
    def fresh_copy(self):
        if self.snapshot: return

        self.logger.debug("Generating a fresh copy...")

        # Create a temporary directory to store a working copy of the AVD.
        self.tmp_home = tempfile.mkdtemp()
        self.tmp_dir  = os.path.join(self.tmp_home, self.avd_name + '.avd')

        # Copy the original AVD to this temporary directory.
        shutil.copytree(self.avd_dir, self.tmp_dir)

        # Create a temporary .ini file for this AVD.
        tmpini, self.tmp_ini = tempfile.mkstemp(prefix = self.avd_name + ".", suffix = ".ini", dir = self.avd_home)
        tmpini = os.fdopen(tmpini,"w")
        self.tmp_name = os.path.splitext(os.path.basename(self.tmp_ini))[0]

        # Open the original .ini...
        orgini = open(self.avd_ini)

        # ...and copy its contents to the temporary .ini...
        for line in orgini:
            # ...but update path=... line so that it points to the temporary location
            tmpini.write(re.sub("path=.*", "path=" + self.tmp_dir, line))

        # Close both .ini files
        tmpini.close()
        orgini.close()

        self.copied = True

# DESTROY ########################################################
    def destroy(self):
        if self.snapshot: return

        self.logger.debug("Destroying copy")

        # Stop running.
        self.stop()

        # Remove the temporary directory (if any).
        shutil.rmtree(self.tmp_home,ignore_errors = True)

        # Remove the temporary .ini (if any).
        try:
            os.remove(self.tmp_ini)
        except OSError as exception:
            # Do not raise an exception if the file does not exist.
            if exception.errno != 2: raise exception

        self.running = False
        self.p       = None
        self.socket  = None
        self.copied  = False


# INIT ##########################################################

    # Return a generic logger in case none was provided.
    def getLogger(self):
        name = str(self)

        formatter     = logging.Formatter("%(message)s")
        consoleLogger = logging.StreamHandler()
        consoleLogger.setFormatter(formatter)

        logging.getLogger(name).addHandler(consoleLogger)
        logging.getLogger(name).setLevel(logging.DEBUG)

        return logging.getLogger(name)


    def __init__(self, logger = None, nowindow = False, scale = False, snapshot = False, extra_opts = ''):
        # Store the current working directory
        self.pwd = os.getcwd()

        if not logger: self.logger = self.getLogger()
        else:          self.logger = logger

        self.logger.debug("Initializing attributes...")

        self.avd_name     = "android.2.3.3"
        self.avd_home     = os.path.join(os.getenv("HOME"), '.android/avd/')
        self.avd_dir      = os.path.join(self.avd_home, self.avd_name + '.avd.backup')
        self.avd_ini      = os.path.join(self.avd_home, self.avd_name + '.ini.backup')
        self.tmp_name     = self.avd_name  # will become <avd_name>.<tmp>
        self.tmp_home     = None           # will become /tmp/<tmpdir>/
        self.tmp_dir      = None           # will become /tmp/<tmpdir>/<avd_dir>
        self.tmp_ini      = None           # will become <avd_home>/<tmp_name>.ini
        self.nowindow     = nowindow
        self.scale        = scale
        self.snapshot     = snapshot
        self.extra_opts   = ''
        self.emulator     = 'emulator'
        self.system       = os.path.join(DIR_IMG, 'system.gapps.img')
        self.system       = os.path.join(DIR_IMG, 'system.gapps_array_unpacking.img')

# if https://android.googlesource.com/platform/sdk/+/35425faccd6c6591c787f69dfb8e845720ca15ac%5E!/
# is applied, we'll need to use our own emulator, but we'll have to setup the other parameters
# (-kernel, ...) as well then :(
        # self.emulator     = os.path.join(DIR_AOSP, 'out', 'host', 'linux-x86', 'bin', 'emulator')

        self.logger.debug("+ avd_name: " + self.avd_name)
        self.logger.debug("+ avd_home: " + self.avd_home)
        self.logger.debug("+ avd_dir : " + self.avd_dir)
        self.logger.debug("+ avd_ini : " + self.avd_ini)

        self.running            = False
        self.p                  = None
        self.socket             = None
        self.copied             = False

        self.fresh_copy()

# ENTER #########################################################
    def __enter__(self):
        return self

# EXIT ##########################################################
    def __exit__(self, type, value, traceback):
        # Restore the current working directory
        os.chdir(self.pwd)

        self.stop()
        self.destroy()

# SIMULATIONS ###################################################

    # Simulate an outgoing call.
    def call_outgoing(self, number):
        # Move to the home screen, press the CALL button, press BACK (as
        # sometimes the search screen is opened instead) and press CALL again.
        self.press(KEY_HOME)
        self.press(KEY_CALL)
        self.press(KEY_BACK)
        self.press(KEY_CALL)

        # Type in the number.
        for digit in str(number): self.press(KEY_DIGIT + int(digit))

        # Press the call button again to start calling.
        self.press(KEY_CALL)

        # Call is immidiately accepted by the other party.

        # Press the home button to go back to where we came from.
        self.press(KEY_HOME)

        # Get the outgoing number as this may be different than <number>
        gsmlist = self.tcp_send("gsm list")
        outnumber = re.search("\d+",gsmlist)
        if outnumber != None: return outnumber.group(0)
        return number

    # Simulate an incoming call.
    def call_incoming(self, number):
        self.tcp_send("gsm call " + str(number))

    # Accept an incoming call.
    def call_accept(self, number):
        self.tcp_send("gsm accept " + str(number))

    # Hangup on a current call.
    def call_cancel(self, number):
        self.tcp_send("gsm cancel " + str(number))

    # Simulate an outgoing sms text message
    def sms_send(self, number, message):
        # Kill com.android.mms.
        self.kil("com.android.mms")

        # Start the ComposeMessageActivity.
        self.adb(["shell", "am", "start", "-a", "android.intent.action.MAIN", "-n", "com.android.mms/.ui.ComposeMessageActivity"])

        # Type in the number.
        for digit in str(number): self.press(KEY_DIGIT + int(digit))

        # Press <enter> to select this number, then press <down> twice to move
        # cursor to the compose field.
        self.press(KEY_ENTER)
        self.press(KEY_DOWN)
        self.press(KEY_DOWN)

        # Press the letters.
        message = message.lower()
        for letter in message:
            if letter == " ": self.press(KEY_SPACE)
            else:             self.press(KEY_LETTER + (ord(letter) - ord('a')))

        # Press space to stop word-completion. Then press right and center to
        # push the send button.
        self.press(KEY_SPACE)
        self.press(KEY_RIGHT)
        self.press(KEY_CENTER)

    # Simulate an incoming sms text message.
    def sms_recv(self, number, message):
        self.tcp_send("sms send " + str(number) + " " + message)

    # Simulate a 'connect-to-AC' event.
    def batt_power_connected(self):
        self.tcp_send("power ac on")

    # Simulate a 'disconnect-from-AC' event.
    def batt_power_disconnected(self):
        self.tcp_send("power ac off")

    # Simulate a low battery.
    def batt_low(self):
        self.tcp_send("power ac off")
        self.tcp_send("power status not-charging")
        self.tcp_send("power capacity 10")

    # Simulate a okay battery.
    def batt_okay(self):
        self.tcp_send("power ac on")
        self.tcp_send("power status charging")
        self.tcp_send("power capacity 50")

    # Simulate a network disconnect.
    def disconnect(self):
        self.tcp_send("gsm data off")
        self.tcp_send("gsm voice off")

    # Simulate a network connect.
    def connect(self):
        self.tcp_send("gsm data on")
        self.tcp_send("gsm voice on")

    def geo(self, longitude, latitude):
        self.tcp_send("geo fix %s %s" % (longitude,latitude))

