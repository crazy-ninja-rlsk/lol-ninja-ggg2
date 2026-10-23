"""
Single-pass orchestration, designed to be triggered every 20 minutes by cron.

On each invocation it looks at the current local (market) time and decides what
is due:
  - refresh the catalog from the search index (once a day, first run);
  - HOT tier (year >= HOT_YEAR): every 20 min during work hours;
  - HOURLY tier (recent year with recent sales): hourly during work hours;
  - TWICE_DAILY tier (other recent-year): at work start and in the evening;
  - DAILY tier (older): once a day;
  - daily report: once, after the work window ends.

State (last-run per tier, fired daily slots, snapshot history) lives in the DB,
which is persisted between runs by the CI cache. This mimics one continuous
loop without a long-running process.
"""
from datetime import datetime, timedelta

from config import (TZ, WORK_DAYS, WORK_START_TIME, WORK_END_TIME, EVENING_TIME,
                    REPORT_TIME, ROUND_THE_CLOCK, TIER_INTERVAL_MINUTES,
                    TWICE_DAILY_TIER, DAILY_TIER, SEND_DAILY_REPORT, TOP_N, RETAIN_DAYS)
import db
from classify import tier_for
from analytics import calculate_delta
from discovery import discover_catalog
from fetcher import fetch_many
from report_telegram import (send_check_delta_report, send_daily_report,
                             send_telegram_document, send_error, fmt_price)
from report_excel import generate_daily_excel


def _now():
    return datetime.now(TZ)


def _is_work_day(now):
    return now.weekday() in WORK_DAYS


def _in_work_window(now):
    if ROUND_THE_CLOCK:
        return True   # HOT/HOURLY run around the clock
    return _is_work_day(now) and WORK_START_TIME <= now.time() <= WORK_END_TIME


def _slot_done(key):
    return db.kv_get("fired:" + key) is not None


def _mark_slot(key):
    db.kv_set("fired:" + key, "1")


def _interval_due(tier, now, minutes):
    last = db.kv_get("last:" + tier)
    if not last:
        return True
    try:
        prev = datetime.fromisoformat(last)
    except ValueError:
        return True
    return (now - prev).total_seconds() >= minutes * 60


def _mark_interval(tier, now):
    db.kv_set("last:" + tier, now.isoformat())


# --- catalog refresh + classification -------------------------------------

def refresh_catalog():
    """Add newly discovered products (tier DAILY by default). Years/tiers are
    learned later from the page, so existing products are left untouched."""
    items = discover_catalog()
    for it in items:
        db.add_product_if_new(it["variant_id"], it["url"], it["title"])
    print(f"Catalog refreshed: {len(items)} products seen.")
    return len(items)


# --- one tier pass ---------------------------------------------------------

def run_tier(tier, now):
    products = db.products_in_tier(tier)
    if not products:
        print(f"[{now:%H:%M}] ({tier}) no products.")
        return
    results, errors = fetch_many(products)
    date = now.date().isoformat()
    changes = []

    for r in results:
        delta = calculate_delta(r["variant_id"], r["stock"], r["status"],
                                r["price_retail"], r["price_cost"])
        db.save_snapshot(r["variant_id"], r["stock"], r["status"],
                         r["price_retail"], r["price_cost"])
        # learn page fields and (re)classify this product by year + recent sales
        db.learn_product(r["variant_id"], r.get("title", ""), r.get("publisher", ""),
                         r.get("year"), r.get("sku"))
        db.set_product_tier(r["variant_id"], tier_for(r.get("year"), r["variant_id"]))
        if not delta:
            continue
        item = {"title": r["title"], "publisher": r["publisher"], "price": r["price_retail"]}
        if delta.get("type") in ("sale", "arrival"):
            item["type"] = delta["type"]
            item["qty"] = delta["qty"]
            db.record_change(date, r["variant_id"], r["title"], r["publisher"],
                             delta["type"], delta["qty"])
        if "price_change" in delta:
            prev, cur = delta["price_change"]
            item["price_change"] = f"{fmt_price(prev)} -> {fmt_price(cur)}"
            db.record_change(date, r["variant_id"], r["title"], r["publisher"],
                             "price_change", detail=item["price_change"])
        if "status_change" in delta:
            prev, cur = delta["status_change"]
            item["status_change"] = f"{prev} -> {cur}"
            db.record_change(date, r["variant_id"], r["title"], r["publisher"],
                             "status_change", detail=item["status_change"])
        changes.append(item)

    send_check_delta_report(now.strftime("%H:%M"), changes)
    print(f"[{now:%H:%M}] ({tier}) checked {len(results)}, changes {len(changes)}, errors {len(errors)}")

    # Alert only on a broad failure (e.g. the source is down) — not a few stray pages
    if products and len(errors) >= max(10, len(products) // 2):
        send_error(f"{tier} {now:%H:%M}: {len(errors)}/{len(products)} fetches failed "
                   f"(source may be down). Example: {errors[0][1] if errors else ''}")


# --- daily report ----------------------------------------------------------

def _safe_tier(tier, now):
    """Run a tier; on an unexpected failure send an error alert and keep going."""
    try:
        run_tier(tier, now)
    except Exception as e:
        print(f"[ERROR] tier {tier} failed: {e}")
        try:
            send_error(f"{tier} {now:%H:%M}: {e}")
        except Exception:
            pass


def emit_daily_report(now):
    date = now.date().isoformat()
    stats = db.daily_stats(date)
    top_sales = db.daily_top(date, "sale", TOP_N)
    top_arrivals = db.daily_top(date, "arrival", TOP_N)
    price_changes = db.daily_list(date, "price_change")
    status_changes = db.daily_list(date, "status_change")
    if SEND_DAILY_REPORT:
        send_daily_report(date, stats, top_sales, top_arrivals, price_changes, status_changes)
    try:
        fn = generate_daily_excel(date, stats, top_sales, top_arrivals,
                                  price_changes, status_changes)
        send_telegram_document(fn, caption=f"{date}")
        print(f"[{now:%H:%M}] daily report + excel sent ({fn})")
    except Exception as e:
        print(f"[WARN] excel/send failed: {e}")


# --- the single pass -------------------------------------------------------

def run_once():
    db.init_db()
    now = _now()
    date = now.date().isoformat()
    t = now.time()
    print(f"Run at {now:%Y-%m-%d %H:%M %Z} (weekday {now.weekday()})")

    if not _is_work_day(now):
        print("Not a work day — nothing to do.")
        return

    # 1) Catalog refresh once a day (24/7: first run after midnight; otherwise
    #    from work start onwards)
    if (ROUND_THE_CLOCK or t >= WORK_START_TIME) and not _slot_done(f"catalog:{date}"):
        try:
            refresh_catalog()
            db.prune_snapshots((now - timedelta(days=RETAIN_DAYS)).isoformat())
            _mark_slot(f"catalog:{date}")
        except Exception as e:
            print(f"[ERROR] catalog refresh failed: {e}")
            try:
                send_error(f"catalog refresh {now:%H:%M}: {e}")
            except Exception:
                pass

    # 2) Interval tiers during the work window
    if _in_work_window(now):
        if _interval_due("HOT", now, TIER_INTERVAL_MINUTES["HOT"]):
            _safe_tier("HOT", now); _mark_interval("HOT", now)
        if _interval_due("HOURLY", now, TIER_INTERVAL_MINUTES["HOURLY"]):
            _safe_tier("HOURLY", now); _mark_interval("HOURLY", now)

    # 3) Fixed-time tiers
    if t >= WORK_START_TIME and not _slot_done(f"twice_morning:{date}"):
        _safe_tier(TWICE_DAILY_TIER, now); _mark_slot(f"twice_morning:{date}")
    # DAILY (older books) once a day: 24/7 right after midnight, else at work start
    if (ROUND_THE_CLOCK or t >= WORK_START_TIME) and not _slot_done(f"daily:{date}"):
        _safe_tier(DAILY_TIER, now); _mark_slot(f"daily:{date}")
    if t >= EVENING_TIME and not _slot_done(f"twice_evening:{date}"):
        _safe_tier(TWICE_DAILY_TIER, now); _mark_slot(f"twice_evening:{date}")

    # 4) Daily report after the evening slot, so it includes the whole day
    if t >= REPORT_TIME and not _slot_done(f"report:{date}"):
        try:
            emit_daily_report(now)
        except Exception as e:
            print(f"[ERROR] daily report failed: {e}")
            try:
                send_error(f"daily report {now:%H:%M}: {e}")
            except Exception:
                pass
        _mark_slot(f"report:{date}")


if __name__ == "__main__":
    run_once()
