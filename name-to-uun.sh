#!/bin/bash

# Script to flip a non-uun account to a uun based account.
# Usage: sudo sh -x /Path/To/Script name uun

name=$1
uun=$2

if ! test -d /Users/${name}
then
echo "Source directory /Users/${name} doesn't exist."
exit 1;
else
echo "Source directory /Users/${name} found."
fi

uun_test=$(id ${uun} | grep "no such user")

if [ -z "${uun_test}" ] || [ "${uun_test}" == '' ]; then
echo "Target account ${uun} found."
else
echo "Target account ${uun} doesn't exist."
exit 1;
fi

echo changing user folder ${uun} to ${uun}.old
mv /Users/${uun} /Users/${uun}.old

echo changing user folder ${name} to ${uun}
mv /Users/${name} /Users/${uun}

echo removing the old ${name} account entry
dscl . -delete /Users/${name}

echo setting ownership for ${uun} on /Users/${uun}
chown -R ${uun} /Users/${uun}

exit 0;