#!/usr/bin/python

def void():
    pass
try:
    try:
        from IPython.Shell import IPShellEmbed
        ipshell = IPShellEmbed(argv=[])
    except:
        from IPython.frontend.terminal.embed import InteractiveShellEmbed
        ipshell = InteractiveShellEmbed()
except:
    # no ipython
    ipshell = void
