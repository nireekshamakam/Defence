# Defence & Aerospace Companies — Live Database

A live, auto-refreshing database of Indian defence & aerospace companies,
seeded from the source Excel and updated daily with market data.

## What this gives you

| Layer | What | Where |
| ----- | ---- | ----- |
| **Source** | The original analyst-built Excel | `data/source_excel/` |
| **DB** | SQLite (single file, easy to share) | `data/defence.db` |
| **Live ingest** | Pluggable adapter (yfinance now, Bloomberg later) | `defence_db/adapters/` |
| **Dashboard** | Streamlit web app for browsing / filtering / charts | `app/streamlit_app.py` |
| **Excel export** | Snapshot xlsx written each refresh | `data/exports/` |
| **Schedule** | GitHub Actions cron — refreshes nightly after NSE close | `.github/workflows/refresh.yml` |

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Create DB + seed companies from the source Excel (idempotent)
python scripts/bootstrap.py

# 2. Pull live market data and write an Excel export
python scripts/refresh.py

# 3. Browse it in your browser
streamlit run app/streamlit_app.py
```

## Architecture

```
+----------------------+   nightly cron    +-----------------------+
|  GitHub Actions      | ----------------> |  scripts/refresh.py   |
+----------------------+                   +----------+------------+
                                                      |
                                                      v
+----------------------+    seed once     +-----------+------------+
|  source Excel (.xlsx)| ---------------> |  defence_db (SQLite)   |
+----------------------+                  +---+--------+-----------+
                                              |        |
                                              v        v
                                  +-----------+--+   +-+---------------+
                                  | Streamlit app|   | xlsx export     |
                                  +--------------+   +-----------------+
```

The schema lives in `defence_db/models.py`:

- `companies` — static descriptor (name, ticker, segment, value chain, promoter, ...)
- `price_snapshots` — one row per (company, day) of live market data
- `financial_snapshots` — historical + estimated revenue / EBITDA / margins
- `manual_inputs` — analyst overrides (target P/E, mgmt estimates) that aren't market-fetchable
- `refresh_runs` — audit log of every refresh attempt

## Data sources

Today we use **yfinance** (free, NSE-listed). The adapter pattern in
`defence_db/adapters/base.py` defines a `MarketDataSource` protocol, so
swapping in a paid feed (Bloomberg BQL, Tijori, Trendlyne) is a single
new class — no DB or UI changes.

| Field | yfinance | Bloomberg (future) | Notes |
| ----- | -------- | ------------------ | ----- |
| Price, mkt cap, EV | ✅ | ✅ | live |
| P/E TTM, P/E Fwd | ✅ | ✅ | fwd missing for thinly-traded names |
| EV/EBITDA, P/B | ✅ | ✅ | TTM only on yfinance |
| ROE | ✅ | ✅ | TTM; bbg has multiple variants (ROE1/ROE3/ROTE) |
| ROCE / ROIC | ❌ | ✅ | not exposed on yfinance |
| Revenue/EBITDA/EPS (annual) | partial | ✅ | for IN small caps yfinance often misses |
| Estimates FY26P–FY30P | ❌ | ✅ | stay as manual inputs (`manual_inputs` table) |
| Order backlog | ❌ | ✅ | manual for now |

## Hosting

- **DB + cron**: GitHub Actions runs `scripts/refresh.py` every weekday at
  00:30 IST. The updated `data/defence.db` is committed back to the repo
  so the dashboard always has fresh data with no separate datastore.
- **Dashboard**: deploy `app/streamlit_app.py` to
  [Streamlit Community Cloud](https://streamlit.io/cloud) (free) — point
  it at this repo, set the main file to `app/streamlit_app.py`. It picks
  up the committed `data/defence.db` on each run.

## Adding a new data source

```python
# defence_db/adapters/my_source.py
from .base import MarketSnapshot

class MySource:
    name = "my_paid_feed"
    def fetch(self, symbol: str) -> MarketSnapshot | None:
        ...   # call the API, normalize, return MarketSnapshot
```

Then `python scripts/refresh.py` with `--source my_paid_feed` (wire up
in the script when you add the second source).

## Tests

```bash
pytest -q tests/
```

Smoke tests cover the ticker mapping and the dataclass contract; they
don't hit the network.
