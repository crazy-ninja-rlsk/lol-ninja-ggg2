"""
Catalog discovery via the storefront sitemap.

The sitemap index lists sub-sitemaps; each lists every page URL (no result cap),
so the full, live catalog is available and new products appear automatically.
We keep only single-segment product URLs of the primary locale and skip
category/author/brand/locale and static pages.

The sitemap does not carry the publication year; that (and price/stock/cost) is
read from the product page by fetcher.py on the first visit and stored.
"""
import re
import ssl
import urllib.request
from urllib.parse import urlparse

from config import SUPPLIER_BASE_URL, REQUEST_TIMEOUT

_SSL = ssl.create_default_context()
_LOC_RE = re.compile(r"<loc>(.*?)</loc>", re.S)

# Single-segment paths that are NOT products.
_STATIC = {
    "about", "delivery", "payment", "oferta", "brands", "authors", "cart",
    "my", "search", "compare", "confidentiality-policy", "contacts", "blog",
    "favorites", "sitemap", "ru", "", "reviews", "news",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; price-monitor/1.0)"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_SSL) as r:
        return r.read().decode("utf-8", "replace")


def _sitemap_urls():
    """Return every <loc> across the sitemap index and its sub-sitemaps."""
    base = SUPPLIER_BASE_URL.rstrip("/")
    index = _get(base + "/sitemap.xml")
    subs = [u for u in _LOC_RE.findall(index) if u.endswith(".xml")]
    if not subs:
        subs = [base + "/sitemap.xml"]
    urls = []
    for sm in subs:
        if "image" in sm:      # product-image sitemap — skip
            continue
        try:
            urls.extend(_LOC_RE.findall(_get(sm)))
        except Exception as e:
            print(f"[WARN] sub-sitemap failed {sm}: {e}")
    return urls


def _is_product(loc):
    path = urlparse(loc).path.strip("/")
    if not path or "/" in path:      # home, or multi-segment (category/, ru/slug, …)
        return False
    return path not in _STATIC


def discover_catalog():
    """Return a list of catalog stubs: {variant_id, url, product_id, sku, title, publisher, year}.

    Only url is known at discovery time; the rest is learned from the page.
    """
    items = []
    seen = set()
    for loc in _sitemap_urls():
        if not _is_product(loc):
            continue
        slug = urlparse(loc).path.strip("/")
        if slug in seen:
            continue
        seen.add(slug)
        items.append({
            "variant_id": f"p-{slug}",
            "url": slug,
            "product_id": None,
            "sku": None,
            "title": slug,         # placeholder until the page is fetched
            "publisher": "",
            "year": None,
        })
    return items
