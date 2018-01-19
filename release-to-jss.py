#!/usr/bin/env python

## release-to-jss.py: push a tagged release from git to the JSS
import subprocess
import dircache
import io
import re
import argparse
import tempfile
import shutil
from string import Template
from base64 import b64encode
import jss

DESCRIPTION = """A tool to update scripts on the JSS to match a tagged release in a Git repository.

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


EPILOG = """
"""

TMPDIR = None

def _get_args():
    """ Parse arguments from the commandline and return something sensible """

    parser = argparse.ArgumentParser(usage=('release-to-jss.py [-h] [--create] '
                                            '[--all | --file FILE '
                                            '[ --name NAME ] ] TAG'),
                                     description=DESCRIPTION, epilog=EPILOG,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('tag', metavar='TAG', type=str,
                        help=('Name of the TAG in Git. The tag must have been pushed to origin: '
                              'locally committed tags will not be accepted.'))

    parser.add_argument('--name', metavar='NAME', dest='script_name', type=str,
                        help=('Name of the script object in the JSS (if omitted, it is assumed '
                              'that the script object has a name exactly matching FILE)'))

    parser.add_argument('--create', action='store_true', default=False, dest='create_tag',
                        help="If TAG doesn't exist, then create it and push to the server")
                        
    file_or_all = parser.add_mutually_exclusive_group()

    file_or_all.add_argument('--file', metavar='FILE', dest='script_file', type=str,
                             help='File containing the script to push to the JSS')

    file_or_all.add_argument('--all', action='store_true', default=False, dest='push_all',
                             help=('Push every file in the current directory which has '
                                   'a matching script object on the JSS'))

    return parser.parse_args()

class Git2JSSError(BaseException):
    """ Generic error class for this script """
    pass

def _main(options):
    """ Main function """
    global TMPDIR
    TMPDIR = make_temp_dir()

    # --name doesn't make any sense with --all, but argparse won't let us express that with groups
    # so add in a hacky check here
    if options.push_all and options.script_name:
        print "WARNING: --all was specified so ignoring --name option"

    if not tag_exists(options.tag):
        if options.create_tag:
            create_tag(options.tag, "Tagged by Git2JSS")
        else:
            raise Git2JSSError("Tag does not exist. If you want to create it you can "
                               "specify --create on the commandline.")
            
    # Create a new JSS object
    jss_prefs = jss.JSSPrefs()
    _jss = jss.JSS(jss_prefs)
    
    print "Pushing tag %s to jss: %s" % (options.tag, jss_prefs.url)

    try:
        checkout_tag(options.tag)
        if options.push_all:
            files = [x for x in dircache.listdir(".")
                     if not re.match(r'^\.', x)
                     and re.match(r'.*\.(sh|py|pl)$', x)]
        else:
            files = [options.script_file]

        for this_file in files:
            if not options.script_name:
                print "No name specified, assuming %s" % options.script_file
                this_name = options.script_file
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
    """ Create a temporary directory """
    return tempfile.mkdtemp()


def load_script(_jss, script_name):
    """ Load a script from the JSS and return a Script object """
    try:
        jss_script = _jss.Script(script_name)
    except:
        raise
    else:
        print "Loaded %s from the JSS" % script_name
        return jss_script

def checkout_tag(script_tag):
    """ Check out a fresh copy of the tag we are going to operate on
        script_tag must be present on the git master
    """
    origin = subprocess.check_output(["git", "config", "--get",
                                      "remote.origin.url"]).strip()
    if re.search(r'\.git$', origin):
        origin = origin[:-4]
    try:
        print origin
        subprocess.check_call(["git", "clone", "-q", "--branch",
                               script_tag, origin + ".git", TMPDIR])
    except subprocess.CalledProcessError:
        print "Couldn't check out tag %s: are you sure it exists?" % script_tag
        raise
    else:
        return True

def tag_exists(tag):
    """ Check whether a tag exists. Returns True or false """
    tags = subprocess.check_output(['git', 'tag']).split('\n')
    return tag in tags

    
def create_tag(tag_name, msg):
    """ Create tag if it doesn't exist """
    if tag_exists(tag_name):
        print "Tag %s already exists" % tag_name
        raise Git2JSSError("Tag %s already exists" % tag_name)
    
    subprocess.check_call(['git', 'tag', '-a', tag_name, '-m', msg])
    subprocess.check_call(['git', 'push', 'origin', tag_name])

    print "Tag %s pushed to master"
    

#def cleanup(script_tag):
    # This function is never called but could be used if we supported
    # pushing a tag that hasn't been pushed to master yet, perhaps for
    # development purposes.
#    print "Cleaning up"
#    subprocess.check_call(["git", "checkout", "master"])
#    if "release-"+script_tag in subprocess.check_output(["git", "branch"]):
#        subprocess.check_call(["git", "branch", "-d", "release-"+script_tag, "-q"])
#    if subprocess.check_output(["git", "stash", "list"]) != "":
#        out = subprocess.check_call(["git", "stash", "pop", "-q"])

def cleanup_tmp():
    """ General cleanup tasks. """
    print "Cleaning up..."
    shutil.rmtree(TMPDIR)
    print "Cleaned up"

def update_script(jss_script, script_file, script_info, should_template=True):
    """ Update the notes field to contain the git log,
        and, if requested, template the script
    """
    # Add log to the script_info
    jss_script.find('notes').text = script_info['LOG']

    # Update the script - we need to write a base64 encoded version
    # of the contents of script_file into the 'script_contents_encoded'
    # element of the script object
    with io.open(TMPDIR + "/" + script_file, 'r', encoding="utf-8") as handle:
        if should_template:
            print "Templating script..."
            jss_script.find('script_contents_encoded').text = b64encode(
                template_script(handle.read(), script_info).encode('utf-8'))
        else:
            print "No templating requested."
            jss_script.find('script_contents_encoded').text = b64encode(
                handle.read().encode('utf-8'))

    # Only one of script_contents and script_contents_encoded should be sent
    # so delete the one we are not using.
    jss_script.remove(jss_script.find('script_contents'))


def get_git_info(jss_prefs, script_file, script_tag):
    """ Populate a dict with information about the script """
    git_info = {}
    git_info['VERSION'] = script_tag
    git_info['ORIGIN'] = subprocess.check_output(["git", "config",
                                                  "--get", "remote.origin.url"],
                                                 cwd=TMPDIR).strip()
    git_info['PATH'] = script_file
    git_info['DATE'] = subprocess.check_output(["git", "log",
                                                "-1", '--format="%ad"',
                                                script_file], cwd=TMPDIR).strip()
    git_info['USER'] = jss_prefs.user
    git_info['LOG'] = subprocess.check_output(["git", "log",
                                               '--format=%h - %cD %ce: %n %s%n',
                                               script_file], cwd=TMPDIR).strip()
    return git_info


def template_script(text, script_info):
    """ Template the script. We use a custom delimiter to
    reduce the risk of collisions """

    class JSSTemplate(Template):
        """ Template subclass with a custom delimiter """
        delimiter = '@@'

    tmpl = JSSTemplate(text)
    out = None

    try:
        out = tmpl.safe_substitute(script_info)
    except:
        print "Failed to template this script."
        raise

    return out


def save_script(jss_script):
    """ Save jss_script to the JSS """
    try:
        jss_script.save()
    except:
        print "Failed to save the script to the jss"
        raise
    else:
        print "Saved %s to the JSS." % jss_script.find('name').text
        return True


if __name__ == "__main__":
    _main(_get_args())
