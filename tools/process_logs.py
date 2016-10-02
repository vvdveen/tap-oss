#!/usr/bin/python

import os
import re
import sys
import argparse

from collections import defaultdict

from dynamic import SIMULATIONS

keywords_local = SIMULATIONS
keywords_local.append('complete')

keywords_andrubis = ['common-only',
                     'broadcast-only',
                     'activities-only',
                     'services-only',
                     'monkey-only',
                     'everything']

#######################################################
# Post process test results
#
# Loop over the log directories in <outdir>. For each logdir, this script
# displays the code coverage and some boolean values:
# - ANR         Did the app receive an ANR during stimulation?
# - died        Did the app die during stimulation? This may indicate a bug in
#               the VM modifications
# - exception   Did the app ran into an uncaught exception? This indicates a
#               faulty app (unexpected exception not caught)
# - incomplete  Did the coverage script ran into lines that couldn't be parsed?
#               This indicates incomplete dump traces, which occur when the
#               traces were not closed before being pulled out. This may
#               indicate a bug in the VM.
#
# Two tables will be printed, one for conservative code coverage computation,
# and one for naive code coverage computation.
#
# This script expects that log directories have a md5sum filename.

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
    

coverage_filename_parser = re.compile('^coverage\..*$')

andrubis_logdir = re.compile('[a-fA-F\d]{32}')
local_logdir    = re.compile('.*\.\d{4}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{5}')

coverage_parser = re.compile('# -> Code coverage:\s+(.*)% \(\s*(\d+) of \s*(\d+)\)( \((.*)\)\s*\((.*)\))?')

results = []

def parse(outdir, keywords):

    for dirpath, dirnames, filenames in sorted(os.walk(outdir)):

        # We are searching for log directories.
        # - Andrubis: <md5sum>
        # - Local:    <original-filename>.<timestamp>
        basename = os.path.basename(dirpath)

        if andrubis_logdir.search(basename) or local_logdir.search(basename):
            result = Result(basename)

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
                            else:
                                if 'complete' in keywords: keyword = 'complete'
                                else:                      keyword = 'everything'

                            result.coverages[ (keyword, naive) ] = coverage
            
            results.append(result)

    return results
        
def display(results, naive, breakdown, keywords, cdf):

    coverages = defaultdict(float)

    if breakdown:
        coverages_total = {}
        for keyword in keywords:
            coverages_total[keyword] = 0
    else:
        coverages_total = 0
        ANRs        = 0
        dead        = 0
        exceptions  = 0
        incompletes = 0
        vmcrashes   = 0


    i = 0

    if naive: sys.stdout.write('-----------------COVERAGES-NAIVE-')
    else:     sys.stdout.write('-----------------COVERAGES-------')

    
    if breakdown: 
        print '-'*137,
        print
        print 'filename                        |',
        for keyword in keywords:
            sys.stdout.write('%s|' % keyword.rjust(6))
        print
        print '--------------------------------+',
        for keyword in keywords:
            if len(keyword) > 6: sys.stdout.write('-'*len(keyword) + '+')
            else:                sys.stdout.write('-'*6            + '+')
        print

    else:
        print '-'*83
        print 'filename                        | coverage | calls of total |     ANR |    died | exception | incomplete | vmcrash |'
        print '--------------------------------+----------+----------------+---------+---------+-----------+------------+---------+'

    for result in results:
        sys.stdout.write('%s|' % result.filename.ljust(32)[:32])

        if breakdown:

            # first check if there is at least one coverage object for this result
            coverage_found = False
            for keyword in keywords:
                if result.coverages.get( (keyword, naive) ):
                    coverage_found = True
            
            if coverage_found:
                for keyword in keywords:
                    coverage_obj = result.coverages.get( (keyword, naive) )
                    if coverage_obj: coverage = coverage_obj.coverage
                    else:            coverage = 0
                    c = '%6.2f' % coverage
                            
                    if len(keyword) > 6: sys.stdout.write('%s|' % c.rjust(len(keyword)))
                    else:                sys.stdout.write('%s|' % c.rjust(6))

                    coverages_total[keyword] += coverage
                print
                i += 1
            else:
                for keyword in keywords:
                    if len(keyword) > 6: sys.stdout.write('%s|' % 'xxx.xx'.rjust(len(keyword)))
                    else:                sys.stdout.write('%s|' % 'xxx.xx'.rjust(6))

                print

        else:
            if 'complete' in keywords: coverage_obj = result.coverages.get( ('complete', naive) )
            else:                      coverage_obj = result.coverages.get( ('everything', naive) )
            if coverage_obj: 
                print '%9.4f | %5d of %5d | %7s | %7s | %9s | %10s | %7s |' % (
                                                                                       coverage_obj.coverage,
                                                                                   coverage_obj.f_executed,
                                                                                   coverage_obj.f_found,
                                                                                   result.ANR,
                                                                                   result.died,
                                                                                       result.exception,
                                                                               result.incomplete,
                                                                                   result.vmcrash)
                coverages_total += coverage_obj.coverage
                if result.ANR:        ANRs        += 1
                if result.died:       dead        += 1
                if result.exception:  exceptions  += 1
                if result.incomplete: incompletes += 1
                if result.vmcrash:    vmcrashes   += 1
                i += 1

#               coverages[ int(round(coverage_obj.coverage)) ] += 1
                coverages[ coverage_obj.coverage ] += 1
            else:
                print ' xxx.xxxx | xxxxx of xxxxx | xxxxxxx | xxxxxxx | xxxxxxxxx | xxxxxxxxxx | xxxxxxx'


    if breakdown:
        average = {}
        if i > 0:
            for keyword in keywords:
                average[keyword] = coverages_total[keyword] / i
        else:
            for keyword in keywords:
                average[keyword] = -1.0


        print '--------------------------------+',
        for keyword in keywords:
            if len(keyword) > 6: sys.stdout.write('-'*len(keyword) + '+')
            else:                sys.stdout.write('-'*6            + '+')
        print

        print 'average                         |',
        for keyword in keywords:
            c = '%6.2f' % average[keyword]
                    
            if len(keyword) > 6: sys.stdout.write('%s|' % c.rjust(len(keyword)))
            else:                sys.stdout.write('%s|' % c.rjust(6))

            coverages_total[keyword] += coverage
            i += 1
        print
        print
        
    else:
        if i > 0:
            average = coverages_total / i
            percentage_anrs       = float(ANRs)       / i * 100.0
            percentage_deads      = float(dead)       / i * 100.0
            percentage_exception  = float(exceptions) / i * 100.0
            percentage_incomplete = float(incompletes)/ i * 100.0
            percentage_vmcrashes  = float(vmcrashes)  / i * 100.0
        else:
            average               = -1.0
            percentage_anrs       = -1.0
            percentage_deads      = -1.0
            percentage_exception  = -1.0
            percentage_incomplete = -1.0
            percentage_vmcrashes  = -1.0

        print '--------------------------------+----------+----------------+---------+---------+-----------+------------+---------+'
        print 'average (only for completed)    |%9.4f |                | %6.2f%% | %6.2f%% | %8.2f%% | %9.2f%% | %6.2f%% |' % (average, percentage_anrs, percentage_deads, percentage_exception, percentage_incomplete, percentage_vmcrashes)
        print


    if cdf:
        s = sum(coverages.values())
        p = 0.0
        
        print '# %s %s' % ('Percentage'.rjust(10), 'Coverage'.rjust(20))
        for key, value in sorted(coverages.iteritems()):
            p += value/ float(s)
            print '  %10f %20f' % (p*100, key)

 #       print '# %s %s' % ('Coverage'.rjust(10), 'Hits'.rjust(20))
 #       for key, value in sorted(coverages.iteritems()):
 #               print '  %10f %20d' % (key, value)



def main():
    parser = argparse.ArgumentParser(description='Process a batch of log directories')
    parser.add_argument('--input',    action = 'store',      required = True,                   help = 'Directory containing the analysis output directories')
    parser.add_argument('--naive',    action = 'store_true', required = False, default = False, help = 'Display naive code coverage instead of conservative')
    parser.add_argument('--breakdown',action = 'store_true', required = False, default = False, help = 'Display coverage per simulation technique')
    parser.add_argument('--andrubis', action = 'store_true', required = False, default = False, help = 'Process Andrubis output files')
    parser.add_argument('--cdf',      action = 'store_true', required = False, default = False, help = 'Print the CDF table')

    args = parser.parse_args() 
    outdir    = args.input
    naive     = args.naive
    breakdown = args.breakdown
    andrubis  = args.andrubis
    cdf       = args.cdf

    if andrubis: keywords = keywords_andrubis
    else:        keywords = keywords_local

    results = parse(outdir, keywords)
    display(results, naive, breakdown, keywords, cdf)


if __name__ == '__main__':
    main()
