#!/bin/sh
# clazy on qtbase files with the build's flags. clazydb/compile_commands.json is the build's database
# with precompiled-header flags removed (a PCH from another compiler can't be read). On macOS with only
# the Command Line Tools, libc++ and the SDK are passed explicitly, as the cxx wrapper does for the build.
ROOT="$(cd "$(dirname "$0")" && pwd)"
SDK="${SDK:-$(xcrun --show-sdk-path 2>/dev/null)}"
RES="${CLANG_RESOURCE_DIR:-$("$(brew --prefix llvm 2>/dev/null)/bin/clang" -print-resource-dir 2>/dev/null)}"
exec clazy-standalone -p "$ROOT/clazydb" --checks="${CLAZY_CHECKS:-level1}" \
  --extra-arg=-resource-dir="$RES" --extra-arg=-isysroot --extra-arg="$SDK" \
  --extra-arg=-nostdinc++ --extra-arg=-isystem --extra-arg="$SDK/usr/include/c++/v1" \
  --extra-arg=-Wno-unknown-warning-option --extra-arg=-Wno-error "$@"
