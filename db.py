import sqlite3
from typing import Optional


def ensure_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                location TEXT,
                price INTEGER,
                currency TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
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
