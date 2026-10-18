"""
Entry point.

    python main.py            # one pass (manual / fallback)
    python main.py --ci-loop  # CI mode: loop a pass every tick until the day is
                              #   done or the time cap is hit; on cap, hand off
                              #   to the next block (6h+6h style) via DISPATCH_PAT
    python main.py --loop     # local continuous loop (polls every minute)
"""
import json
import sys
import time as _time
import urllib.request
from datetime import datetime

from config import (TZ, WORK_DAYS, CI_LOOP_TICK_SECONDS, CI_MAX_RUN_SECONDS,
                    CI_LOOP_UNTIL, DISPATCH_PAT, GITHUB_REPOSITORY, WORKFLOW_FILE)
from monitor import run_once


def _dispatch_next():
    """Start the next workflow block immediately (needs a PAT)."""
    if not (DISPATCH_PAT and GITHUB_REPOSITORY):
        print("No DISPATCH_PAT — next block will rely on cron.")
        return
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    body = json.dumps({"ref": "main"}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {DISPATCH_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"Handed off to next block (HTTP {r.status}).")
    except Exception as e:
        print(f"[WARN] handoff dispatch failed: {e}")


def _ci_loop():
    start = _time.monotonic()
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[ERROR] pass failed: {e}")
        now = datetime.now(TZ)
        if now.weekday() not in WORK_DAYS:
            print("Not a work day — exiting loop.")
            return
        if now.time() >= CI_LOOP_UNTIL:
            print("Day finished — exiting loop.")
            return
        if _time.monotonic() - start >= CI_MAX_RUN_SECONDS:
            print("Time cap reached — handing off to the next block.")
            _dispatch_next()
            return
        _time.sleep(CI_LOOP_TICK_SECONDS)


def main():
    if "--ci-loop" in sys.argv:
        _ci_loop()
    elif "--loop" in sys.argv:
        print("Local loop mode (Ctrl-C to stop).")
        while True:
            try:
                run_once()
            except Exception as e:
                print(f"[ERROR] pass failed: {e}")
            _time.sleep(60)
    else:
        run_once()


if __name__ == "__main__":
    main()
