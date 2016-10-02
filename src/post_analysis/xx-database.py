#!/usr/bin/python

import argparse 
import logging
import os
import re


import features
import db 

import static


DATABASE = 'analysis.db'

class Coverage:
    def __init__(self):
        self.coverage = 0.0
        self.f_executed = 0
        self.f_found    = 0
    def __str__(self):
        return 'Code coverage: %15.10f%% (%8d of %8d)' % (self.coverage, self.f_executed, self.f_found)

class Result:
    def __init__(self, filename):
        self.filename = filename
        self.ANR        = False # Did the package ANR during analysis?
        self.died       = False # Was the package killed during analysis?
        self.exception  = False # Was there an uncaught excpetion during analysis?
        self.incomplete = False # Are there incomplete logfiles?
        self.vmcrash    = False # Did the VM crash during analysis?
        self.coverages  = {} 
    def __str__(self):
        return 'Filename: %s, ANR: %s, died: %s, exception: %s, incomplete: %s, vmcrash: %s, coverage: %s' % (self.filename, self.ANR, self.died, self.exception, self.incomplete, self.vmcrash, self.coverages)

def get_coverage_result(outdir):

    coverage_filename_parser = re.compile('^coverage\..*$')
    coverage_parser          = re.compile('# -> Code coverage:\s+(.*)% \(\s*(\d+) of \s*(\d+)\)( \((.*)\)\s*\((.*)\))?')

    result = Result( os.path.basename(os.path.normpath(outdir)) )

    for dirpath, dirnames, filenames in sorted(os.walk(outdir)):

        # Search for the coverage.<timestamp> files
        for filename in filenames:
            if coverage_filename_parser.search(filename):

                naive = False

                f = open( os.path.join(dirpath, filename) )
                for line in f:
                    if 'ANR'                in line: result.ANR        = True
                    if 'Died'               in line: result.died       = True
                    if 'Uncaught Exception' in line: result.exception  = True
                    if 'Could not parse'    in line: result.incomplete = True
                    if 'Empty file'         in line: result.incomplete = True
                    if 'VM Crashed'         in line: result.vmcrash    = True
                
                    if 'naive'              in line: naive = True

                    groups = coverage_parser.search(line)
                    if groups:
                        coverage = Coverage()
                        coverage.coverage   = float(groups.group(1))
                        coverage.f_executed =   int(groups.group(2))
                        coverage.f_found    =   int(groups.group(3))
#                       if groups.group(5) == 'naive': naive = True
#                       else:                          naive = False
                        if groups.group(6): keyword = groups.group(6)
                        else:               keyword = 'everything'

                        result.coverages[ (keyword, naive) ] = coverage
        
    return result

def get_logger():
    # file log format
    formatter  = logging.Formatter('[%(asctime)s   %(name)s] %(message)s')

    # root logger that handles every message.
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # console logger that handles messages to <level>.
    consoleLogger = logging.StreamHandler()

    consoleLogger.setFormatter(formatter)
    consoleLogger.setLevel(logging.INFO)
    logger.addHandler(consoleLogger)

    return logger

def close_logger(logger):
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.flush()
        handler.close()
    logging.shutdown()

def main(apk = None, logdir = None, static_analysis = None, logger = None):
    if not apk or not logdir:
        parser = argparse.ArgumentParser(description="Store output results in database.")
        parser.add_argument("--logdir",    action="store",     required=True, help="Log directory")
        args     = parser.parse_args() 
        logdir   = args.logdir

        # Get filename of the original APK
        apk = os.path.basename( os.path.normpath(logdir) )
        apk = re.sub('\.\d{4}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{6}', '', apk)

        # Get static analysis
        static_analysis = static.parse( os.path.join(logdir,'static.log') )

        # Get logger
        logger = get_logger()

    logger.info("Parsing coverage output")
    coverages = get_coverage_result(logdir)

    logger.info("Parsing feature output")
    fs = features.parse( os.path.join(logdir,'features.log') )

    logger.info("Writing to database")
    database = db.Database(DATABASE)
    database.insert(apk, logdir, static_analysis, coverages, fs)

    close_logger(logger)


def post_analysis(apk, logbase, static_analysis, logger):
    main(apk = apk, logdir = logbase, static_analysis = static_analysis, logger = logger)

if __name__ == "__main__":
    main()

