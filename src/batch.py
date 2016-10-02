#!/usr/bin/python

import subprocess
import os

indir   = '/mnt/misc/working/tap/apks/andrubis/goodware/'
outdir  = '/mnt/misc/working/tap/apks.results/andrubis.very.naive/goodware/'
analyze = '/mnt/misc/working/tap/src/analyze.py'

def is_apk(filename):
    p = subprocess.Popen(['file', filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if 'Zip archive data' in out: return True
    return False

for dirpath, dirnames, filenames in os.walk(indir):
    for filename in filenames:

        if is_apk( os.path.join(dirpath, filename)):

            args = '%s --input %s --output %s --nowindow' % (analyze, os.path.join(dirpath, filename), outdir)
            print args
            os.system(args)

