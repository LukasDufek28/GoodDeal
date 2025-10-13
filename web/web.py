import os
import sqlite3
from typing import List, Tuple, Optional
from flask import Flask, request, Response, render_template, redirect, url_for

try:
	from app.db import ensure_db  # type: ignore
except Exception:
	def ensure_db():
		pass

DB_PATH = "./gooddeal.sqlite3"

def get_conn():
	return sqlite3.connect(DB_PATH)

def format_price(value: Optional[int], currency: Optional[str]) -> str:
	if value is None:
		return "—"
	num = f"{value:,}".replace(",", " ")
	if currency == "EUR":
		return f"{num} €"
	if currency == "CZK":
		return f"{num} Kč"
	return f"{num} {currency}" if currency else num

def clear_db_rows() -> None:
	ensure_db()
	# First delete inside a regular transaction and close it
	with get_conn() as conn:
		conn.execute("DELETE FROM listings")
		conn.commit()
	# Then run VACUUM outside of any transaction (autocommit mode)
	with sqlite3.connect(DB_PATH, isolation_level=None) as conn2:
		conn2.execute("VACUUM")

app = Flask(__name__)

# The HTML template has been moved to web/templates/listings.html and styling to web/static/style.css

def query_listings(q: str = "", min_price: Optional[int] = None, max_price: Optional[int] = None, limit: int = 500) -> List[Tuple]:
	ensure_db()
	sql = """SELECT title, url, price_value, price_currency, description, location
	         FROM listings"""
	conds = []
	args: list = []
	if q:
		conds.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ?)")
		qp = f"%{q.lower()}%"
		args.extend([qp, qp])
	if min_price is not None:
		conds.append("(price_value IS NOT NULL AND price_value >= ?)")
		args.append(min_price)
	if max_price is not None:
		conds.append("(price_value IS NOT NULL AND price_value <= ?)")
		args.append(max_price)
	if conds:
		sql += " WHERE " + " AND ".join(conds)
	sql += " ORDER BY COALESCE(datetime(created_at), '') DESC, id DESC"
	sql += " LIMIT ?"
	args.append(limit)
	with get_conn() as conn:
		return list(conn.execute(sql, args))

@app.route("/")
def index():
	q = request.args.get("q", "").strip()
	min_q = request.args.get("min", "").strip()
	max_q = request.args.get("max", "").strip()
	limit_q = request.args.get("limit", "").strip()
	msg = request.args.get("msg", "").strip()
	err = request.args.get("err", "").strip() == "1"
	min_price = int(min_q) if min_q.isdigit() else None
	max_price = int(max_q) if max_q.isdigit() else None
	limit = int(limit_q) if limit_q.isdigit() else 500
	rows = query_listings(q=q, min_price=min_price, max_price=max_price, limit=limit)
	return render_template("listings.html", rows=rows, q=q, min=min_price, max=max_price, limit=limit, msg=msg, err=err, format_price=format_price)

@app.route("/export")
def export_text():
	q = request.args.get("q", "").strip()
	min_q = request.args.get("min", "").strip()
	max_q = request.args.get("max", "").strip()
	limit_q = request.args.get("limit", "").strip()
	min_price = int(min_q) if min_q.isdigit() else None
	max_price = int(max_q) if max_q.isdigit() else None
	limit = int(limit_q) if limit_q.isdigit() else 1000
	rows = query_listings(q=q, min_price=min_price, max_price=max_price, limit=limit)
	lines: List[str] = []
	for title, url, pv, pc, desc, loc in rows:
		lines.append(f"Title: {title or ''}")
		lines.append(f"URL: {url or ''}")
		lines.append(f"Price: {format_price(pv, pc)}")
		lines.append(f"Location: {loc or '—'}")
		lines.append(f"Description: {desc or ''}")
		lines.append("")  # blank line separator
	text = "\n".join(lines)
	return Response(text, mimetype="text/plain; charset=utf-8")

@app.route("/clear", methods=["POST"])
def clear():
	confirm = (request.form.get("confirm") or "").strip().upper()
	if confirm == "DELETE":
		try:
			clear_db_rows()
			return redirect(url_for("index", msg="Database cleared."))
		except Exception as e:
			return redirect(url_for("index", msg=f"Failed to clear DB: {e}", err="1"))
	else:
		return redirect(url_for("index", msg="Confirmation failed. Type DELETE to confirm.", err="1"))

if __name__ == "__main__":
	port = int(os.getenv("PORT", "5000"))
	app.run(host="127.0.0.1", port=port, debug=True)
