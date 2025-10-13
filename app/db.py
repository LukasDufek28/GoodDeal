import sqlite3
from typing import Optional

DB_PATH = "./gooddeal.sqlite3"

def ensure_db(path: Optional[str] = None) -> None:
	path = path or DB_PATH
	with sqlite3.connect(path) as conn:
		conn.execute("""
			CREATE TABLE IF NOT EXISTS listings (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				title TEXT,
				url TEXT UNIQUE,
				price_value INTEGER,
				price_currency TEXT,
				description TEXT,
				location TEXT,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		""")
		conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_listings_url ON listings(url)")

def insert_listing(title: Optional[str], url: Optional[str], path: Optional[str] = None) -> int:
	if not url:
		return 0
	path = path or DB_PATH
	ensure_db(path)
	with sqlite3.connect(path) as conn:
		cur = conn.execute(
			"INSERT OR IGNORE INTO listings (title, url) VALUES (?, ?)",
			(title, url),
		)
		if cur.rowcount == 0:
			# Already exists; update title if provided
			conn.execute("UPDATE listings SET title = COALESCE(?, title) WHERE url = ?", (title, url))
			return 0
		return cur.lastrowid or 0

def insert_listing_with_details(
	title: Optional[str],
	url: Optional[str],
	price_value: Optional[int],
	price_currency: Optional[str],
	description: Optional[str],
	location: Optional[str],
	path: Optional[str] = None,
) -> int:
	if not url:
		return 0
	path = path or DB_PATH
	ensure_db(path)
	with sqlite3.connect(path) as conn:
		cur = conn.execute(
			"INSERT OR IGNORE INTO listings (title, url, price_value, price_currency, description, location) "
			"VALUES (?, ?, ?, ?, ?, ?)",
			(title, url, price_value, price_currency, description, location),
		)
		if cur.rowcount == 0:
			# Exists -> update fields
			conn.execute(
				"""UPDATE listings
				   SET title = COALESCE(?, title),
					   price_value = ?,
					   price_currency = ?,
					   description = COALESCE(?, description),
					   location = COALESCE(?, location)
				   WHERE url = ?""",
				(title, price_value, price_currency, description, location, url),
			)
			return 0
		return cur.lastrowid or 0
