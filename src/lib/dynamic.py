#!/usr/bin/python

import datetime
import os
import time

import emudroid
import ipshell

# 'normal' simulation runtime
SIMULATION_RUNTIME = 4

# runtime for 'special' simulations
ACTIVITIES_RUNTIME = 20 # total time in simulate_activities. Ignored for now
SERVICES_RUNTIME   = 10 # total time in simulate_services. Ignored for now

ACTIVITY_RUNTIME   = 10 # runtime per activity
SERVICE_RUNTIME    = 10 # runtime per service
MONKEY_RUNTIME     = 60 


# A list of possible actions that may be simulated during dynamic analysis.
SIMULATIONS = [
   'boot',                 # Simulate a reboot
   'gpsfix',               # Simulate a GPS fix
   'incoming_sms',         # Simulate an incoming sms text message
   'outgoing_sms',         # Simulate an outgoing sms text message
   'incoming_call',        # Simulate an incoming phone call
   'outgoing_call',        # Simulate an outgoing phone call
   'disconnect',           # Simulate a network disconnect
   'power',                # Simulate a low battery
   'package',              # Simulate a package install / update / removal
   'main',                 # Execute the main activity
   'activities',           # Start all activities
   'services',             # Start all services
   'monkey',               # Run monkey
   'manual',               # Manual analysis
]

INCOMING_SMS_MESSAGE = 'incoming text message'  # Content of the incoming SMS  message (will be converted to lowercase).
INCOMING_SMS_NUMBER  = '4224'                   # Phone number of the sender.
OUTGOING_SMS_MESSAGE = 'outgoing text message'  # Content of the outgoing SMS message (will be converted to lowercase).
OUTGOING_SMS_NUMBER  = '4224'                   # Phone number to send to.
INCOMING_CALL_NUMBER = '0624424224'             # Phone number of the caller.
OUTGOING_CALL_NUMBER = '0624424224'             # Phone number to call.

# Longitude / latitude used for gps fix simulation
LONGITUDE =  4.900557
LATITUDE  = 52.379016

ROOTDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..')
DIR_APP = os.path.join(ROOTDIR, 'lib', 'apps')
DIR_IMG = os.path.join(ROOTDIR, 'lib', 'images')
DIR_AND = os.path.join(ROOTDIR, 'lib', 'android')

# Package used to simulate a package install / update / removal
EMPTY_APK              = os.path.join(DIR_APP, 'Empty', 'bin', 'Empty.apk')
EMPTY_APK_PACKAGE_NAME = 'com.vvdveen.empty'
 

# Default Error class which we will extend.
class Error(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

# Errors thrown.
class DynamicError(Error):
    pass


class DynamicOptions:
    def __init__(self,
                       nowindow    = False,         # Start emulator with -no-window?
                       breakdown   = False,         # Compute code coverage per simulation technique?
                       scale       = False,         # Scale emulator window by 50%?
                       simulations = SIMULATIONS,   # Actions to simulate.
                ):

        self.nowindow    = nowindow
        self.breakdown   = breakdown
        self.scale       = scale
        self.simulations = simulations

        
        # These are fixed for now
        self.simulation_runtime = SIMULATION_RUNTIME
        self.activities_runtime = ACTIVITIES_RUNTIME    # time spend in simulate_activities (ignored for now)
        self.services_runtime   = SERVICES_RUNTIME      # time spend in simulate_services   (ignored for now)
        self.activity_runtime   = ACTIVITY_RUNTIME      # time spend per activity
        self.service_runtime    = SERVICE_RUNTIME       # time spend per service
        self.monkey_runtime     = MONKEY_RUNTIME        # time spend in simulate_monkey
        self.longitude = LONGITUDE
        self.latitude  = LATITUDE
        self.incoming_sms_message = INCOMING_SMS_MESSAGE
        self.incoming_sms_number  = INCOMING_SMS_NUMBER
        self.outgoing_sms_message = OUTGOING_SMS_MESSAGE
        self.outgoing_sms_number  = OUTGOING_SMS_NUMBER
        self.incoming_call_number = INCOMING_CALL_NUMBER
        self.outgoing_call_number = OUTGOING_CALL_NUMBER

class DynamicAnalysis:

    def __init__(self, filename, options, logger, logbase):
        self.filename = filename
        self.options  = options
        self.logger   = logger
        self.logbase  = logbase

        # This mapping of actions to functions is used in the main loop of the
        # dynamic analysis to execute the simulations. Only actions defined in
        # this dictionary can be simulated.
        # 'fanction': a combination of the words function and action :)
        self.fanctions = { 'boot':          self.simulate_boot,
                           'gps':           self.simulate_gps,
                           'incoming_sms':  self.simulate_incoming_sms,
                           'outgoing_sms':  self.simulate_outgoing_sms,
                           'incoming_call': self.simulate_incoming_call,
                           'outgoing_call': self.simulate_outgoing_call,
                           'disconnect':    self.simulate_disconnect,
                           'power':         self.simulate_power,
                           'package':       self.simulate_package,
                           'main':          self.simulate_main,
                           'activities':    self.simulate_activities,
                           'services':      self.simulate_services,
                           'monkey':        self.simulate_monkey,
                           'manual':        self.simulate_manual}
        
        # remove any simulation from the todo list that is not supported
        self.options.simulations = [ x for x in self.options.simulations if self.fanctions.get(x) ]

# End of initalization/cleanup functions
###############################################################################

    def simulate_boot(self, static_analysis):
        self.logger.debug('+++ Broadcasting BOOT_COMPLETED')
        self.emu.boot_completed(static_analysis.package_name)

        time.sleep(self.options.simulation_runtime)

    def simulate_gps(self, static_analysis):
        self.logger.debug('+++ Simulating GPS location')
        self.emu.gps(self.options.longitude, self.options.latitude)

        time.sleep(self.options.simulation_runtime)

    def simulate_incoming_sms(self, static_analysis):
        self.logger.debug('+++ Simulating an incoming text message')
        self.emu.sms_recv(self.options.incoming_sms_number, self.options.incoming_sms_message)
        
        time.sleep(self.options.simulation_runtime)

    def simulate_outgoing_sms(self, static_analysis):
        self.logger.debug('+++ Simulating an outgoing text message')
        self.emu.sms_send(self.options.outgoing_sms_number, self.options.outgoing_sms_message)

        time.sleep(self.options.simulation_runtime)

    def simulate_incoming_call(self, static_analysis):
        self.logger.debug('+++ Simulating an incoming call')
        self.emu.call_incoming(self.options.incoming_call_number)

        # Wait before we pick up the phone.
        time.sleep(self.options.simulation_runtime)
        self.logger.debug('+++ Accepting the call')
        self.emu.call_accept(self.options.incoming_call_number)

        # Wait before we hang up.
        time.sleep(self.options.simulation_runtime)
        self.logger.debug('+++ Hanging up')
        self.emu.call_cancel(self.options.incoming_call_number)

        time.sleep(self.options.simulation_runtime)

    def simulate_outgoing_call(self, static_analysis):
        self.logger.debug('+++ Simulating an outgoing call')
        number = self.emu.call_outgoing(self.options.outgoing_call_number)

        # Call is automatically accepted by the other party. Wait before we
        # hang up.
        time.sleep(self.options.simulation_runtime)
        self.logger.debug('+++ Hanging up')
        self.emu.call_cancel(number)

        time.sleep(self.options.simulation_runtime)

    def simulate_disconnect(self, static_analysis):
        self.logger.debug('+++ Simulating a network disconnect')
        self.emu.disconnect()

        # Wait before we reconnect.
        time.sleep(self.options.simulation_runtime)
        self.logger.debug('+++ Reconnecting')
        self.emu.connect()

        time.sleep(self.options.simulation_runtime)

    def simulate_power(self, static_analysis):
        self.logger.debug('+++ Simulating a low battery')
        self.emu.batt_low()

        # Wait before we restore the battery to its normal level.
        time.sleep(self.options.simulation_runtime)
        self.logger.debug('+++ Restoring')
        self.emu.batt_okay()

        time.sleep(self.options.simulation_runtime)

    def simulate_package(self, static_analysis):
        self.logger.debug('+++ Simulating package install')
        self.emu.install(EMPTY_APK)

        # Wait before we replace the package.
        time.sleep(self.options.simulation_runtime)
        self.logger.debug('+++ Simulating package replacement')
        self.emu.install(EMPTY_APK)

        # Wait before we remove the package.
        time.sleep(self.options.simulation_runtime)
        self.logger.debug('+++ Simulating package removal')
        self.emu.uninstall(EMPTY_APK_PACKAGE_NAME)

        time.sleep(self.options.simulation_runtime)

    def simulate_main(self, static_analysis):
        if not static_analysis.main_activity: return
        self.logger.debug('+++ Starting main activity')
        self.emu.start_main_activity(static_analysis.package_name, static_analysis.main_activity)

        # Wait before taking a screenshot.
        time.sleep(self.options.simulation_runtime)
        #self.emu.screenshot(os.path.join(self.logbase, os.path.basename(self.filename) + str(datetime.datetime.now()) + '.png'))
        self.emu.screenshot(os.path.join(self.logbase, 'screenshot.png'))
        
        time.sleep(self.options.simulation_runtime)

    def simulate_activities(self, static_analysis):
        if len(static_analysis.activities) == 0: return
        if not static_analysis.main_activity: return
        self.logger.debug('+++ Simulating activities for %5.2fs' % self.options.activities_runtime)
       
        # Run main first to make sure the screen is initialized
        self.emu.start_main_activity(static_analysis.package_name, static_analysis.main_activity)
        time.sleep(self.options.activity_runtime)

        # According to Andrubis, this should not work.
#       runtime = self.options.activities_runtime / float( len(static_analysis.activities) )
#       runtime = self.options.activity_runtime
#       for activity in static_analysis.activities:
#           self.logger.debug('+++ - %s for %5.2fs' % (activity, runtime))
#           self.emu.start_activity(static_analysis.package_name, activity)
#
#           time.sleep(runtime)

        # Instead, they do do something like:
#       runtime = self.options.activities_runtime / float( len(static_analysis.activityactions) )
#       runtime = self.options.activity_runtime
#       for activity, actions in static_analysis.activityactions.iteritems():
#           self.logger.debug('+++ - %s for %5.2fs' % (activity, runtime))
#           self.emu.start_activity(static_analysis.package_name, activity)
#
#           time.sleep(runtime)

        # Having a list of actions, I would choose for something like (if the first option doesn't work. or maybe do a combination...):
#       runtime = self.options.activities_runtime / float( sum(len(val) for val in static_analysis.activityactions.itervalues()) )
        runtime = self.options.activity_runtime
        for activity, actions in static_analysis.activityactions.iteritems():
            for action in actions:
                self.logger.info('+++ - %s, action: %s for %5.2fs' % (activity, action, runtime))
                self.emu.start_activity(static_analysis.package_name, activity, action)

                time.sleep(runtime)


    def simulate_services(self, static_analysis):
        if len(static_analysis.services) == 0: return
        self.logger.debug('+++ Simulating services for %5.2fs' % self.options.services_runtime)

#       runtime = self.options.services_runtime / float( len(static_analysis.services) )
        runtime = self.options.service_runtime
        for service in static_analysis.services:
            self.logger.info('+++ - %s for %5.2fs' % (service, runtime))
            self.emu.start_service(static_analysis.package_name, service)

            time.sleep(runtime)
    
    def simulate_monkey(self, static_analysis):
        self.logger.debug('+++ Simulating monkey for %5.2fs' % self.options.monkey_runtime)
        self.emu.start_monkey(os.path.join(self.logbase, 'monkey.log'), 
                                           static_analysis.package_name, 
                                           static_analysis.categories)
        time.sleep(self.options.monkey_runtime)
        self.emu.stop_monkey()

    def simulate_manual(self, static_analysis):
        print 'Dropping an ipython shell. The package is installed and you'
        print 'should be able to run it. You can use the self.emu object to'
        print 'trigger stimulations:'
        print "- Receive SMS:         self.emu.sms_recv(<number>, <message>)"
        print "- Send SMS:            self.emu.sms_send(<number>, <message>)"
        print "- Screenshot:          self.emu.screenshot(<outputfile>)"
        print "- Start activity Main: self.emu.start_main_activity(<package-name>, <activity>)"
        print "- Start activity X:    self.emu.start_(<package-name>, <activity> [, <action>])"
        print "- Start service:       self.emu.start_service(<package-name>, <service>)"
        print "- Outgoing call:       self.emu.call_outgoing(<number>)"
        print "- Incoming call:       self.emu.call_incoming(<number>)"
        print "- Accept call:         self.emu.call_accept(<number>)"
        print "- Hangup call:         self.emu.call_cancel(<number>)"
        print "- Boot:                self.emu.boot_completed(<package-name>)"
        print "- Network disconnect:  self.emu.disconnect()"
        print "- Network connect:     self.emu.connect()"
        print "- Battery low:         self.emu.batt_power_low()"
        print "- Battery OK:          self.emu.batt_okay()"
        print "- GPS fix:             self.emu.geo(<longitude>,<latitude>)"
        print ""
        print "It is also possible to send commands directly over the current"
        print "TCP connection with the emulator:"
        print "- self.emu.tcp_send(<command>)"
        print ""
        print "And adb commands:"
        print "- using subprocess.Popen(): self.emu.adb(<command>)"
        print "- using os.system():        self.emu.adb_sys(<command>)"
        print ""
        print "Kill an app:"
        print "- self.emu.kil(<package-name>)"
        print ""
        print "static analysis results are available in the static_analysis object:"
        print "- package-name:        static_analysis.package_name"
        print "- activities:          static_analysis.activities"
        print "- ..."
        print ""
        print "Hit Ctrl-D to continue analysis."
        ipshell.ipshell()

    def init(self, static_analysis):
        self.logger.debug('++ Starting emulator')
        self.emu.try_start()

        self.logger.debug('++ Figuring out time discrepancy between host and guest')
        discrepancy = self.emu.get_timing()
        self.logger.info('Host - Guest = %d s' % discrepancy)

        if static_analysis.package_name == '':
            # No package name found during static analysis, it probably failed.
            # get a list of already installed packages before we install the
            # target app so we can figure out the package name.
            pre_installed_packages = self.emu.get_installed_packages()
        
        self.logger.debug('++ Installing APK')
        try: delta = self.emu.install(self.filename)
        except emudroid.EmulatorError as exception:
            self.logger.error('++ --> Failed to install %s: %s', self.filename, str(exception))
            raise DynamicError('Could not install APK: ' + str(exception))
        self.logger.debug('++ Install took %5.2fs' % delta)

        if static_analysis.package_name == '':
            new_installed_packages = self.emu.get_installed_packages()
            for package in new_installed_packages:
                if package not in pre_installed_packages:
                    package_name = package.split()[0]
                    self.logger.info('Found possible package: %s' % package_name)
            static_analysis.package_name = package_name

        self.logger.debug('++ Starting logcat')
        self.logcat_proc, self.logcat_file = self.emu.log(os.path.join(self.logbase, 'logcat.log'))

        self.logger.debug('++ Starting network capture')
        self.emu.start_capturing(os.path.join(self.logbase, 'traffic.pcap'))

        self.logger.debug("++ Enabling VM tracing")
        self.emu.enable_trace(static_analysis.package_name)

        self.logger.debug('++ Starting clock')
        self.start = time.time()

    def finit(self, static_analysis):
        self.emu.disable_trace(static_analysis.package_name)

        self.logger.debug('++ Stopping network capture')
        self.emu.stop_capturing()
       
        self.logger.debug('++ Stopping logcat')
        self.logcat_proc.terminate()

        self.logger.debug('++ Pulling trace files')
        self.emu.pull_dump(self.logbase)

        self.logger.debug('++ Stopping emulator')
        self.emu.stop()
        self.emu.destroy()

##################################################################################
# This is the main loop of the dynamic analysis script 
    def analyse(self, static_analysis):
        self.logger.info('Initializing emulator')
        with emudroid.emudroid(nowindow   = self.options.nowindow, 
                               scale      = self.options.scale,
                               logger     = self.logger) as self.emu:

            self.init(static_analysis)

            for action in self.options.simulations:
                self.logger.info('- Looking at action: ' + action)

                self.logger.debug('++ Simulating ' + action)
                try:
                    self.fanctions[action](static_analysis)
                except emudroid.EmulatorError as exception:
                    self.logger.warning('++ Simulation of action %s failed: %s', action, str(exception))
                
                if self.options.breakdown:
                    self.emu.disable_trace(static_analysis.package_name)
                    os.makedirs       (os.path.join(self.logbase, action))
                    self.emu.pull_dump(os.path.join(self.logbase, action))
                    self.emu.remv_dump()
                    
                    try:
                        self.emu.install(self.filename)
                    except emudroid.EmulatorError as e:
                        self.logger.warning('- Reinstall of package failed: ' + str(e))
                        # The system should have restored the original package, just continue


                # We could kill the app here to get a 'clean' state for the
                # next round, but it turns out that this may have some negative
                # side effects: the AM might reschedule a killed service to
                # restart in x seconds, which may result in undesired behavior.

#               self.emu.disable_trace(static_analysis.package_name)
#               self.emu.kil(static_analysis.package_name)

            self.finit(static_analysis)

