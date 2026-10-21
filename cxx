#!/bin/sh
exec /usr/bin/clang++ -nostdinc++ -isystem /Library/Developer/CommandLineTools/SDKs/MacOSX26.2.sdk/usr/include/c++/v1 "$@"
