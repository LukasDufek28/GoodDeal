# Bazos finder (simple CLI)

Find Bazos listings under a maximum price by keyword.

Configuration

Open `config.py` and edit the CONFIG dictionary:

- `watch`: set to true to loop forever
- `interval`: seconds between checks (e.g., 300 for 5 minutes)
- `state_file`: where seen URLs are stored to avoid duplicate prints
- `searches`: list of search objects with fields:
  - `keyword` (string)
  - `max_price` (number)
  - `site` ("sk" or "cz")
  - `pages` (int)
  - `include_content` (boolean, optional)

You can also modify CONFIG at runtime by calling helpers from code (if you embed this as a module):

- `set_interval(600)`
- `add_search("rtx 3060", 200, site="sk", pages=2)`
- `clear_searches()`

Install

- Python 3.9+
- Install deps:

  pip install -r requirements.txt

Run

- One-shot: simply run the script. It will execute all searches in CONFIG and print only new links.

  python .\main.py

- Watch mode: set `"watch": true` and `"interval": 300` in CONFIG, then run the script; it will loop until Ctrl+C.

Notes

- Rate limiting is applied between requests.
- Results are pre-filtered to the PC category to avoid false positives like ski gear named "RTX".
- Bazos can change HTML; if selectors break, adjust extract_listings_from_search/find_price_near_anchor.
- In watch mode, only newly seen URLs per search key are printed to avoid duplicates.
