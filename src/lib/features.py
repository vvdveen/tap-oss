#!/usr/bin/python

import subprocess
import operator
import os
import sys
import array
import hashlib

from collections import Counter

import trace

# Get the platform directories
ROOTDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
if not os.path.exists( os.path.join(ROOTDIR, 'config.sh') ):
    ROOTDIR = os.path.join(ROOTDIR, '..')

DIR_APP = os.path.join(ROOTDIR, 'lib', 'apps')
DIR_IMG = os.path.join(ROOTDIR, 'lib', 'images')
DIR_AND = os.path.join(ROOTDIR, 'lib', 'android')
DIR_API = os.path.join(DIR_AND, 'apis')

API = os.path.join(DIR_API, 'android-10.jar') 


class Feature():
    def __init__(self, name, value = False):
        self.name = name
        self.value = value

    def disable(self, value = False):
        self.value = value
    def enable(self, value = True):
        self.value = value
    
    def __repr__(self):
        return "%s: %s" % (str(self.name), str(self.value))

class Features():
    def __init__(self, output = None):

        if output: self.output = open(output, 'w')
        else:      self.output = sys.stdout 

        self.package_name     = Feature('package_name', '')

        # IMEI, IMSI, MSISDN, NET-ISO, ..., read?
        self.telephony_imei           = Feature('telephony_imei')
        self.telephony_imsi           = Feature('telephony_imsi')
        self.telephony_msisdn         = Feature('telephony_msisdn')
        self.telephony_net_iso        = Feature('telephony_net_iso')
        self.telephony_net_op         = Feature('telephony_net_op')
        self.telephony_net_op_name    = Feature('telephony_net_op_name')
        self.telephony_net_type       = Feature('telephony_net_type')
        self.telephony_sim_serial     = Feature('telephony_sim_serial')
        self.telephony_sim_operator   = Feature('telephony_sim_operator')
        self.telephony_get_call_state = Feature('telephony_get_call_state')

#       self.sms_send = Feature('telephony_sms_send')               # Calls to      - android.telephony.SmsManager.sendTextMessage()
                                                                    #               - android.telephony.gsm.SmsManager.sendTextMessage() indicate sms text sending
        self.telephony_sms        = Feature('telephony_sms')        # Objects of type android.telephony.smsMessage*   could indicate SMS text reading/writing
        self.net_connect_manager  = Feature('net_connect_manager')  # Objects of type android.net.ConnectivityManager could indicate information stealing (monitor network connections, ...)
        self.net_info             = Feature('net_info')             # Objects of type android.net.NetworkInfo         could indicate information stealing (current network state, ...)

        self.location              = Feature('location')                   # Objects of type android.location.LocationManager        could indicate GPS usage
        self.content_intent        = Feature('content_intent')             # Calls to        android.content.Intent.setaction()      indicate an new intent action to be performed
        self.content_query         = Feature('content_query')              # Calls to        android.content.ContentResolver.query() could indicate information steailing (SMS, contactlist, ...)
        self.content_signature     = Feature('content_signature')          # Objects of type android.content.pm.signature            could indicate package signature checking
        self.content_get_service   = Feature('content_get_service')        # Calls to *.getSystemService     indicate retrieval of list of system services
        self.content_get_prefs     = Feature('content_get_prefs')          # Calls to *.getSharedPreferences indicate retrieval of shared preferences
        self.content_get_pmanager  = Feature('content_get_pmanager')       # Calls to *.getPackageManager    indicate retrieval of package manager
        self.content_start_service = Feature('content_start_service')      # Calls to *.startService         indicate the start of a new service

        self.settings_android_id   = Feature('settings_android_id')        # Calls to        android.provider.Settings$Secure.getString('android_id') could indicate emulator detection

        self.io_database = Feature('io_database')                # Calls to   android.database*                indicate database reading/writing
        self.io_delete   = Feature('io_delete')                  # Calls to                  *.deleteFile()    indicate File operations (delete File)
        self.io_exec     = Feature('io_exec')                    # Calls to  java.lang.Runtime.exec()          indicate external command execution
        self.io_fexists  = Feature('io_fexists')                 # Calls to            java.io.File.exists()   indicate File operations (does File exists?)
        self.io_fopen    = Feature('io_fopen')                   # Calls to -                *.openFileInput()
                                                                 #          -                *.openFileOutput()
                                                                 #          -          java.io.File()          indicate File operations (open File)
        self.io_file     = Feature('io_file')                    # Calls to java.io.File* indicate File operations

        self.misc_alarm       = Feature('misc_alarm')            # Calls to android.app.AlarmManager*            could indicate a dynamic analysis evasion
        self.misc_classloader = Feature('misc_classloader')      # Calls to  - java.lang.ClassLoader*
                                                                 #           - java.lang.system.loadLibrary      indicate dynamic class loader operations
        self.misc_crypto      = Feature('misc_crypto')           # Calls to javax.crypto*                        indicate crypto operations
        self.misc_digest      = Feature('misc_digest')           # Calls to java.security.Messagedigest.digest() indicate a hashing operation
        self.misc_handler     = Feature('misc_handler')          # Calls to - android.os.handler.sendMessageAtTime() could indicate dynamic analysis evasion
                                                                 #          - android.os.handler.sendMessageDelayed() could indicate dynamic analysis evasion
                                                                 #          - android.os.handler.sendEmptyMessageDelayed
                                                                 #          - android.os.handler.sendEmptyMessageAtTime
                                                                 #          - android.os.handler.postDelayed
                                                                 #          - android.os.handler.postAtTime

        self.misc_locale     = Feature('misc_locale')            # Calls to java.util.locale*                    indicate Locale operations
        self.misc_native     = Feature('misc_native')            # Calls to native code indicate binary ARM code being executed
        self.misc_reflection = Feature('misc_reflection')        # Calls to java.lang.reflect*                   indicate reflection operations
        self.misc_schedule   = Feature('misc_schedule')          # Calls to java.util.Timer*                     could indicate a dynamic analysis bypass 
        self.misc_sleep      = Feature('misc_sleep')             # Calls to java.lang.Thread.sleep()             could indicate a dyanmic analsysi evasion
        self.misc_zip        = Feature('misc_zip')               # Calls to java.util.zip*                       indicate zip operations

        self.network         = Feature('network')                # Calls to java.net* indicate network operations
        self.network_http    = Feature('network_http')           # Calls to - java.net.HttpURLConnection.connect()
                                                                 #          -                 org.apache.http*       indicate HTTP network operations

        # The average length of function names that are not API calls or implemented abstract methods
        self.average        = Feature('average', 0.0)

        # Two bloom arrays. One for storing whether or not a function was executed, and one that keeps track of the number of times a function was executed.
        self.bloom          = Feature('bloom', 0)
        self.bloom_array    = Feature('bloom_array', None)

    def get_dict(self):
        d = {}
        for attr, feature in self.__dict__.iteritems():
            if attr != 'output': d[feature.name] = feature.value
        return d

    def get_values(self):
        return sorted(self.get_dict().iteritems(), key = operator.itemgetter(0))

    def get_fields(self):
        return sorted(self.get_dict().iteritems())

    def get_pretty(self, colorize = False):
        string = ""
        for name, value in self.get_values():
#           if name not in ['bloom', 'bloom_array']:
                if value == True and colorize: string += '\033[91m%s: %15s\n\033[0m' % (name.ljust(25), value)
                else:                          string +=         '%s: %15s\n'        % (name.ljust(25), value)
        return string

    def __repr__(self):
        return self.get_pretty()

    def dump(self, colorize = False):
        print >>self.output, self.get_pretty(colorize)

        if self.output != sys.stdout:
            self.output.close()

    # Find features
    def get_features(self, traces, api_classes, package_name):

        # For a given API, get a list of abstract classes 
        def _load_abstracts(api):
            abstracts   = []
            api_classes = trace.load_api([api])

            try:
                abstracts_f = open(api + ".abstracts", 'r')
                for line in abstracts_f:
                    abstracts.append(line.strip())
                abstracts_f.close()
            except IOError:
                abstracts_f = open(api + ".abstracts", 'w')

                for classname in api_classes:
                    p = subprocess.Popen(["javap", "-classpath", api, classname], stdout = subprocess.PIPE, stderr = subprocess.PIPE)
                    out, err = p.communicate()
                    for line in out.splitlines():
                        if 'abstract' in line:
                            abstracts.append(line.strip())
                            print >>abstracts_f, line.strip()

                abstracts_f.close()

            return abstracts

        # Generate a list of traced functions that are *not*:
        # - Android API calls
        # - Implemented abstract methods from the Android API
        # - VM internals (e.g. access$...() calls)
        # This will give us a list of functions that were declared by the target app itself
        def _get_target_functions(functions, abstracts): 
            dict = {}
            targ = []
            
            for function in functions:
                if not function.is_api and function.modifiers and function.return_type and function.name and not '$' in function.name:
                    name = "%s abstract %s %s(%s)" % (" ".join(function.modifiers), function.return_type, function.name, ", ".join([x[0] for x in function.parameters]) )
                    if not any(name in s for s in abstracts):
                        if function.name in dict: dict[function.name] = dict[function.name] + 1
                        else:                     dict[function.name] = 1
                        targ.append(function)
                        
            return dict, targ

        def _bloom_array(target):
            myarray = array.array('i', (0 for i in range(0,1024)) )
            for k, v in target.iteritems():
                hashint = int(hashlib.sha224(k[0]).hexdigest(), 16)
                index = int(hashint % 1024)
                
                myarray[index] = myarray[index] + v
            return myarray

        def _bloom(target):
            myhash = 0
            numones = 0         # for debugging
            numcollisions = 0   # for debugging
            for s in target:
                hashint = int(hashlib.sha224(s[0]).hexdigest(), 16)
                index = (1 << (hashint % 1024))

                if myhash & index == 0:
                    numones += 1
                else:
                    numcollisions += 1
                
                myhash = myhash | index

            assert(myhash < (2 ** 1024))
            return myhash

        function_names    = Counter()
        functions         = []
        constructor_names = Counter()
        constructors      = []
        reflected_names   = Counter()
        for key, value in traces.iteritems():
            function_names    += Counter(value.get_function_names())
            functions         += value.functions
            constructor_names += Counter(value.get_constructor_names())
            constructors      += value.constructors
            reflected_names   += Counter(value.get_reflected_names())

        # TODO Not sure if necessary, but this does not include recursive reflection calls.
        reflected = [x.reflected_method for x in functions if x.reflected_method]

        self.package_name.enable(package_name)
       
        for function in functions+reflected :
      
            if function.target_object:
                # ANDROID CLASSES FIRST
                if function.target_object == 'android.telephony.TelephonyManager':
                    if function.name == 'getDeviceId':                 self.telephony_imei.enable()
                    if function.name == 'getSubscriberId':             self.telephony_imsi.enable()
                    if function.name == 'getLine1Number':              self.telephony_msisdn.enable()
                    if function.name == 'getNetworkCountryIso':        self.telephony_net_iso.enable()
                    if function.name == 'getNetworkOperator':          self.telephony_net_op.enable()
                    if function.name == 'getNetworkOperatorName':      self.telephony_net_op_name.enable()
                    if function.name == 'getNetworkType':              self.telephony_net_type.enable()
                    if function.name == 'getSimSerialNumber':          self.telephony_sim_serial.enable()
                    if function.name == 'getSimOperator':              self.telephony_sim_operator.enable()
                    if function.name == 'getCallState':                self.telephony_get_call_state.enable()

                if (   (function.target_object == 'android.telephony.SmsManager'     and function.name == 'sendTextMessage')
                    or (function.target_object == 'android.telephony.gsm.SmsManager' and function.name == 'sendTextMessage')): self.telephony_sms.enable()
                if function.target_object.startswith('android.telephony.SmsMessage'):                                          self.telephony_sms.enable()

                if function.target_object == 'android.net.ConnectivityManager':  self.net_connect_manager.enable()
                if function.target_object == 'android.net.NetworkInfo':          self.net_info.enable()
                if function.target_object == 'android.location.LocationManager': self.location.enable()
                if function.target_object == 'android.app.AlarmManager':         self.misc_alarm.enable()

                if function.target_object == 'android.content.Intent'          and function.name == 'setAction': self.content_intent.enable()
                if function.target_object == 'android.content.ContentResolver' and function.name == 'query':     self.content_query.enable()
                if function.target_object == 'android.content.pm.Signature':                                     self.content_signature.enable()
                # These functions are implemented by android.content.Context, but they are inherited by other classes as well, which is why we make it a bit more generic here.
                if function.name == 'getSystemService':     self.content_get_service.enable()
                if function.name == 'getPackageManager':    self.content_get_pmanager.enable()
                if function.name == 'getSharedPreferences': self.content_get_prefs.enable()
                if function.name == 'startService':         self.content_start_service.enable()
                if function.name == 'openFileInput':        self.io_fopen.enable()
                if function.name == 'openFileOutput':       self.io_fopen.enable()
                if function.name == 'deleteFile':           self.io_delete.enable()
      
                if function.target_object == 'android.provider.Settings$Secure' and function.name == 'getString' and ('java.lang.String', 'android_id') in function.parameters: self.settings_android_id.enable()
      
                if function.target_object.startswith('android.database'): self.io_database.enable()
      
                if (function.target_object == 'android.os.Handler' and
                       (function.name == 'sendMessageAtTime' or
                        function.name == 'sendMessageDelayed' or
                        function.name == 'sendEmptyMessageAtTime' or
                        function.name == 'sendEmptyMessageDelayed' or
                        function.name == 'postAtTime' or
                        function.name == 'postDelayed')):                   self.misc_handler.enable()


                # THEN JAVA
                if function.target_object == 'java.security.MessageDigest' and function.name == 'digest':      self.misc_digest.enable()
                if function.target_object == 'java.util.Timer':                                                self.misc_schedule.enable()
                if function.target_object == 'java.lang.Thread'            and function.name == 'sleep':       self.misc_sleep.enable()
                if function.target_object == 'java.util.Locale':                                               self.misc_locale.enable()
                if function.target_object == 'java.io.File'                and function.name == 'exists':      self.io_fexists.enable()
                if function.target_object == 'java.lang.Runtime'           and function.name == 'exec':        self.io_exec.enable()
                if function.target_object == 'java.lang.ClassLoader'       and function.name == 'loadClass' and function.parameters[0][1] not in api_classes: 
                                                                                                               self.misc_classloader.enable()
                if function.target_object == 'java.lang.System'            and function.name == 'loadLibrary': self.misc_classloader.enable()
                if function.target_object == 'java.net.HttpURLConnection'  and function.name == 'connect':     self.network_http.enable()
                if function.target_object.startswith('org.apache.http'):                                       self.network_http.enable()
                if function.target_object.startswith('java.net'):                                              self.network.enable()
                if function.target_object.startswith('javax.crypto'):                                          self.misc_crypto.enable()
                if function.target_object.startswith('java.lang.reflect'):                                     self.misc_reflection.enable()
                if function.target_object.startswith('java.io.File'):                                          self.io_file.enable()
                if function.target_object.startswith('java.util.zip'):                                         self.misc_zip.enable()

                if 'native' in function.modifiers and not function.is_api:                                     self.misc_native.enable()
            
        for constructor in constructors:
            if constructor.class_name == 'java.io.File':  self.io_fopen.enable()

        abstracts = _load_abstracts(API)

        target_function_count, target_function_list = _get_target_functions(functions, abstracts) 
        target_function_names = list(target_function_count)

        if target_function_names:
            average = lambda x: sum(x) / float(len(x))
            self.average.enable(average( map(lambda x: len(x), target_function_names )))

        if function_names:
            self.bloom.enable(       _bloom( list(function_names)         ))
            self.bloom_array.enable( _bloom_array(function_names).tolist() )

def parse(path):
    features = Features()

    try:
        f = open(path)
        for line in f:
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip()

            if key and val:
                if key == 'package_name': val = val.strip()
                else:                     val = eval(val)
                setattr( features, key, Feature(key, val) )

    except IOError:
        pass

    return features

