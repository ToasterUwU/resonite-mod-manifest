#!/usr/bin/env bash

# Usage: ./validate_hash.sh <url>

set -e

if [ -z "$1" ]; then
	echo "Usage: $0 <url>"
	exit 1
fi

url="$1"
filename="downloaded_file_$$"

# Download the file
curl -L -o "$filename" "$url"

# Get sha256 hash
sha256sum "$filename" | awk '{print $1}'

# Delete the file
rm "$filename"
