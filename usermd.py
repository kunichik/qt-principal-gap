"""Moves the user's ~/.claude/CLAUDE.md aside for an isolated Claude run, under a lock, so the
harness and the judge can never interleave their move/restore."""
import contextlib, fcntl, os, sys, time
from pathlib import Path
ROOT = Path(os.environ.get("QTEXP_ROOT", Path(__file__).resolve().parent))  # experiment root

USER_MD = Path.home() / ".claude/CLAUDE.md"
ASIDE = Path.home() / ".claude/CLAUDE.md.aside-for-qtexp"
LOCK = ROOT / ".usermd.lock"


def _restore():
    """Puts the moved file back; never overwrites a CLAUDE.md written in the meantime."""
    if not ASIDE.exists():
        return
    if USER_MD.exists():
        keep = USER_MD.with_name(f"CLAUDE.md.aside-for-qtexp.{int(time.time())}")
        ASIDE.rename(keep)
        print(f"usermd: {USER_MD} was recreated during the run; the original is in {keep}",
              file=sys.stderr)
    else:
        ASIDE.rename(USER_MD)


@contextlib.contextmanager
def user_md_aside():
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)  # held for the whole isolated run
        _restore()                      # left over from a crashed run
        moved = USER_MD.exists()
        if moved:
            USER_MD.rename(ASIDE)
        try:
            yield
        finally:
            if moved:
                _restore()


def restore_if_crashed():
    with open(LOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        _restore()
