import os
from datetime import time
from zoneinfo import ZoneInfo

# Load variables from .env locally (GitHub Actions provides them as env secrets)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# --- Monitored source (identity kept out of the code) ---
SUPPLIER_BASE_URL = os.getenv("SUPPLIER_BASE_URL", "")

# --- Storage ---
DB_NAME = os.getenv("DB_NAME", "monitor.db")

# Keep only this many days of snapshot history (older is pruned daily).
# The product catalog (incl. learned years) persists; only history resets.
RETAIN_DAYS = int(os.getenv("RETAIN_DAYS", "3"))

# Local-only text templates (localized); English defaults live in strings.py
LOCALE_FILE = os.getenv("LOCALE_FILE", "locale.local.json")

# --- Timezone & work window (local time of the monitored market) ---
TZ = ZoneInfo(os.getenv("TZ_NAME", "Europe/Kyiv"))
WORK_DAYS = [0, 1, 2, 3, 4]            # Mon..Fri
WORK_START_TIME = time(9, 0)
WORK_END_TIME = time(19, 30)
EVENING_TIME = time(20, 0)             # second fixed-time slot (TWICE_DAILY)

# --- Tier cadence (minutes) for interval tiers ---
TIER_INTERVAL_MINUTES = {
    "HOT": 20,       # year >= HOT_YEAR — every 20 min
    "HOURLY": 60,    # year == RECENT_YEAR with recent sales — hourly
}
# Fixed-time tier fires at WORK_START_TIME and EVENING_TIME
TWICE_DAILY_TIER = "TWICE_DAILY"
# Once-a-day tier fires at WORK_START_TIME
DAILY_TIER = "DAILY"

# --- Classification by publication year ---
HOT_YEAR = 2026      # this year and newer -> HOT
RECENT_YEAR = 2025   # this exact year -> HOURLY/TWICE_DAILY by recent sales
# older than RECENT_YEAR -> DAILY

# How many trailing working days define "recent sales" for HOURLY promotion
RECENT_SALES_WINDOW_DAYS = 2

# Reports
SEND_DAILY_REPORT = True
TOP_N = 10

# Network
REQUEST_TIMEOUT = 30
FETCH_WORKERS = int(os.getenv("FETCH_WORKERS", "10"))

# --- CI internal loop (works around unreliable Actions cron) ---
# Each CI run loops, calling a pass every CI_LOOP_TICK_SECONDS, until the day is
# done or CI_MAX_RUN_SECONDS elapses (kept under the 6h job cap). Cron only has
# to start a run; the 20-min cadence is held by the loop itself.
CI_LOOP_TICK_SECONDS = int(os.getenv("CI_LOOP_TICK_SECONDS", "300"))   # 5 min
CI_MAX_RUN_SECONDS = int(os.getenv("CI_MAX_RUN_SECONDS", "18000"))     # 5 h
CI_LOOP_UNTIL = time(21, 30)   # stop after evening slot + daily report are done
