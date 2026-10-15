"""Compute the change (delta) between a fresh reading and the last snapshot."""
from db import last_snapshot


def calculate_delta(variant_id, stock, status, price_retail, price_cost):
    """Return a dict of changes vs the last stored snapshot, or None if first/no change."""
    prev = last_snapshot(variant_id)
    if not prev:
        return None
    prev_stock, prev_status, prev_retail, prev_cost = prev
    delta = {}

    if stock is not None and prev_stock is not None:
        diff = stock - prev_stock
        if diff < 0:
            delta["type"] = "sale"
            delta["qty"] = abs(diff)
        elif diff > 0:
            delta["type"] = "arrival"
            delta["qty"] = diff

    if status != prev_status and status != "unknown" and prev_status is not None:
        delta["status_change"] = (prev_status, status)

    if price_retail is not None and prev_retail is not None and price_retail != prev_retail:
        delta["price_change"] = (prev_retail, price_retail)

    return delta or None
