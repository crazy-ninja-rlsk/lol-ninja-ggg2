"""User-facing message templates. English defaults ship publicly; localized
wording is loaded at runtime from LOCALE_FILE (gitignored)."""
import json
import os

from config import LOCALE_FILE

_DEFAULTS = {
    "check_header": "⚡ <b>Source · Live movement ({time})</b>",
    "daily_header": "📊 <b>Source · Daily summary ({date})</b>",
    "sale": "🔻 Sale: {qty} pcs × {price}",
    "arrival": "🔺 Arrival: +{qty} pcs × {price}",
    "price_change": "💲 Price change: {change}",
    "status_change": "🔄 Status: {change}",
    "daily_sales": "🔻 Sales: {count} ({qty} pcs)",
    "daily_arrivals": "🔺 Arrivals: {count} ({qty} pcs)",
    "daily_price_changes": "💲 Price changes: {count}",
    "daily_status_changes": "🔄 Status changes: {count}",
    "daily_no_movement": "No movement recorded today.",
    "daily_top_sales": "🔻 TOP-10 sales:",
    "daily_top_arrivals": "🔺 TOP-10 arrivals:",
    "daily_top_item": "{n}. {title} ({publisher}) — {qty} pcs",
    "excel_sheets": ["Summary", "Daily movement", "Top arrivals", "Top sales"],
}


def _load():
    s = dict(_DEFAULTS)
    if LOCALE_FILE and os.path.exists(LOCALE_FILE):
        try:
            with open(LOCALE_FILE, encoding="utf-8") as f:
                s.update(json.load(f))
        except (OSError, ValueError) as e:
            print(f"[WARN] Could not read locale file {LOCALE_FILE}: {e}")
    return s


_STRINGS = _load()


def t(key, **kwargs):
    tpl = _STRINGS.get(key, _DEFAULTS.get(key, key))
    return tpl.format(**kwargs) if kwargs else tpl


def raw(key):
    return _STRINGS.get(key, _DEFAULTS.get(key))
