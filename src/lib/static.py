#!/usr/bin/python

import os
import sys
import hashlib
import datetime
import argparse

import androlyze

class StaticAnalysis:

    def __init__(self, filename = None, output = None):
        self.package_name    = ''
        self.main_activity   = ''
        self.activities      = []
        self.services        = []
        self.receivers       = []
        self.providers       = []
        self.actions         = []
        self.activityactions = {}
        self.categories      = []
        self.md5sum = ''

        if filename: self.apk = os.path.abspath(filename)
        else:        self.apk = ''

        if output: self.output = open(output, 'w')
        else:      self.output = sys.stdout 

    def dump(self):
        print >>self.output, "filename     : %s" % self.apk
        print >>self.output, "md5sum       : %s" % self.md5sum
        print >>self.output, "date         : %s" % datetime.datetime.now().strftime("%A, %d. %B %Y %H:%M:%S")
        print >>self.output, "package      : %s" % self.package_name
        print >>self.output, "main activity: %s" % self.main_activity
        print >>self.output, ""

        print >>self.output, "activities     : %d" % len(self.activities);
        for activity   in self.activities:  
            print >>self.output, "-> %s" % activity 

        print >>self.output, "services       : %d" % len(self.services);
        for service    in self.services:    
            print >>self.output, "-> %s" % service 

        print >>self.output, "receivers      : %d" % len(self.receivers);   
        for receiver   in self.receivers:   
            print >>self.output, "-> %s" % receiver 

        print >>self.output, "providers      : %d" % len(self.providers);   
        for provider   in self.providers:   
            print >>self.output, "-> %s" % provider 

        print >>self.output, "actions        : %d" % len(self.actions);     
        for action     in self.actions:     
            print >>self.output, "-> %s" % action

        print >>self.output, "activityactions: %d" % len(self.activityactions);
        for activity, action in self.activityactions.iteritems():
            print >>self.output, "-> %s: %s" % (activity, action)

        print >>self.output, "categories     : %d" % len(self.categories);
        for category in self.categories:
            print >>self.output, "-> %s" % category

        if self.output != sys.stdout:
            self.output.close()

    def analyse(self):
        self.md5sum          = hashlib.md5(open(self.apk,"rb").read()).hexdigest()
        a = androlyze.APK(self.apk)
        self.package_name    = a.get_package()
        self.main_activity   = a.get_main_activity()
        self.activities      = a.get_activities()
        self.services        = a.get_services() 
        self.receivers       = a.get_receivers()
        self.providers       = a.get_providers()
        self.actions         = a.get_actions()
        self.activityactions = a.get_activityactions()
        self.categories      = a.get_categories()

        if self.package_name   == '': self.package_name  = 'unknown'
        if self.main_activity  == '': self.main_activity = 'unknown'



def parse(path):

    def read_list(f):
        result = []
        while True:
            line = f.readline()
            if not line.startswith('-> '): break
            result.append(line.strip('-> ').strip())

        return line, result

    def read_dict(f):
        result = {}
        while True:
            line = f.readline()
            if not line.startswith('-> '): break
            line = line.strip('-> ').strip()
            key, eq, value = line.partition(':')
            result[key] = eval(value)

        return line, result


    sa = StaticAnalysis()

    try:
        f = open(path)
        while True:
            line = f.readline()
            if line.startswith('filename'):        sa.apk           = line.partition(':')[2].strip()
            if line.startswith('md5sum'):          sa.md5sum        = line.partition(':')[2].strip()
            if line.startswith('package'):         sa.package_name  = line.partition(':')[2].strip()
            if line.startswith('main activity'):   sa.main_activity = line.partition(':')[2].strip()
            if line.startswith('activities'):      line, sa.activities      = read_list(f)
            if line.startswith('services'):        line, sa.services        = read_list(f)
            if line.startswith('receivers'):       line, sa.receivers       = read_list(f)
            if line.startswith('providers'):       line, sa.providers       = read_list(f)
            if line.startswith('actions'):         line, sa.actions         = read_list(f)
            if line.startswith('activityactions'): line, sa.activityactions = read_dict(f)
            if line.startswith('categories'):      line, sa.categories      = read_list(f)

            if not line: break
    except IOError:
        pass

    return sa

def main():
    parser = argparse.ArgumentParser(description="Static analysis")
    parser.add_argument("--input",action="store",required=True, help="Android package (.apk)")

    args = parser.parse_args() 
    apk  = args.input

    sa = StaticAnalysis(apk)
    sa.analyse()
    sa.dump()

if __name__ == "__main__":
    main()
