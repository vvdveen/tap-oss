#!/usr/bin/python

import os
import logging
import datetime
import argparse
import imp
import re

from lib.static import  StaticAnalysis
from lib.dynamic import DynamicAnalysis, DynamicOptions, SIMULATIONS

SCRIPT_DIR = './post_analysis/'

def get_logger(name, root):
    # Create a new base log directory for this package where all the log data will be stored.
    logname = os.path.basename(name) + '.' + str(datetime.datetime.now()).replace(' ','.').replace(':','.')
    logbase = os.path.join(root, logname)
#   logbase = root
    os.makedirs(logbase)

    logger = logging.getLogger('package')
    logger.setLevel(logging.DEBUG)

    formatter  = logging.Formatter('[%(asctime)s   %(name)s] %(message)s')
    fileLogger = logging.FileHandler(filename = os.path.join(logbase, 'analysis.log'))
    fileLogger.setLevel(logging.DEBUG)
    fileLogger.setFormatter(formatter)

    consoleLogger = logging.StreamHandler()
    consoleLogger.setLevel(logging.INFO)
    consoleLogger.setFormatter(formatter)

    logger.addHandler(fileLogger)
    logger.addHandler(consoleLogger)

    return logbase, logger

 
class Package():

    def __init__(self, filename, output, 
                       da_options = DynamicOptions()
                ):
        self.filename   = filename
        self.logroot    = output
        self.da_options = da_options

        self.logbase, self.logger = get_logger(self.filename, self.logroot)

        self.result = 'failed'

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            handler.flush()
            handler.close()
        logging.shutdown()

    def post_analysis(self):
        files = os.listdir(SCRIPT_DIR)
        files.sort()
        for f in files:
            if not re.search('^\d+-.*.py$',f): continue
        
            try:
                module_desc = imp.find_module( os.path.splitext(f)[0], [SCRIPT_DIR] )
                module      = imp.load_module( os.path.splitext(f)[0], *module_desc )

                self.logger.info('Executing post analysis script %s' % f)
                module.post_analysis(self.filename, self.logbase, self.sa, self.logger.getChild(f))
            except Exception:
                self.logger.exception('Error in post analysis script %s' % f)


    # Analyse an Android package.
    def analyse(self):
        self.sa = StaticAnalysis (filename = self.filename,
                output   = os.path.join(self.logbase,'static.log'))

        self.da = DynamicAnalysis(filename = self.filename,
                options  = self.da_options,
                logger   = self.logger,
                logbase  = self.logbase)

        try:
            self.logger.info('Starting static analysis')
            self.sa.analyse()
        except Exception, e:
            self.logger.exception('Error in static analysis: %s' % e)
        finally:
            self.sa.dump()

        self.logger.info('Starting dynamic analysis')
        self.da.analyse(self.sa)

        self.logger.info('Starting post analysis')
        self.post_analysis()

        self.result = 'success'
        self.logger.info('Analysis finished succesfully')


def main():
    parser = argparse.ArgumentParser(description='Analyse a package')
    parser.add_argument('--input',    action = 'store',      required = True,                   help = 'Android package (.apk)')
    parser.add_argument('--output',   action = 'store',      required = False, default = '.',   help = 'Output directory')
    parser.add_argument('--nowindow', action = 'store_true', required = False, default = False, help = 'Hide emulator window')
    parser.add_argument('--breakdown',action = 'store_true', required = False, default = False, help = 'Compute code coverage per simulation technique')
    parser.add_argument('--manual',   action = 'store_true', required = False, default = False, help = 'Run manual analysis')

    # Default simulations
    simulations = SIMULATIONS
    if 'manual' in simulations: simulations.remove('manual')

    args = parser.parse_args() 
    if args.manual: simulations = ['manual']

    da_options = DynamicOptions(nowindow = args.nowindow, breakdown = args.breakdown, simulations = simulations)

    p = Package(args.input, args.output, da_options)
    p.analyse()

if __name__ == '__main__':
    main()
