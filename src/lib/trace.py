#!/usr/bin/python

import re
import zipfile
import os
import argparse
import logging
import pydot

from collections import defaultdict, Counter
from ipshell import ipshell

# Get the platform directories
ROOTDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
if not os.path.exists( os.path.join(ROOTDIR, 'config.sh') ):
    ROOTDIR = os.path.join(ROOTDIR, '..')

DIR_APP = os.path.join(ROOTDIR, 'lib', 'apps')
DIR_IMG = os.path.join(ROOTDIR, 'lib', 'images')
DIR_AND = os.path.join(ROOTDIR, 'lib', 'android')
DIR_API = os.path.join(DIR_AND, 'apis')

API = os.path.join(DIR_API, 'android-10.jar') 

possible_modifiers = ['abstract', 
                      'final', 
                      'inline', 
                      'interface', 
                      'native', 
                      'private', 
                      'protected', 
                      'public', 
                      'static', 
                      'strict', 
                      'synchronized',  
                      'transient', 
                      'volatile']

colorize = False

# These functions are accesible without the need of creating a Trace object.

def load_api(apis = [API]):
    api_classes = []
 
    for api in apis:
        api_f = zipfile.ZipFile(api)
        for class_file in api_f.infolist():
            filename, ext = os.path.splitext(class_file.filename)
            if ext == '.class':
                api_classes.append(filename.replace('/','.'))
        api_f.close()

    return list(set(api_classes))

def is_api(class_name, api_classes):
    if class_name in api_classes:             return True
    if class_name == 'dalvik.system.VMDebug': return True
    return False

def print_progress(logger, current, total, prev):
    newp = int(float(current) / total * 100)
    if newp > prev:
        logger.info('#     .%03d%%' % newp)
        prev = newp
    return prev

def get_linenumbers(filename):
    linenumbers = -1
    f = open(filename)
    for linenumbers, line in enumerate(f): pass
    f.close()
    return linenumbers+1



class Error(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class ParseError(Error):
    pass

class Constructor:
    def __init__(self, linenumber = 0, timestamp = 0, depth = 0):
        self.class_name       = None       # Class name
        self.parameters       = []         # Parameters as a list of tuples: (parameter_type, parameter_value)

        self.called_by        = None       # Function/Constructor object that called this function
        self.called           = defaultdict(set)    # Dictionary with class names as keys and a unique list of method names as values

        self.is_api           = False      # Whether or not this is an API class
        self.depth            = depth      # Depth
        self.linenumber_enter = linenumber # Linenumber in trace file upon entering
        self.linenumber_leave = 0          # Linenumber in trace file upon return
        self.timestamp_enter  = timestamp  # Timestamp of entering
        self.timestamp_leave  = 0          # Timestamp of leaving
        self.failed_enter     = True       # Whether or not parsing failed during the constructor call
        self.failed_leave     = True       # Whether or not parsing failed during the return statement of the functino 
    def __str__(self):
        if colorize: return ("new \033[94m%s(\033[0m\033[91m%s\033[0m)" % (self.class_name, self.parameters))
        else:        return ("new %s(%s)" % (self.class_name, self.parameters))

class Function:
    def __init__(self, linenumber = 0, timestamp = 0, depth = 0):
        self.modifiers       = []          # Modifiers of this function (public, private, protected, static, volatile, ...)
        self.parameters      = []          # Parameters as a list of tuples: (parameter_type, parameter_value)
        self.exception       = None        # Exception thrown
        self.return_type     = None        # Return type of this function
        self.return_value    = None        # Return value of this function
        self.target_object   = None        # Target object
        self.target_object_s = None        # Target object (string representation) (only if non-static)
        self.name            = None        # Method name
        self.retway          = None        # returns/throws

        self.called_by       = None        # Function/Constructor object that called this function
        self.called          = defaultdict(set)    # Dictionary with class names as keys and a unique list of method names as values

        self.is_api           = False      # Whether or not this is an API call 
        self.depth            = depth      # Depth
        self.linenumber_enter = linenumber # Linenumber in trace file upon entering
        self.linenumber_leave = 0          # Linenumber in trace file upon return
        self.timestamp_enter  = timestamp  # Timestamp of entering
        self.timestamp_leave  = 0          # Timestamp of leaving
        self.failed_enter     = True       # Whether or not parsing failed during the function call
        self.failed_leave     = True       # Whether or not parsing failed during the return statement of the function 

        self.reflected_method = None

    def __str__(self):
        if colorize: return ("\033[94m%s\033[0m(\033[91m%s\033[0m).\033[94m%s\033[0m(\033[91m%s\033[0m) %s (\033[94m%s\033[0m) '\033[92m%s\033[0m'" % (
            #                 self.linenumber_enter, self.timestamp_enter, 
                              self.target_object, self.target_object_s, self.name, self.parameters, 
                              self.retway, self.return_type, self.return_value))
        else:        return ("%s(%s).%s(%s) %s (%s) '%s'" % (
            #                 self.linenumber_enter, self.timestamp_enter, 
                              self.target_object, self.target_object_s, self.name, self.parameters, 
                              self.retway, self.return_type, self.return_value))

    def equals_signature(self, other):
        return (self.name          == other.name
            and self.parameters    == other.parameters
            and self.target_object == other.target_object
            and self.return_type   == other.return_type)

    def __eq__(self, other):
        if isinstance(other, self.__class__): return self.__dict__ == other.__dict__
        else:                                 return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(str(self))

class Trace:
    def __init__(self, 
                        filename             = None,   # Input trace file.
                        logger               = None,   # Logger.
                        api_classes          = [],     # A list of class names that are considered part of the API.
                        constructors_return  = True,   # Whether or not constructor calls have return statements associated with them (True for VM tracing).
                        trace_has_timestamps = True    # Whether or not tracelines start with a timestamp.
                ):

        self.function_stack = []        # A stack of function objects. Whenever a return statement is found, a function object is popped from this stack.
        self.functions      = []        # A list of functions found.
        self.constructors   = []        # A list of constructors found.

        self.constructors_return  = constructors_return
        self.trace_has_timestamps = trace_has_timestamps

        self.logger = logger

        # load api classes
        if not api_classes: self.api_classes = load_api()
        else:               self.api_classes = api_classes

        # Regular expressions to parse the trace output:
        self.constructor_parser     = re.compile('(.*?)\((.*)')
        self.function_parser        = re.compile('(.*?) ([^\(]*)(\("(.*?)(?="\)\.)"\))?\.([^\(]*)\((.*)')
        self.leaving_parser         = re.compile('(\((.*?)\))?\s*("(.*?)")?\s*(// (.*))?')
#       self.parm_parser            = re.compile('\((.*?)\) "(.*?((?=", \()|(?="\))))"')
        self.parm_parser            = re.compile('\((.*?)\) ["\[](.*?((?=["\]], \()|(?=["\]]\))))["\]]')    ## HIGHLY EXPERIMENTAL

        if filename: self._parse_file(filename)

    def is_api(self, classname):
        return is_api(classname, self.api_classes)

    def get_function_names(self, is_api = None):
        name_list = defaultdict(int)
        for function in self.functions:
            name_list[(function.target_object + "." + function.name, function.is_api)] += 1
        return name_list

    def get_constructor_names(self, is_api = None):
        name_list = defaultdict(int)
        for constructor in self.constructors:
            name_list[(constructor.class_name, constructor.is_api)] += 1
        return name_list

    def get_reflected_names(self, is_api = None):
        name_list = defaultdict(int)
        for function in self.functions:
            if function.reflected_method:
                name_list[(function.reflected_method.target_object + "." + function.reflected_method.name, function.reflected_method.is_api)] += 1
        return name_list

    def get_failures(self):
        failures = []
        for    function in self.functions:
            if    function.failed_enter or    function.failed_leave: failures.append(function)
        for constructor in self.constructors: 
            if constructor.failed_enter or constructor.failed_leave: failures.append(constructor)
        return failures


##############################################################################################################
# PARSE FUNCTIONS                                                                                            #
# For each handler, there is also a _fast() variant. These methods are used                                # # #
# when computing code coverage. When calling _parse_file_fast, a list will be                               ###
# populated with functions and constructors (which are represented as function                               #
# objects as well, instead of constructor objects). The functions objects in
# this list do not contain return values and may be missing other fields as
# well (timestamps are omitted for example). 
#

    # PARSE PARAMETERS
    #   input:      ((<return_type>) "<return_value>", (<return_type>) "<return_value>", ...)
    #   return:    list of parameters
    #
    def _parse_parameters(self, line):
        print 'parse-parameters, input: '  + line

        parameters = []

        # Parse using regex
        groups = self.parm_parser.findall(line)
        try:
            for group in groups: parameters.append( (group[0], group[1]) )
        except IndexError as exception:
            raise ParseError("Could not parse parameters: %s" % exception)

        return parameters

    # PARSE PARAMETERS, FAST
    #   input:      ((<return_type>) "<return_value>", (<return_type>) "<return_value>", ...)
    #   return:    list of parameters
    #
    def _parse_parameters_fast(self, line):
        # this is not really much faster. we only omit return values, to make
        # it easier to match against static analysis results
        print 'parse-parameters, input: '  + line

        parameters = []

        # parse using regex
        groups = self.parm_parser.findall(line)
        try:
            for group in groups: parameters.append( group[0] )
        except IndexError as exception:
            raise ParseError("Could not parse parameters: %s" % exception)

        return parameters


    # PARSE ENTER CALL
    #   input:      new <class_name>(<parameters>) | <modifiers> <return_type> <target_object>(<target_object_description>).method_name(<parameters>)
    #   return:     Constructor | Function
    #
    def _parse_enter(self, line, linenumber, timestamp, depth):

        if line.split()[0] == 'new':            # CONSTRUCTOR
            obj = Constructor(linenumber, timestamp, depth)

            # Remove 'new' from the input
            line = line.split(' ',1)[1].strip()
        
            # Parse the class name using regex
            groups = self.constructor_parser.search(line)
            if groups is None: raise ParseError("Constructor parser regex failed (line incomplete?)")
            try:
                obj.class_name = groups.group(1)
                line           = groups.group(2)
            except IndexError as exception:
                raise ParseError("Could not parse constructor: %s" % exception)
            if self.is_api(obj.class_name): obj.is_api = True

        else:                                   # FUNCTION
            obj = Function(linenumber, timestamp, depth)

            # Parse modifiers by looping over all words at the beginning of the input
            for modifier in line.split():
                if modifier in possible_modifiers:
                    obj.modifiers.append(modifier)
                    line = line.replace(modifier, '', 1).strip()
                else: break

            # Parse function call by using regex
            groups = self.function_parser.search(line)
            if groups is None: raise ParseError("Function parser regex failed (line incomplete?)")
            try:
                obj.return_type     = groups.group(1)
                obj.target_object   = groups.group(2)
                obj.target_object_s = groups.group(4)
                obj.name            = groups.group(5)
                line                = groups.group(6)
            except IndexError as exception:
                raise ParseError("Could not parse function: %s" % exception)
            if self.is_api(obj.target_object): obj.is_api = True
            
#            # Extract reflected methods
#            if obj.target_object == 'java.lang.reflect.Method' and obj.name == 'invoke':
#                line2 = obj.target_object_s
#                f = self._parse_enter(line2, linenumber, timestamp, depth)
##               obj.target_object = f.target_object
##               obj.target_object_s = f.target_object_s
##               obj.name = f.name
#                obj.reflected_method = self._parse_enter(line2, linenumber, timestamp, depth)
                
        obj.parameters      = self._parse_parameters(line)
        obj.failed_enter    = False

        return obj 

    # PARSE ENTER CALL, FAST
    #   input:      new <class_name>(<parameters>) | <modifiers> <return_type> <target_object>(<target_object_description>).method_name(<parameters>)
    #   return:     Function object
    #
    def _parse_enter_fast(self, line, timestamp):
        # We handle constructors as functions, as this makes it easier to
        # compare to static analysis output. Optimizations are mainly achieved
        # by removing debug statements and not parsing API calls completely.

        function = Function()

        if line.split()[0] == 'new': #constructor
            # remove 'new' from the input
            line = line.split(' ',1)[1].strip()

            # parse the class_name using regex
            groups = self.constructor_parser.search(line)
            if groups is None: raise ParseError("Constructor parser regex failed (line incomplete?)")
            try:
                # ignore API calls only if timestamps are ignored. this way, if we are generating a code coverage table, we can include the total number of functions called
                if timestamp == 0: 
                    if self.is_api(groups.group(1)): return None
                function.return_type   = 'void' 
                function.name          = "<init>"
                function.target_object = groups.group(1)
                line                   = groups.group(2)
            except IndexError as exception:
                raise ParseError("Could not parse constructor: %s" % exception)
    
        else: #function
            # remove modifiers by looping over all words at the beginning of the input
            for modifier in line.split():
                if modifier in possible_modifiers: line = line.replace(modifier, '', 1).strip()
                else: break

            # parse function call by using regex
            groups = self.function_parser.search(line)
            if groups is None: raise ParseError("Function parser regex failed (line incomplete?)")
            try:
                # ignore API calls if timestamps are ignored
                if timestamp == 0: 
                    if self.is_api(groups.group(2)): return None
                function.return_type     = groups.group(1)
                function.target_object   = groups.group(2)
                function.name            = groups.group(5)
                line                     = groups.group(6)
            except IndexError as exception:
                raise ParseError("Could not parse function: %s" % exception)

        # parse the paramaters
        function.parameters = self._parse_parameters_fast(line)
        function.timestamp  = timestamp
        return function


    # PARSE RETURN STATEMENT
    #   input:      return|throws <return_type>[ <return_value>[ // <function call>]]
    #
    def _parse_leaving(self, line, linenumber, timestamp, depth, obj):
        # Parse 'return' or 'throws' (both 6 characters long)
        retway = line[:6]
        line = line.replace(retway, '', 1).strip()

        # Parse return statement using regex
        if retway == 'return':
            groups = self.leaving_parser.search(line)
            if groups is None: raise ParseError("Leaving parser regex failed (line incomplete?)")
            try:
                exception    = None
                return_type  = groups.group(2)
                return_value = groups.group(4)
                line         = groups.group(6)
            except IndexError as exception:
                raise ParseError("Could not parse return value: %s", exception)
        else:
            groups = re.search('(.*)',line)
            if groups is None: raise ParseError("Could not parse exception")
            try:
                exception    = groups.group(1)
                return_value = groups.group(1)
                line         = '' # Truncate line due to inability to parse [ // <function call> ]
            except IndexError as exception:
                raise ParseError("Could not parse exception: %s" % exception)

        # Parse function call if it was not parsed before (i.e., if linenumber of entering was 0)
        if line and obj.linenumber_enter == 0:
            obj = self._parse_enter(line, linenumber, timestamp, depth)

        # If the provided function has a return_type set, it should be the same
        # as the return_type of this statement. 
        if retway == 'retun' and ( 
                (isinstance(obj, Function)    and return_type != obj.return_type) or
                (isinstance(obj, Constructor) and return_type != obj.class_name )):
            raise ParseError("Invalid return_type found. Expected " + str(obj.return_type) + ",  but found " + str(return_type))
       
        obj.exception        = exception
        obj.return_value     = return_value
        obj.retway           = retway
        obj.linenumber_leave = linenumber
        obj.timestamp_leave  = timestamp
        obj.failed_leave     = False


    # PARSE A SINGLE TRACE LINE
    #   input:      input line from trace file
    #
    def _parse_line(self, line, linenumber):

        try:
            timestamp = 0
            if self.trace_has_timestamps: 
                timestamp, eq, line = line.partition(':')
                timestamp.strip()
                timestamp = int(timestamp)

            depth = len(line) - len(line.lstrip())
            line = line.lstrip()

            if line.split()[0] in ['return', 'throws']:
                # Pop the matching function the stack.
                if self.function_stack:
                    prev_depth = self.function_stack[-1].depth
                    if depth == prev_depth:    f = self.function_stack.pop()   # We're good.
                    elif depth < prev_depth:   f = Function()                  # We missed a function call, use a fake one.
                    elif depth > prev_depth:                                   # We missed a return, keep trying...
                        while self.function_stack[-1].depth > depth:
                            self.function_stack.pop()
                        f = self.function_stack.pop()
                else: f = Function()                                                # No function stack, use a fake Function
                self._parse_leaving(line, linenumber, int(timestamp), depth, f)
            elif line.split()[0] == 'new':
                try:
                    constructor = self._parse_enter(line, linenumber, int(timestamp), depth)
                    if len(self.function_stack) > 0:
                        constructor.called_by = self.function_stack[-1]
                    self.constructors.append(constructor)
                    if self.constructors_return: self.function_stack.append(constructor)
                except ParseError as exception:
                    constructor = Constructor()
                    if self.constructors_return: self.function_stack.append(constructor)
                    raise exception
            else: # Function call
                try:
                    function = self._parse_enter(line, linenumber, int(timestamp), depth)
                    if len(self.function_stack) > 0:
                        function.called_by = self.function_stack[-1]
                    self.functions.append(function)
                    self.function_stack.append(function)
                except ParseError as exception:
                    function = Function()
                    self.function_stack.append(function)
                    raise exception

        except ParseError as exception:
            pass

    # PARSE A SINGLE TRACE LINE, FAST
    #   input:      input line from trace file
    #   return:     Function object
    #
    def _parse_line_fast(self, line, ignore_timestamps):
        # If set, we don't care about timestamps. We also don't care about
        # return statements or thrown exceptions, so we don't have to keep
        # track of a function stack. We can also ditch function depths and omit
        # debug messages.
        
        # Remove <TIMESTAMP>:<WHITESPACE> from line format: <TIMESTAMP>:<WHITESPACE><FUNCTION_LINE>
        try:
            timestamp = 0
            if self.trace_has_timestamps: 
                timestamp = line.split(':',1)[0].strip() 
                line      = line.split(' ',1)[1].strip()
            if ignore_timestamps: timestamp = 0
            if line.split()[0] in ['return', 'throws']:    return None
            else:                                          return self._parse_enter_fast(line, int(timestamp))
        except (ParseError, IndexError) as exception:
            self.logger.warning("Could not parse line\n  %s\n--> %s" % (line.strip(), exception ))
        
        return None


    # PARSE THE ENTIRE FILE
    #
    def _parse_file(self, filename):
        functions = []

        f = open(filename)
        for linenumber, line in enumerate(f):
            # only parse lines that end with a newline
            if re.search('.*$\n',line):
                function = self._parse_line(line, linenumber+1)
                if function != None: functions.append(function)
        f.close()

        return functions

    # PARSE THE ENTIRE FILE, FAST
    #
    def _parse_file_fast(self, filename, ignore_timestamps = False, verbose = False):
        functions = []

        # get the total number of lines if we have to keep track of the progress
        linenumbers = get_linenumbers(filename)
        if linenumbers == 0:
            self.logger.warning('#     ! Empty file')
            return functions

        # progress percentages are rounded and will only be logged if different than previous
        prev = 0

        f = open(filename)
        for linenumber, line in enumerate(f):

            # only print progress in verbose mode to avoid bloated coverage log files
            if verbose: prev = print_progress(self.logger, linenumber, linenumbers, prev)
            
            # we don't care about incomplete lines, these should result in
            # a thrown exception. should not occur that often anymore
            function = self._parse_line_fast(line, ignore_timestamps)
            if function != None: functions.append(function)
        f.close()

        # return a unique list of functions. this would only make a difference if timestamps are ignored
        if ignore_timestamps: return list(set(functions))
        return functions 
                                                                                                            
                                                                                                             #
                                                                                                            ###
                                                                                                           # # #
# PARSE FUNCTIONS                                                                                            #
##############################################################################################################

def load_dir(logdir, api_classes, logger):
    traces = {}

    dump_filename_parser = re.compile('^[a-zA-Z\.]*\.(\d+)\.(\d+)$')
    
    for dirpath, dirnames, filenames in os.walk(logdir):
        for filename in filenames:

            # search for method traces
            groups = dump_filename_parser.search(filename)
            if groups is None: continue
            pid = int(groups.group(1))
            tid = int(groups.group(2))

            dump = os.path.join(dirpath, filename)

            traces[ (pid, tid) ] = Trace( filename               = dump,
                                          api_classes            = api_classes,
                                          logger                 = logger)

    return traces

def print_names(names, no_api = None):
    for key, value in sorted(names.iteritems()): 
        if no_api is not None:
            if no_api == False: 
                if not key[1]: print "%75s: %d" % (key[0].ljust(75), value)
            else:               
                if     key[1]: print "%75s: %d" % (key[0].ljust(75), value)
        else:                  print "%75s: %d" % (key[0].ljust(75), value)


#classes[ <class_name> ] [ <method_name> ] [ <class_callled> ] = set (<methods_called>)
classes = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))


def print_callgraph():
    for clazz, methods in sorted(classes.iteritems()):
        for methodname, called in sorted(methods.iteritems()):
            print '%s.%s called:' % (clazz, methodname)
            for class_called, methods_called in sorted(called.iteritems()):
                      
                for m in sorted(methods_called):
                    print '- %s.%s' % (class_called, m)   


def generate_callgraph(apis = False, use_clusters = True, use_colors = True, vertical = False, splines = 'spline', fs = None, cs = None):
    """
    Generate a pydot graph
    Parameters:
        apis            - Include API calls. Note that you cannot revert once API calls were included.
        use_clusters    - Group functions into clusters by their classname.
        use_colors      - Use a different color for each classname.
        vertical        - Vertically allign nodes in clusters.
        splines         - Which graphviz spline type to use ('spline', 'ortho', ...).
    """

    global functions
    global constructors

    if fs: functions = fs
    if cs: constructors = cs

    # populate a list of constructors/functions called for each constructor/function
    for f in functions + constructors:
        if apis:
            if f.called_by:
                if isinstance(f, Function):    
                    if not '$' in f.name:       f.called_by.called[f.target_object].add(f.name)
                if isinstance(f, Constructor):  f.called_by.called[f.class_name].add('<init>')
        else:
            if f.called_by and not f.is_api:
                if isinstance(f, Function):    
                    if not '$' in f.name:       f.called_by.called[f.target_object].add(f.name)
                if isinstance(f, Constructor):  f.called_by.called[f.class_name].add('<init>')


    for f in functions + constructors:
        if apis:
            if f.called:
                for clazz, methods in f.called.iteritems():
                    if isinstance(f, Function):    
                        if not '$' in f.name:      classes[ f.target_object ] [ f.name   ] [clazz].update( methods )
                    if isinstance(f, Constructor): classes[ f.class_name    ] [ '<init>' ] [clazz].update( methods )
        else:
            if not f.is_api and f.called:
                for clazz, methods in f.called.iteritems():
                    if isinstance(f, Function):    
                        if not '$' in f.name:      classes[ f.target_object ] [ f.name   ] [clazz].update( methods )
                    if isinstance(f, Constructor): classes[ f.class_name    ] [ '<init>' ] [clazz].update( methods )

    callgraph = pydot.Dot(graph_type='digraph')
    clusters = {}
   
    # Firt pass. Create the nodes and clusters
    for clazz, methods in sorted(classes.iteritems()):
        clazz_safe = re.sub('[.$]', '_', clazz)
        
        if use_colors: color = '#%06X' % (hash(clazz_safe) % 0xFFFFFF)
        else:          color = '#%06X' % (0xFFFFFF)

        if use_clusters:
            if clazz_safe not in clusters: clusters[clazz_safe] = pydot.Cluster(clazz_safe, label = clazz, style='bold', color=color)
            cluster = clusters[clazz_safe]

        for method, called in sorted(methods.iteritems()):
            method_safe = re.sub('[.$]', '_', method)

            if use_clusters:   cluster.add_node(pydot.Node('%s_%s' % (clazz_safe, method_safe), label = '%s()' % method, shape='box'))
            else:            callgraph.add_node(pydot.Node('%s_%s' % (clazz_safe, method_safe), label = '%s()' % method, shape='box'))
            
            for class_called, methods_called in sorted(called.iteritems()):
                class_called_safe = re.sub('[.$]', '_', class_called)
        
                if use_colors: color = '#%06X' % (hash(class_called_safe) % 0xFFFFFF)
                else:          color = '#%06X' % (0xFFFFFF)

                if use_clusters:
                    if class_called_safe not in clusters: clusters[class_called_safe] = pydot.Cluster(class_called_safe, label = class_called, style='bold', color=color)
                    clusterX = clusters[class_called_safe]
                      
                for method_called in sorted(methods_called):
                    method_called_safe = re.sub('[.$]', '_', method_called)
                
                    if use_clusters:  clusterX.add_node(pydot.Node('%s_%s' % (class_called_safe, method_called_safe), label = '%s()' % method_called, shape='box'))
                    else:            callgraph.add_node(pydot.Node('%s_%s' % (class_called_safe, method_called_safe), label = '%s()' % method_called, shape='box'))
                
                if use_clusters: callgraph.add_subgraph(clusterX)

            if use_clusters: callgraph.add_subgraph(cluster)

    # Second pass. Create invisible edges between nodes in clusters to allign them vertically
    if vertical:
        for key, cluster in clusters.iteritems():
            nodes = sorted(cluster.get_nodes(), key=lambda x: x.get_label())
            for nodeA, nodeB in zip ( nodes, nodes[1:] ):
                cluster.add_edge(pydot.Edge(nodeA,nodeB, style='invis'))



    # Third pass. Create the edges between the nodes
    for clazz, methods in sorted(classes.iteritems()):
        clazz_safe = re.sub('[.$]', '_', clazz)

        for method, called in sorted(methods.iteritems()):
            method_safe = re.sub('[.$]', '_', method)           
            
            for class_called, methods_called in sorted(called.iteritems()):
                class_called_safe = re.sub('[.$]', '_', class_called)
                      
                for method_called in sorted(methods_called):
                    method_called_safe = re.sub('[.$]', '_', method_called)
                
                    if use_colors: color = '#%06X' % (hash(clazz_safe) % 0xFFFFFF)
                    else:          color = '#%06X' % (0xFFFFFF)
                    callgraph.add_edge(pydot.Edge('%s_%s' % (clazz_safe, method_safe), '%s_%s' % (class_called_safe, method_called_safe), style='dashed', penwidth='0.5', color=color  ))

#    if vertical:
#        callgraph.set_ranksep('0.75')
#        callgraph.set_nodesep('3.00')

    if splines:
        callgraph.set_splines(splines)

    return callgraph



functions     = []
constructors  = []


def main():
    parser = argparse.ArgumentParser(description="Load an existing log directory into memory and dump an ipython shell.")
    parser.add_argument("--logdir",  action="store",     required=True, help="Log directory")
    parser.add_argument("--colorize",action="store_true",required=False,help="Colorize output")
    args = parser.parse_args() 
    
    if args.colorize: 
        global colorize
        colorize = True

    logger = logging.getLogger('trace')
    logger.setLevel(logging.DEBUG)
    formatter  = logging.Formatter('[%(asctime)s   %(name)s] %(message)s')
    consoleLogger = logging.StreamHandler()
    consoleLogger.setLevel(logging.INFO)
    consoleLogger.setFormatter(formatter)
    logger.addHandler(consoleLogger)

    api_classes = load_api()

    traces = load_dir(args.logdir, api_classes, logger)
   
    fnames = Counter()
    cnames = Counter()
#   rnames = Counter()

    global functions
    global constructors

    failures      = []
    for key, value in traces.iteritems():
        fnames += Counter(value.get_function_names())
        cnames += Counter(value.get_constructor_names())
#       rnames += Counter(value.get_reflected_names())
        functions    += value.functions
        constructors += value.constructors
        failures     += value.get_failures()

    fnames = dict(fnames)
    cnames = dict(cnames)
#   rnames = dict(rnames)

#   # TODO Not sure if necessary, but this does not include recursive reflection calls.
#   reflected = [x.reflected_method for x in functions if x.reflected_method]

    print "Dropping an ipython shell. You can now play with the traces."
    print
    ipshell()
    

if __name__ == "__main__":
    main()
