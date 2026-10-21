"""Moves the user's ~/.claude/CLAUDE.md aside for an isolated Claude run, under a lock, so the
harness and the judge can never interleave their move/restore."""
import contextlib, fcntl
import os
from pathlib import Path
ROOT = Path(os.environ.get("QTEXP_ROOT", Path(__file__).resolve().parent))  # experiment root

USER_MD = Path.home() / ".claude/CLAUDE.md"
ASIDE = Path.home() / ".claude/CLAUDE.md.aside-for-qtexp"
LOCK = ROOT / ".usermd.lock"


@contextlib.contextmanager
def user_md_aside():
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)  # held for the whole isolated run
        if ASIDE.exists() and not USER_MD.exists():
            ASIDE.rename(USER_MD)        # left over from a crashed run
        USER_MD.rename(ASIDE)
        try:
            yield
        finally:
            ASIDE.rename(USER_MD)


def restore_if_crashed():
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        if ASIDE.exists() and not USER_MD.exists():
            ASIDE.rename(USER_MD)
