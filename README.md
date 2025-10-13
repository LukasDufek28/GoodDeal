# Bazos finder (simple CLI)

Find Bazos listings under a maximum price by keyword and get notified when new potential deals appear.

## Setup

- Python 3.9+
- Install dependencies:

  ```powershell
  pip install -r requirements.txt
  ```

- Optional: copy `.env.example` to `.env` and fill in values for Telegram or regional filters.

## Configuration

Open `config.py` and edit the `CONFIG` dictionary:

- `watch`: set to true to loop forever
- `interval`: seconds between checks (e.g., 300 for 5 minutes)
- `state_file`: JSON file to track seen URLs and avoid duplicates (set to `None` to disable persistence)
- `cities`: `{"include": [..], "exclude": [..]}` to soft-filter locations (detail page is fetched to confirm)
- `ignore`: list of words/phrases to ignore (accent-insensitive)
- `searches`: list of search objects with fields:
  - `keyword` (string)
  - `max_price` (number) and optional `min_price` (number)
  - `site` ("sk" or "cz")
  - `pages` (int)
  - `include_content` (boolean, optional)
  - `match_in` ("title", "description", or "both")

Runtime helpers if you import it as a module:

- `set_interval(600)`
- `add_search("rtx 3060", 200, site="sk", pages=2)`
- `clear_searches()`

## Run

- One-shot: executes all searches in CONFIG and prints only new links.

  ```powershell
  python .\main.py
  ```

- Watch mode: set `"watch": true` and `"interval": 300` in CONFIG, then run; it will loop until Ctrl+C.

## Notes

- Polite rate limiting and retry with backoff are applied between requests.
- Bazos HTML can change; if parsing breaks, adjust `extract_listings_from_search` / `find_price_near_anchor`.
- In watch mode, only newly seen URLs per search key are printed to avoid duplicates.

## Regional filtering (optional)

Limit searches by postal code and radius via environment variables in a `.env` file next to `main.py`:

```
HLOKALITA=811 01
HUMKREIS=40
```

- `HLOKALITA`: postal code or place (Bazos "PSČ (miesto)" field). `"903 01"` and `"903+01"` are both accepted; `+` is normalized to a space.
- `HUMKREIS`: radius in km.

Alternatively, set `"hlokalita"` and `"humkreis"` directly in `CONFIG` in `config.py`. Environment variables take precedence.

## Telegram notifications (optional)

Set the following env vars (via `.env`):

```
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
```

You can get a bot token from BotFather and your chat id by sending a message to the bot and calling `getUpdates` on the Bot API. When present, the app sends a compact summary of new finds.

## Windows scheduling (hands-free)

To run every 5 minutes on Windows via Task Scheduler:

```powershell
# Register a task (adjust paths)
schtasks /Create /SC MINUTE /MO 5 /TN "GoodDealWatcher" /TR "cmd /c \"cd /d c:\\Users\\DufekLukáš\\Desktop\\GoodDeal && python main.py\""

# Run it now (optional)
schtasks /Run /TN "GoodDealWatcher"
```

Delete the task later:

```powershell
schtasks /Delete /TN "GoodDealWatcher" /F
```

## Flipping workflow playbook

This is a practical pipeline to use this tool for a flipping business.

1) Sourcing (automated by this repo)
- Define 5–15 liquid SKUs in `CONFIG["searches"]` with tight price caps.
- Use `cities.include`/`exclude` to reduce travel distance.
- Enable Telegram to get instant pings.

2) Triage leads (daily ritual)
- When new items arrive, open links immediately; assess condition, photos, accessories, and seller history.
- Use the optional Tkinter review GUI (`CONFIG["gui"] = True`) to curate and store accepted leads into SQLite.

3) Contact and negotiate
- Prepare 2–3 message templates with: fast pickup, cash, polite, no time-wasting.
- Aim to be first and decisive: propose a fair cash price with a specific pickup time.

4) Due diligence before pickup
- For electronics: serial numbers, battery health (iOS/macOS), test plan (boot, ports, fan noise), accessories.
- Factor travel and shipping cost; keep a simple profit calculator target (e.g., at least €40 or 25%).

5) Purchase and refurbish
- Wipe, clean, re-paste if needed, update firmware, factory reset.
- Take daylight photos with a consistent background; list key specs clearly.

6) Relist and sell fast
- Price slightly below median to move inventory quickly; disclose minor defects honestly.
- Cross-list where allowed and consistent with TOS (respect platform rules).

7) Track metrics and improve
- Track: leads/day, contact rate, meeting rate, buy rate, avg profit, time-to-sell, returns.
- Cull SKUs with low conversion; add new ones with better liquidity.

## Ideas to upgrade the script (roadmap)

Quick wins (low effort)
- Logging: switch `print` to `logging` with INFO/DEBUG; rotate file logs for history.
- CLI params: add `argparse` to override CONFIG (watch, interval, site, keyword) from the command line.
- Enrich DB: extend SQLite schema to record decisions (accepted/declined), timestamps, and notes.
- CSV export: dump new listings or accepted ones to a CSV for spreadsheet workflows.

Medium (a few hours)
- Telegram actions: send inline buttons (Accept/Skip/Open) and handle callbacks to store to DB remotely.
- Web review UI: tiny FastAPI + HTMX dashboard to review and mark deals headlessly (replaces Tkinter on servers).
- Price comp helpers: store a per-keyword reference price or a simple heuristic (median of last N seen prices) to flag bargains.
- Testable parser: add unit tests with saved HTML fixtures for Bazos to keep scrapers stable across changes.
- Fuzzy dedupe: tolerate small title differences using token-set similarity to avoid near-duplicate prints.

Bigger features
- Profit calculator: add a table with fees, transport, refurb cost; compute expected margin per lead and prioritize by ROI.
- Multi-channel notifications: optional Slack/Discord webhooks alongside Telegram.
- Concurrency with care: parallelize detail-page fetches per search while obeying per-host pacing to stay polite.
- Config as YAML: load config from `config.yaml` for non-programmers; keep `config.py` as fallback.

Operational safeguards
- Respect site terms and avoid aggressive scraping; keep delays and random jitter (already implemented).
- Backoff on HTTP 429/503 (already implemented) and use a consistent `User-Agent`.
- Persist `state_file` to avoid re-processing the same links.

## Database cheatsheet (optional extensions)

Current table:

```
listings(id, title, url UNIQUE, location, price, currency, added_at)
```

Suggested additional tables (schema idea):

```
leads(id PRIMARY KEY, listing_url UNIQUE, status, note, created_at, updated_at)
offers(lead_id, offered_price, when)
purchases(lead_id, buy_price, cost_refurb, transport, when)
sales(lead_id, sell_price, fees, when)
```

Statuses like: NEW, CONTACTED, NEGOTIATING, BOUGHT, LISTED, SOLD, DEAD.

This enables simple ROI reports and a clear pipeline.

## Troubleshooting

- If you see "Missing dependencies", install requirements again.
- If parsing returns no items, Bazos may have changed markup; update selectors in `main.py`.
- For Telegram issues, re-check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` and that the bot has a chat with you.