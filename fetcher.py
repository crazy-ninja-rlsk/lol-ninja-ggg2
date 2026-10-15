"""
Per-product live fetch from the storefront page.

The search index gives title/year/retail price for discovery, but NOT the exact
stock count, the purchase (cost) price or the availability status. Those are
read here from the product page: the embedded storefront product config
(per-SKU `price`, `purchase_price`, `count`) plus the schema.org JSON-LD
availability.
"""
import json
import re
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from config import SUPPLIER_BASE_URL, REQUEST_TIMEOUT, FETCH_WORKERS

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; price-monitor/1.0)"}

_AVAILABILITY = {
    "instock": "in_stock", "preorder": "preorder", "outofstock": "out",
    "soldout": "out", "backorder": "preorder", "limitedavailability": "in_stock",
}

_SKUS_RE = re.compile(r'skus:\s*(\{.*?\})\s*,\s*services:', re.S)
_JSONLD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I)

_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)


def _absolute_url(slug_or_url):
    if slug_or_url.startswith("http"):
        return slug_or_url
    return SUPPLIER_BASE_URL.rstrip("/") + "/" + slug_or_url.strip("/") + "/"


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pick_sku(skus, want_sku):
    if not skus:
        return None
    if want_sku:
        for entry in skus.values():
            if str(entry.get("sku")) == str(want_sku):
                return entry
    return next(iter(skus.values()))


def _parse_jsonld(html):
    """Return (status, name, publisher) from the schema.org Product block."""
    for block in _JSONLD_RE.findall(html):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for obj in (data if isinstance(data, list) else [data]):
            if isinstance(obj, dict) and "Product" in str(obj.get("@type", "")):
                offers = obj.get("offers") or {}
                if isinstance(offers, dict) and offers.get("offers"):
                    offers = offers["offers"]
                offer = offers[0] if isinstance(offers, list) and offers else offers
                avail = offer.get("availability", "") if isinstance(offer, dict) else ""
                status = _AVAILABILITY.get(str(avail).rsplit("/", 1)[-1].lower(), "unknown")
                brand = obj.get("brand") or {}
                publisher = brand.get("name", "") if isinstance(brand, dict) else str(brand)
                return status, obj.get("name", ""), publisher
    return "unknown", "", ""


def _year_from_entry(entry):
    feats = entry.get("features") if isinstance(entry, dict) else None
    if isinstance(feats, dict):
        try:
            return int(str(feats.get("god_izdaniya"))[:4])
        except (TypeError, ValueError):
            return None
    return None


def fetch_one(item):
    """Fetch live stock/cost/price/status (+ title/publisher/year) for one item."""
    resp = _SESSION.get(_absolute_url(item["url"]), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    html = resp.text

    stock = price = cost = year = None
    sku = None
    m = _SKUS_RE.search(html)
    if m:
        try:
            entry = _pick_sku(json.loads(m.group(1)), item.get("sku"))
        except ValueError:
            entry = None
        if entry:
            price = _to_float(entry.get("price"))
            cost = _to_float(entry.get("purchase_price"))
            cnt = entry.get("count")
            stock = int(cnt) if isinstance(cnt, (int, float)) else None
            year = _year_from_entry(entry)
            sku = entry.get("sku")

    status, name, publisher = _parse_jsonld(html)
    if status == "unknown" and stock is not None:
        status = "in_stock" if stock > 0 else "out"

    return {
        "variant_id": item["variant_id"],
        "sku": sku or item.get("sku"),
        "title": name or item.get("title", ""),
        "publisher": publisher or item.get("publisher", ""),
        "year": year if year is not None else item.get("year"),
        "stock": stock,
        "status": status,
        "price_retail": price if price is not None else item.get("price"),
        "price_cost": cost,
    }


def fetch_many(items):
    """Fetch many items concurrently. Returns (results, errors)."""
    results, errors = [], []
    if not items:
        return results, errors
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        futures = {ex.submit(fetch_one, it): it for it in items}
        for fut in as_completed(futures):
            it = futures[fut]
            try:
                results.append(fut.result())
            except Exception as e:
                errors.append((it.get("variant_id"), str(e)))
    return results, errors
