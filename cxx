#!/bin/sh
# macOS with only the Command Line Tools: Apple clang needs libc++ headers from the SDK.
# The SDK path is resolved (MacOSX.sdk is a symlink) so it matches what a build was made with.
SDK="${SDK:-$(cd "$(xcrun --show-sdk-path)" && pwd -P)}"
exec /usr/bin/clang++ -nostdinc++ -isystem "$SDK/usr/include/c++/v1" "$@"
