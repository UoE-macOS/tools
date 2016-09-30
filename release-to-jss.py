#!/usr/bin/env python

## release-to-jss.py: push a tagged release from git to the JSS

import jss
import sys
import time
import subprocess
import dircache
import io
import re
from string import Template
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
  if not ( options.script_file or options.push_all ):
    print "You need to specify a script file to push, or --all"
    sys.exit(255)
  if not options.script_tag:
    print "Please specify a tag to push to the JSS"
    sys.exit(255)

  # Create a new JSS object
  jss_prefs = jss.JSSPrefs()
  _jss = jss.JSS(jss_prefs)
  print "Pushing tag %s to jss: %s" % (options.script_tag, jss_prefs.url) 
  try:
    switch_to_tag(options.script_tag)
    if not options.push_all:
      if not options.script_name:
        print "No name specified, assuming %s" % options.script_file
	options.script_name=options.script_file
      jss_script = load_script(_jss, options.script_name)
      script_info = get_git_info(_jss, options.script_file, options.script_tag) 
      update_script(jss_script, options.script_file, script_info)
      save_script(jss_script)
    else:
      print "Trying to push all script files"
      # Find out the names of all potential files on the current directory
      all_files = [ x for x in dircache.listdir(".")\
                    if not re.match('^\.', x)\
                    and re.match('.*\.(sh|py|pl)$', x) ]
      for this_file in all_files:
        try:
          print "Loading %s" % this_file
          jss_script = load_script(_jss, this_file)
        except:
          print "Skipping %s: couldn't load it from the JSS" % this_file
          continue
        script_info = get_git_info(_jss, this_file, options.script_tag)
        update_script(jss_script, this_file, script_info)
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
    subprocess.check_call([ "git", "stash", "-q" ])
    subprocess.check_call([ "git", "checkout", "tags/" + script_tag, "-b", "release-" + script_tag, "-q" ])
  except:
    print "Couldn't switch to tag %s: are you sure it exists?"
    raise
  else:
    return True

def cleanup(script_tag):
  print "Cleaning up"
  subprocess.check_call([ "git", "checkout", "master" ])
  subprocess.check_call([ "git", "branch", "-d", "release-"+script_tag, "-q"])
  if subprocess.check_output([ "git", "stash", "list" ]) != "":
    out = subprocess.check_call([ "git", "stash", "pop", "-q" ])

  
  
def update_script(jss_script, script_file, script_info, should_template=True):
  # Update the notes field to contain the full GIT log for this
  # script. I don't know what the size limit on this is...
  jss_script.find('notes').text = script_info['LOG']
  print jss_script.find('notes')
  
  # Update the script - we need to write a base64 encoded version
  # of the contents of script_file into the 'script_contents_encoded'
  # element of the script object
  f = io.open(script_file, 'r', encoding="utf-8")
  
  if should_template == True:
    print "Templating script..."
    jss_script.find('script_contents_encoded').text = b64encode(template_script(f.read(), script_info).encode('utf-8'))
  else:
    jss_script.find('script_contents_encoded').text = b64encode(f.read().encode('utf-8'))
  f.close()
  
  # Only one of script_contents and script_contents_encoded should be sent
  # so delete the one we are not using.
  jss_script.remove(jss_script.find('script_contents'))

def get_git_info(jss_prefs, script_file, script_tag):
  git_info={}
  git_info['VERSION'] = script_tag
  git_info['ORIGIN'] = subprocess.check_output(["git", "config", "--get", "remote.origin.url"]).strip()
  git_info['DATE'] = time.strftime("%c")
  git_info['USER'] = jss_prefs.user
  git_info['LOG'] = subprocess.check_output(["git", "log", '--format=%h - %cD %ce: %n %s%n', script_file]).strip()
  return git_info

def template_script(text, script_info):

  # We need to subclass Template in order to change the delimiter
  class JSSTemplate(Template):
    delimiter = '@@'
    
  t = JSSTemplate(text)
  
  try:
    out = t.safe_substitute(script_info)
  except:
    print "Failed to template this script!" 
    raise
  return out


  
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
