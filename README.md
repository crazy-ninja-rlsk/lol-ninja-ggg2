# Monitoring & Reporting Bot (lol-ninja-ggg2)

Periodically checks a storefront for stock, price and availability movement,
stores snapshots, and reports via Telegram. Runs serverless on GitHub Actions
(scheduled), so no always-on machine is needed.

## What it does

- **Discovers the catalog live** from the storefront sitemap — new products are
  picked up automatically, nothing is hardcoded.
- **Classifies** each product into a monitoring tier by publication year and
  recent sales activity.
- **Monitors** each tier at its own cadence, reading exact stock, cost and
  availability from the product page, and detects sales / arrivals / price /
  status changes.
- **Instant alert** to Telegram after any check that detected movement.
- **Daily summary** at end of day: totals + TOP-10 arrivals and TOP-10 sales,
  plus an Excel file.

## Tiers

| Tier | Products | Cadence |
|------|----------|---------|
| HOT | newest years (`year >= HOT_YEAR`) | every 20 min |
| HOURLY | recent year with recent sales | hourly |
| TWICE_DAILY | other recent-year | work start + evening |
| DAILY | older | once a day |

All cadence gating uses the market's local time (`TZ_NAME`), so DST never
breaks the schedule. Work window and years are set in `config.py`.

## How data is obtained

- **Discovery** (whole catalog, dynamic): the storefront sitemap (`discovery.py`).
- **Year, price, exact stock, cost, availability**: the product page — embedded
  storefront product config + schema.org JSON-LD (`fetcher.py`). Year is learned
  on first visit and stored; tiers are (re)assigned from it.

## Privacy / secrets

Nothing identifying is in this repository. All of it is supplied at runtime via
environment variables / CI secrets, or kept in local gitignored files:

| Data | Where |
|------|-------|
| Telegram token, chat id | env / CI secret |
| Source base URL, index credentials | env / CI secret |
| Localized message text | `locale.local.json` (gitignored) / `LOCALE_JSON` secret |
| Snapshot DB | CI cache (local file, gitignored) |

Public code is English-only and generic (schema.org / hosted-index parsing).

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env            # fill in your values
cp locale.example.json locale.local.json   # optional localized text
python main.py                  # one pass
python main.py --loop           # continuous (polls every minute)
```

## Run on GitHub Actions

Set repository **Secrets**: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
`SUPPLIER_BASE_URL`, `TZ_NAME`, and optionally `LOCALE_JSON` (the localized
templates as JSON).
The workflow in `.github/workflows/monitor.yml` runs every 20 minutes and
persists the DB between runs via the Actions cache. The catalog (and learned
years) persists; only snapshot history is trimmed, to `RETAIN_DAYS` days.
