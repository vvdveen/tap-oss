#!/bin/bash

# Get our local directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Location of new Androguard files
NEW_ANDROGUARD=$DIR/../lib/androguard-1.9
OLD_ANDROGUARD=$(dirname $(which androlyze.py))

output=$(androlyze.py -v 2>/dev/null)
if [ -z "$output" ]; then 
    echo "Androlyze not found. Is Androguard installed and added to the path?"
    exit
fi


if [ "$output" != "Androlyze version 1.9" ]; then
    echo "Androlyze version incorrect. Please install Androguard 1.9."
    exit
fi

function update {
    file=$1

    diff=$(diff $NEW_ANDROGUARD/$file $OLD_ANDROGUARD/$file)
    if [ -n "$diff" ]; then
        read -e -p "Update $file [Y/n]? " yn
        case $yn in
            [Nn]* ) exit;;
        esac
    fi
    cp $NEW_ANDROGUARD/$file $OLD_ANDROGUARD/$file
}

update "androlyze.py"
update "androguard/core/bytecodes/apk.py"
echo "Androguard was updated"
    
