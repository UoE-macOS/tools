#!/usr/bin/env python

## release-to-jss.py: push a tagged release from git to the JSS

import jss
import sys
import time
import subprocess
import dircache
from base64 import b64encode, b64decode
from optparse import OptionParser
  
parser = OptionParser()

parser.add_option("-t", "--tag", dest="script_tag",
                  help="Name of the tag to push", metavar="TAG")
parser.add_option("-f", "--file", dest="script_file",
                  help="Name of the local file whose contents we want to push to the JSS", metavar="FILE")
parser.add_option("-n", "--name", dest="script_name",
                  help="Name of the script on the JSS, assumed to be the same as FILE if not provided", metavar="NAME")
parser.add_option("-a", "--all", action="store_true", dest="push_all",  default=False,
                  help="Push ALL scripts in CWD to the JSS, at version TAG, assuming each local script has a matching name on the JSS")
parser.add_option("-q", "--quiet", action="store_false", dest="verbose", default=True, help="don't print status messages to stdout")
parser.description="The script expects that the current working directory is a local git repository in which <file> exists. You need to have the jss-python module installed and configured appropriately to talk to your JSS. MANY thanks to craigsheag for that module:  https://github.com/sheagcraig/python-jss"

(options, args) = parser.parse_args()

def _main(options):
  # For debugging only
  print options

  if not ( options.script_file or options.push_all ):
    print "You need to specify a script file to push, or --all"
    sys.exit(255)
  if not options.script_tag:
    print "Please specify a tag to push to the JSS"
    sys.exit(255)

  # Create a new JSS object
  jss_prefs = jss.JSSPrefs()
  _jss = jss.JSS(jss_prefs)
  try:
    switch_to_tag(options.script_tag)
    if not options.push_all:
      if not options.script_name:
        print "No name specified, assuming %s" % options.script_file
	options.script_name=options.script_file
      jss_script = load_script(_jss, options.script_name)
      update_script(jss_script, options.script_file, options.script_tag)
      save_script(jss_script)
    else:
      # Find out the names of all potential files on the current directory
      all_files = [ x for x in dircache.listdir(".") if \
                    not re.match('^\.', x) \
                    and re.match('.*\.(sh|py|pl)$', x) ]
      for this_file in all_files:
        try:
          jss_script = load_script(_jss, this_file)
        except:
          print "Skipping %s: couldn't load it from the JSS" % this_file
          continue
        update_script(jss_script, options.script_file, options.script_tag)
        save_script(jss_script)
  except:
    print "Something went horribly wrong!"
    raise
  finally:
    cleanup(options.script_tag)

def load_script(_jss, script_name):
   # look up the script in the jss
  try:
    jss_script = _jss.Script(script_name)
  except:
    print "Failed to load script %s from the JSS" % script_name
    raise
  else:
    print "Loaded %s from the JSS" % script_name
    return jss_script

def switch_to_tag(script_tag):
  try:
    subprocess.check_call([ "git", "checkout", "tags/" + script_tag, "-b", "release-" + script_tag ])
  except:
    print "Couldn't switch to tag %s: are you sure it exists?"
    raise
  else:
    return True

def cleanup(script_tag):
  print "Cleaning up"
  subprocess.check_call([ "git", "checkout", "master" ])
  subprocess.check_call([ "git", "branch", "-d", "release-"+script_tag ])

  
def update_script(jss_script, script_file, script_tag):
  
  # Update the notes field - we just prepend a message stating when
  # this push took place.
  msg = "Tag %s pushed from git @ %s\n" % (script_tag, time.strftime("%c"))
  jss_script.find('notes').text = msg + jss_script.find('notes').text
  print jss_script.find('notes')

  # Update the script - we need to write a base64 encoded version
  # of the contents of script_file into the 'script_contents_encoded'
  # element of the script object
  f = open(script_file, 'r')
  jss_script.find('script_contents_encoded').text = b64encode(f.read())
  f.close()
  
  # Only one of script_contents and script_contents_encoded should be sent
  # so delete the one we are not using.
  jss_script.remove(jss_script.find('script_contents'))


def save_script(jss_script):
  try:
    jss_script.save()
  except:
    print "Failed to save the script to the jss"
    raise
  else:
    print "Saved %s to the JSS!" % jss_script.find('name').text
    return True
  

_main(options)
