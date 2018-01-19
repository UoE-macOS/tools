#!/usr/bin/env python

## release-to-jss.py: push a tagged release from git to the JSS

import jss
import sys
import time
import subprocess
import dircache
import io
import os
import re
import argparse
import tempfile
import shutil
from string import Template
from base64 import b64encode, b64decode
from optparse import OptionParser

description = """A tool to update scripts on the JSS to match a tagged release in a Git repository.

The 'notes' field of the JSS script object will contain the Git log for the corresponding
Script file. Some templating is also carried out.

You need to have the jss-python module installed and configured appropriately to talk to your JSS.
MANY thanks to sheagcraig for that module:  https://github.com/sheagcraig/python-jss

TEMPLATING: The following fields, if present in the script file, will be templated with values from Git:

@@DATE Date of last change
@@VERSION The name of the TAG this file was pushed from
@@ORIGIN Origin URL from Git config
@@PATH The path to the script file relative to the root of the Git repo
@@USER JSS Username used to push the script (from jss-python configuration)

"""


epilog="""
"""

parser = argparse.ArgumentParser(usage='release-to-jss.py [-h] [--all | --file FILE [ --name NAME ] ] TAG', description=description, epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)

parser.add_argument('tag', metavar='TAG', type=str,
                    help=('Name of the TAG in Git. The tag must have been pushed to origin: '
                          'locally committed tags will not be accepted.'))
parser.add_argument('--name', metavar='NAME', dest='script_name', type=str,
                    help=('Name of the script object in the JSS (if omitted, it is assumed '
                          'that he script object has a name exactly matching FILE)'))
fileorall = parser.add_mutually_exclusive_group()
fileorall.add_argument('--file', metavar='FILE', dest='script_file', type=str,
                       help='File containing the script to push to the JSS')
fileorall.add_argument('--all', action='store_true', default=False, dest='push_all',
                       help='Push every file in the current directory which has a matching script object on the JSS')

options = parser.parse_args()

def _main(options):

    global tmpdir, owd
    owd = os.getcwd()
    tmpdir = make_temp_dir()

    # --name doesn't make any sense with --all, but argparse won't let us express that with groups
    # so add in a hacky check here
    if options.push_all and options.script_name:
        print "WARNING: --all was specified so ignoring --name option"
    # Create a new JSS object
    jss_prefs = jss.JSSPrefs()
    _jss = jss.JSS(jss_prefs)
    print "Pushing tag %s to jss: %s" % (options.tag, jss_prefs.url)
    try:
        switch_to_tag(options.tag)
        if options.push_all:
            files = [ x for x in dircache.listdir(".")\
                          if not re.match('^\.', x)\
                          and re.match('.*\.(sh|py|pl)$', x) ]
        else:
            files = [ options.script_file ]
        for this_file in files:
            if not options.script_name:
                print "No name specified, assuming %s" % options.script_file
                this_name=options.script_file
            else:
                this_name = options.script_name
            try:
                print "Loading %s" % this_name
                jss_script = load_script(_jss, this_name)
            except jss.exceptions.JSSGetError:
                print "Skipping %s: couldn't load it from the JSS" % this_name
                continue
            script_info = get_git_info(_jss, this_file, options.tag)
            update_script(jss_script, this_file, script_info)
            save_script(jss_script)
    except:
        print "Something went wrong."
        raise
    finally:
        cleanup_tmp()

def make_temp_dir():
    return tempfile.mkdtemp()


def load_script(_jss, script_name):
   # look up the script in the jss
    try:
        jss_script = _jss.Script(script_name)
    except:
        raise
    else:
        print "Loaded %s from the JSS" % script_name
        return jss_script

def switch_to_tag(script_tag):
    origin = subprocess.check_output(["git", "config", "--get",
                                      "remote.origin.url"]).strip()
    if re.search('\.git$', origin):
        origin = origin[:-4]
    try:
        print origin
        # Check out a fresh copy of the tag we are interested in pushing
        subprocess.check_call([ "git", "clone", "-q", "--branch",
                                script_tag, origin + ".git", tmpdir ])
    except Exception:
        print "Couldn't check out tag %s: are you sure it exists?" % script_tag
        raise
    else:
        return True


def cleanup(script_tag):
    # This function is never called but could be used if we supported
    # pushing a tag that hasn't been pushed to master yet, perhaps for
    # development purposes.
    print "Cleaning up"
    subprocess.check_call([ "git", "checkout", "master" ])
    if "release-"+script_tag in subprocess.check_output([ "git", "branch" ]):
        subprocess.check_call([ "git", "branch", "-d", "release-"+script_tag, "-q"])
    if subprocess.check_output([ "git", "stash", "list" ]) != "":
        out = subprocess.check_call([ "git", "stash", "pop", "-q" ])

def cleanup_tmp():
    print "Cleaning up..."
    shutil.rmtree(tmpdir)
    print "Done."

def update_script(jss_script, script_file, script_info, should_template=True):
    # Update the notes field to contain the full GIT log for this
    # script. I don't know what the size limit on this is...
    jss_script.find('notes').text = script_info['LOG']

    # Update the script - we need to write a base64 encoded version
    # of the contents of script_file into the 'script_contents_encoded'
    # element of the script object
    with io.open(tmpdir + "/" + script_file, 'r', encoding="utf-8") as f:
        if should_template == True:
            print "Templating script..."
            jss_script.find('script_contents_encoded').text = b64encode(template_script(f.read(), script_info).encode('utf-8'))
        else:
            jss_script.find('script_contents_encoded').text = b64encode(f.read().encode('utf-8'))

    # Only one of script_contents and script_contents_encoded should be sent
    # so delete the one we are not using.
    jss_script.remove(jss_script.find('script_contents'))


def get_git_info(jss_prefs, script_file, script_tag):
    git_info={}
    git_info['VERSION'] = script_tag
    git_info['ORIGIN'] = subprocess.check_output(["git", "config",
                                                  "--get", "remote.origin.url"], cwd=tmpdir).strip()
    git_info['PATH'] = script_file
    git_info['DATE'] = subprocess.check_output(["git", "log",
                                                "-1", '--format="%ad"', script_file], cwd=tmpdir).strip()
    git_info['USER'] = jss_prefs.user
    git_info['LOG'] = subprocess.check_output(["git", "log",
                                               '--format=%h - %cD %ce: %n %s%n', script_file], cwd=tmpdir).strip()
    return git_info


def template_script(text, script_info):
    # We need to subclass Template in order to change the delimiter
    class JSSTemplate(Template):
        delimiter = '@@'

    t = JSSTemplate(text)

    try:
        out = t.safe_substitute(script_info)
    except:
        print "Failed to template this script."
        raise
    return out


def save_script(jss_script):
    try:
        jss_script.save()
    except:
        print "Failed to save the script to the jss"
        raise
    else:
        print "Saved %s to the JSS." % jss_script.find('name').text
        return True


_main(options)
