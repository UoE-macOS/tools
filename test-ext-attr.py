#!/usr/bin/python
############################################################
# Test whether we can modify the value of a 
# User Extension Attribute in the JSS. As of
# this writing this works in 9.96 but broke some
# time after that.
###########################################################

import random
import string
import sys
import jss

try:
    USER = sys.argv[1]
    ATTR = sys.argv[2]
except IndexError:
    print "Usage: {} username attributename".format(sys.argv[0])
    print "Use this script to test whether it's possible to modify a User Extension Attribute on a JSS"
    print "User <username> should have <attributename> set to some value that you don't mind losing"
    print "WARNING: we will not set the value back to what it was before!"
    sys.exit(255)
 
jss_prefs = jss.JSSPrefs()
j = jss.JSS(jss_prefs)

user = j.User(USER)

print "Testing Extension Attribute {} on user {}".format(ATTR, USER)
print "Using JSS at ", j.base_url

init_val = user.find(".//extension_attribute[name='{}']/value".format(ATTR)).text
print "Initial value is: ", init_val
newval = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5))

print "Trying to change value to: ", newval

user.find(".//extension_attribute[name='{}']/value".format(ATTR)).text = newval
user.save()

postval = user.find(".//extension_attribute[name='{}']/value".format(ATTR)).text

if postval != newval:
  print "FAILED.\nOriginal value: {}\nCurrent value is: {}\nWe were expecting: {}".format(init_val, postval, newval) 
else:
  print "Yay! We modified attribute {} on user {} on JSS {}".format(ATTR, USER, j.base_url)  
