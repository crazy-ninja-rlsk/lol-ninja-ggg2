"""Assign each product to a monitoring tier by publication year and recent sales."""
from datetime import datetime, timedelta

from config import (HOT_YEAR, RECENT_YEAR, RECENT_SALES_WINDOW_DAYS,
                    DAILY_TIER, TWICE_DAILY_TIER)
from db import had_sale_since


def tier_for(year, variant_id):
    """Return the tier for a product.

    - year >= HOT_YEAR            -> HOT        (every 20 min)
    - year == RECENT_YEAR         -> HOURLY if it sold on a recent day, else TWICE_DAILY
    - older / unknown             -> DAILY      (once a day)
    """
    if year is None:
        return DAILY_TIER
    if year >= HOT_YEAR:
        return "HOT"
    if year == RECENT_YEAR:
        since = (datetime.now() - timedelta(days=RECENT_SALES_WINDOW_DAYS)).isoformat()
        return "HOURLY" if had_sale_since(variant_id, since, min_days=1) else TWICE_DAILY_TIER
    return DAILY_TIER
