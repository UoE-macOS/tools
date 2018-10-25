#!/bin/bash
#
# Generic package preinstall check (Updated 02.08.17).

# Manually set the package name, version and an application name used for the ps command.


PkgName=`basename "$1"`
PkgVersion=`echo "$1" | awk -F "-" '{print $2}'`
AppPath=`pkgutil --payload-files "$1"  | grep ".app" | grep -v "/Contents" | grep -v "._"` # For a single app this works
AppPathFix=`echo "$AppPath" | sed 's/^[./] *//g'` # Remove leading .
AppName=`basename "$AppPath"`

# Find the currently-installed version of the app. Not all applications have the 
# "CFBundleShortVersionString" key, where this isn't available use "CFBundleVersionString".
AppVersion=`defaults read "${AppPathFix}/Contents/Info" CFBundleShortVersionString`

# In case one or both version numbers are in the format N.N.N, the following commands make both the
# install package version and the currently-installed app version into unary numbers by
# removing the second decimal point in order to make the Check_Version comparison much simpler.
# If a version is in the format N.N, the $3 doesn't exist, so is simply ignored.

PkgMajorVersion=`echo "$PkgVersion" | awk -F "." '{print $1}'`
echo "****** $PkgMajorVersion ******"
PkgMinorVersion=`echo "$PkgVersion" | awk -F "." '{print $2$3}'`
echo "****** $PkgMinorVersion ******"
AppMajorVersion=`echo "$AppVersion" | awk -F "." '{print $1}'`
echo "****** $AppMajorVersion ******"
AppMinorVersion=`echo "$AppVersion" | awk -F "." '{print $2$3}'`
echo "****** $AppMinorVersion ******"
#PkgVersionUnary=`echo "$PkgVersion" | awk -F "." '{print $1 "." $2$3}'`
#AppVersionUnary=`echo "$AppVersion" | awk -F "." '{print $1 "." $2$3}'`

# Check whether the software being installed is currently running on the target Mac.

Check_Running ()
{
# To find if the app is running, use:
ps -A | grep "${AppName}" | grep -v "grep" > /tmp/RunningApps.txt

if grep -q $AppName /tmp/RunningApps.txt;
then
	echo "******Application is currently running on target Mac. Installation of "${PkgName}" cannot proceed.******"
	exit 1;
else
    echo "******Application is not running on target Mac. Proceeding...******"
    exit 0
fi
}

# Compare the version of the install package to the currently-installed app and fail if the same or older.

Check_Version ()
{
#if [ $(echo "${PkgVersionUnary} = ${AppVersionUnary}" ) ] || [ $(echo "${PkgVersionUnary} > ${AppVersionUnary}" | bc ) -ne 1 ]

if [ $PkgMajorVersion -eq $AppMajorVersion ] && ! [ $PkgMinorVersion -ge $AppMinorVersion ] || [ $PkgMajorVersion -lt $AppMajorVersion ] || [ $PkgMajorVersion -eq $AppMajorVersion ] && [ $PkgMinorVersion -eq $AppMinorVersion ]

then
    touch /Library/MacMDP/Receipts/${PkgName}.mdpreceipt
	echo "******The installation package is at version "$PkgVersion" and the currently-installed app is at version "$AppVersion". This installation "${PkgName}" cannot continue******"
	exit 1;
else
	echo "******The app is either not installed on the target Mac or is at an older version than the install package. Proceeding with installation...******"
	Check_Running
	exit 0;
fi
}

Check_Version

exit 0;
