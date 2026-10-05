"""Runs `python3 -m app.domains.run.sidecar` (ADR-0008) and exits when the desktop shell goes away.

The shell holds the write end of our stdin pipe. When the shell exits for any reason (even SIGKILL) the pipe
closes, stdin reaches EOF, and this process exits, so the sidecar never outlives the app.
"""
import os
import runpy
import sys
import threading


def _watch_parent():
    try:
        while sys.stdin.buffer.read(4096):
            pass
    finally:
        os._exit(0)


if __name__ == "__main__":
    threading.Thread(target=_watch_parent, daemon=True).start()
    sys.argv[0] = "app.domains.run.sidecar"
    runpy.run_module("app.domains.run.sidecar", run_name="__main__", alter_sys=True)
