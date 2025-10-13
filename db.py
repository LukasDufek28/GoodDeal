import sqlite3
from typing import Optional, Tuple


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    return column in cols


def ensure_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        # Base table with 'type' column for category
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                location TEXT,
                price INTEGER,
                currency TEXT,
                type TEXT,
                rating TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Migrate existing DBs: add 'type' if missing
        if not _column_exists(conn, "listings", "type"):
            try:
                cur.execute("ALTER TABLE listings ADD COLUMN type TEXT")
            except Exception:
                pass
        # Migrate existing DBs: add 'rating' if missing
        if not _column_exists(conn, "listings", "rating"):
            try:
                cur.execute("ALTER TABLE listings ADD COLUMN rating TEXT")
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()


def insert_listing(path: str, title: str, url: str, location: Optional[str], price: Optional[int], currency: Optional[str]) -> None:
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO listings (title, url, location, price, currency)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, url, location, price, currency),
        )
        conn.commit()
    finally:
        conn.close()


def _get_listing_id(cur: sqlite3.Cursor, url: str) -> Optional[int]:
    cur.execute("SELECT id FROM listings WHERE url=?", (url,))
    row = cur.fetchone()
    return int(row[0]) if row else None


def _norm_type(type_: Optional[str]) -> Optional[str]:
    if not type_:
        return None
    return type_.strip().lower() or None


def insert_listing_with_details(
    path: str,
    title: str,
    url: str,
    location: Optional[str],
    price: Optional[int],
    currency: Optional[str],
    type_: Optional[str],
    product_name: Optional[str],  # kept for compatibility (unused)
    listing_title: Optional[str],  # kept for compatibility (unused)
    rating: Optional[str] = None,
    params_json: Optional[str] = None,  # kept for compatibility (unused)
) -> Tuple[Optional[int], Optional[str]]:
    """
    Insert or update listing with type and rating stored directly in listings.
    Returns (listing_id, normalized_type).
    """
    tnorm = _norm_type(type_)
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO listings (title, url, location, price, currency, type, rating)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, url, location, price, currency, tnorm, rating),
        )
        lid = cur.lastrowid or _get_listing_id(cur, url)
        # Update row in case it existed already
        if lid is not None:
            cur.execute(
                "UPDATE listings SET title=?, location=?, price=?, currency=?, type=?, rating=? WHERE id=?",
                (title, location, price, currency, tnorm, rating, lid),
            )

        conn.commit()
        return lid, tnorm
    finally:
        conn.close()
