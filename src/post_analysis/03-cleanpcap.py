#!/usr/in/python

import os
import subprocess

def post_analysis(apk, logbase, static_analysis, logger):

    traffic = os.path.join(logbase,'traffic.pcap')
    traffic_new = os.path.join(logbase,'network-dump.pcap')

    # Remove local traffic (ADB stuff)
    cmd = ['/usr/sbin/tcpdump', '-nn', '-s0', '-r', traffic, '-w', traffic_new, 'not host 10.0.2.2']
    p = subprocess.Popen(cmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    p.communicate()

    # Remove original traffic.pcap
    os.remove(traffic)

    # Don't really care if this failed or not :)


