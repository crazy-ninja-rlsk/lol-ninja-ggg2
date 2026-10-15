"""
Entry point.

    python main.py          # one pass (used by the scheduled CI job every 20 min)
    python main.py --loop   # local continuous loop (polls every minute)
"""
import sys
import time as _time

from config import TZ
from monitor import run_once


def main():
    if "--loop" in sys.argv:
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
