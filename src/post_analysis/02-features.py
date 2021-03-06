#!/usr/bin/python

import argparse 
import logging
import os
import re

import features

import static
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
        parser = argparse.ArgumentParser(description="Get the features of a given log directory.")
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

    logger.info('Populating API classes')
    api_classes = trace.load_api([API])

    logger.info('Parsing trace files')
    traces = trace.load_dir(logdir, api_classes, logger)

    logger.info('Searching for features')
    fs = features.Features(output = os.path.join(logdir,'features.log') )
    fs.get_features(traces, api_classes, static_analysis.package_name)
    fs.dump()

    close_logger(logger)

def post_analysis(apk, logbase, static_analysis, logger):
    main(apk = apk, logdir = logbase, static_analysis = static_analysis, logger = logger)

if __name__ == "__main__":
    main()

