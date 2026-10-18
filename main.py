"""
Entry point.

    python main.py            # one pass (manual / fallback)
    python main.py --ci-loop  # CI mode: loop a pass every tick until the day is
                              #   done or the time cap is hit, then exit cleanly;
                              #   the next queued block takes over (6h+6h style)
    python main.py --loop     # local continuous loop (polls every minute)
"""
import sys
import time as _time
from datetime import datetime

from config import (TZ, WORK_DAYS, CI_LOOP_TICK_SECONDS, CI_MAX_RUN_SECONDS,
                    CI_LOOP_UNTIL)
from monitor import run_once


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
            print("Time cap reached — exiting; the next queued block continues.")
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
