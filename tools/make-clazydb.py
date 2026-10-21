#!/usr/bin/env python3
"""Writes clazydb/compile_commands.json: the build's database without precompiled-header flags.

clazy runs on Homebrew's LLVM, which cannot read a PCH built by another compiler (Apple clang).
Usage: tools/make-clazydb.py [build-dir]   (default: b3)
"""
import json, re, sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
build = root / (sys.argv[1] if len(sys.argv) > 1 else "b3")
db = json.loads((build / "compile_commands.json").read_text())
for e in db:
    c = e["command"]
    c = re.sub(r"-Xclang -include-pch -Xclang \S+", "", c)
    c = re.sub(r"-Xclang -include -Xclang \S+cmake_pch\S*", "", c)
    c = re.sub(r"-include \S+cmake_pch\S*", "", c)
    e["command"] = c
out = root / "clazydb/compile_commands.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(db))
print(f"wrote {out} ({len(db)} entries)")
