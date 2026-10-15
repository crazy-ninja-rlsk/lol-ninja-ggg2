import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from strings import t


def fmt_price(value):
    """Whole units (no decimals), space thousands separator."""
    try:
        return f"{int(round(float(value))):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        print("[TG MOCK]:", text[:120].replace("\n", " ") + "...")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chunk in _split(text, 4096):
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"})


def _split(text, limit):
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit:
            parts.append(cur)
            cur = ""
        cur += line + "\n"
    if cur:
        parts.append(cur)
    return parts


def send_check_delta_report(check_time_str, changes_list):
    if not changes_list:
        return
    msg = t("check_header", time=check_time_str) + "\n\n"
    for item in changes_list:
        msg += f"• <b>{item['title']}</b> ({item['publisher']})\n"
        if item.get("type") == "sale":
            msg += "   " + t("sale", qty=item["qty"], price=fmt_price(item["price"])) + "\n"
        elif item.get("type") == "arrival":
            msg += "   " + t("arrival", qty=item["qty"], price=fmt_price(item["price"])) + "\n"
        if "price_change" in item:
            msg += "   " + t("price_change", change=item["price_change"]) + "\n"
        if "status_change" in item:
            msg += "   " + t("status_change", change=item["status_change"]) + "\n"
    send_telegram_message(msg)


def _top_block(header_key, top_list):
    if not top_list:
        return ""
    lines = [t(header_key)]
    for i, it in enumerate(top_list, 1):
        lines.append(t("daily_top_item", n=i, title=it["title"],
                       publisher=it["publisher"], qty=it["qty"]))
    return "\n".join(lines)


def send_daily_report(date_str, stats, top_sales=None, top_arrivals=None):
    msg = t("daily_header", date=date_str) + "\n\n"
    total = (stats["sales"][0] + stats["arrivals"][0]
             + stats["price_changes"] + stats["status_changes"])
    if total == 0:
        send_telegram_message(msg + t("daily_no_movement"))
        return
    msg += t("daily_sales", count=stats["sales"][0], qty=stats["sales"][1]) + "\n"
    msg += t("daily_arrivals", count=stats["arrivals"][0], qty=stats["arrivals"][1]) + "\n"
    msg += t("daily_price_changes", count=stats["price_changes"]) + "\n"
    msg += t("daily_status_changes", count=stats["status_changes"])
    arr = _top_block("daily_top_arrivals", top_arrivals)
    sal = _top_block("daily_top_sales", top_sales)
    if arr:
        msg += "\n\n" + arr
    if sal:
        msg += "\n\n" + sal
    send_telegram_message(msg)
