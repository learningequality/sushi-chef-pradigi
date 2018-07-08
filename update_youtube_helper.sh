#!/bin/bash
set -e

echo 'Copying latest youtube.py from kollivier github'
git clone git@github.com:kollivier/pressurecooker.git
cd pressurecooker/
git checkout youtube_info
cp pressurecooker/youtube.py ../youtube_helper.py
cd ..
rm -rf pressurecooker

