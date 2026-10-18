import sqlite3
from datetime import datetime

from config import DB_NAME


def _conn():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = _conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            variant_id TEXT PRIMARY KEY,
            product_id TEXT,
            sku TEXT,
            title TEXT NOT NULL,
            publisher TEXT,
            year INTEGER,
            url TEXT,
            tier TEXT,
            last_price REAL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            variant_id TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            stock INTEGER,
            status TEXT,
            price_retail REAL,
            price_cost REAL
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_snap_variant ON snapshots(variant_id, timestamp)')
    # per-day movement log (for daily summary + TOP-10)
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_changes (
            date TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            title TEXT,
            publisher TEXT,
            kind TEXT NOT NULL,
            qty INTEGER DEFAULT 0,
            detail TEXT DEFAULT '',
            ts TEXT NOT NULL
        )
    ''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_changes(date, kind)')
    # migrate older cached DBs that predate the detail column
    cols = [r[1] for r in c.execute("PRAGMA table_info(daily_changes)").fetchall()]
    if "detail" not in cols:
        c.execute("ALTER TABLE daily_changes ADD COLUMN detail TEXT DEFAULT ''")
    # simple key/value state (last-run per tier, fired daily slots)
    c.execute('CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    conn.close()


def record_change(date, variant_id, title, publisher, kind, qty=0, detail=""):
    conn = _conn()
    conn.execute('INSERT INTO daily_changes (date, variant_id, title, publisher, kind, qty, detail, ts) '
                 'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                 (date, variant_id, title, publisher, kind, qty, detail, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def daily_list(date, kind):
    """All changes of a kind for the day, with their detail text."""
    conn = _conn()
    rows = conn.execute('SELECT title, publisher, detail FROM daily_changes '
                        'WHERE date=? AND kind=? ORDER BY ts ASC', (date, kind)).fetchall()
    conn.close()
    return [{"title": r[0], "publisher": r[1], "detail": r[2] or ""} for r in rows]


def daily_stats(date):
    conn = _conn()
    def agg(kind):
        row = conn.execute('SELECT COUNT(*), COALESCE(SUM(qty),0) FROM daily_changes '
                           'WHERE date=? AND kind=?', (date, kind)).fetchone()
        return (row[0], row[1])
    sales = agg("sale")
    arrivals = agg("arrival")
    pc = conn.execute('SELECT COUNT(*) FROM daily_changes WHERE date=? AND kind=?',
                      (date, "price_change")).fetchone()[0]
    sc = conn.execute('SELECT COUNT(*) FROM daily_changes WHERE date=? AND kind=?',
                      (date, "status_change")).fetchone()[0]
    conn.close()
    return {"sales": sales, "arrivals": arrivals, "price_changes": pc, "status_changes": sc}


def daily_top(date, kind, limit=10):
    conn = _conn()
    rows = conn.execute('''
        SELECT title, publisher, SUM(qty) AS q FROM daily_changes
        WHERE date=? AND kind=? GROUP BY title, publisher ORDER BY q DESC LIMIT ?
    ''', (date, kind, limit)).fetchall()
    conn.close()
    return [{"title": r[0], "publisher": r[1], "qty": r[2]} for r in rows]


# --- key/value state ---

def kv_get(key, default=None):
    conn = _conn()
    row = conn.execute('SELECT value FROM kv WHERE key = ?', (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def kv_set(key, value):
    conn = _conn()
    conn.execute('INSERT INTO kv(key, value) VALUES(?, ?) '
                 'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))
    conn.commit()
    conn.close()


# --- products ---

def add_product_if_new(variant_id, url, placeholder_title):
    """Insert a freshly discovered product (default tier DAILY). Never overwrites
    already-learned fields (title/publisher/year/tier) for existing products."""
    conn = _conn()
    conn.execute('''
        INSERT INTO products (variant_id, url, title, tier)
        VALUES (?, ?, ?, 'DAILY')
        ON CONFLICT(variant_id) DO NOTHING
    ''', (variant_id, url, placeholder_title))
    conn.commit()
    conn.close()


def learn_product(variant_id, title, publisher, year, sku):
    """Update fields learned from the product page."""
    conn = _conn()
    conn.execute('''
        UPDATE products SET
            title = COALESCE(NULLIF(?, ''), title),
            publisher = COALESCE(NULLIF(?, ''), publisher),
            year = COALESCE(?, year),
            sku = COALESCE(?, sku)
        WHERE variant_id = ?
    ''', (title, publisher, year, sku, variant_id))
    conn.commit()
    conn.close()


def prune_snapshots(before_iso):
    conn = _conn()
    conn.execute('DELETE FROM snapshots WHERE timestamp < ?', (before_iso,))
    conn.execute('DELETE FROM daily_changes WHERE date < ?', (before_iso[:10],))
    conn.commit()
    conn.close()


def set_product_tier(variant_id, tier):
    conn = _conn()
    conn.execute('UPDATE products SET tier=? WHERE variant_id=?', (tier, variant_id))
    conn.commit()
    conn.close()


def get_last_price(variant_id):
    conn = _conn()
    row = conn.execute('SELECT last_price FROM products WHERE variant_id=?', (variant_id,)).fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else None


def set_last_price(variant_id, price):
    conn = _conn()
    conn.execute('UPDATE products SET last_price=? WHERE variant_id=?', (price, variant_id))
    conn.commit()
    conn.close()


def products_in_tier(tier):
    conn = _conn()
    rows = conn.execute(
        'SELECT variant_id, product_id, sku, title, publisher, year, url FROM products WHERE tier=?',
        (tier,)).fetchall()
    conn.close()
    cols = ["variant_id", "product_id", "sku", "title", "publisher", "year", "url"]
    return [dict(zip(cols, r)) for r in rows]


def all_products():
    conn = _conn()
    rows = conn.execute(
        'SELECT variant_id, product_id, sku, title, publisher, year, url FROM products').fetchall()
    conn.close()
    cols = ["variant_id", "product_id", "sku", "title", "publisher", "year", "url"]
    return [dict(zip(cols, r)) for r in rows]


# --- snapshots ---

def save_snapshot(variant_id, stock, status, price_retail, price_cost):
    conn = _conn()
    conn.execute('''
        INSERT INTO snapshots (variant_id, timestamp, stock, status, price_retail, price_cost)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (variant_id, datetime.now().isoformat(), stock, status, price_retail, price_cost))
    conn.commit()
    conn.close()


def last_snapshot(variant_id):
    conn = _conn()
    row = conn.execute('''
        SELECT stock, status, price_retail, price_cost FROM snapshots
        WHERE variant_id=? ORDER BY timestamp DESC LIMIT 1
    ''', (variant_id,)).fetchone()
    conn.close()
    return row  # (stock, status, price_retail, price_cost) or None


def had_sale_since(variant_id, since_iso, min_days=1):
    """True if stock decreased on at least `min_days` distinct dates since since_iso."""
    conn = _conn()
    rows = conn.execute('''
        SELECT timestamp, stock FROM snapshots
        WHERE variant_id=? AND timestamp>=? ORDER BY timestamp ASC
    ''', (variant_id, since_iso)).fetchall()
    conn.close()
    days = set()
    prev = None
    for ts, stock in rows:
        if prev is not None and stock is not None and prev is not None and stock < prev:
            days.add(ts[:10])
        if stock is not None:
            prev = stock
    return len(days) >= min_days
