import tkinter as tk
import webbrowser
from typing import List, Any, Optional
# Add HTTP/HTML parsing and DB helpers
try:
	import requests
	from bs4 import BeautifulSoup
except Exception:
	requests = None  # type: ignore
	BeautifulSoup = None  # type: ignore

from db import ensure_db, insert_listing, insert_listing_with_details

USER_AGENT = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
	"AppleWebKit/537.36 (KHTML, like Gecko) "
	"Chrome/127.0.0.0 Safari/537.36"
)

def fetch_description(url: Optional[str]) -> Optional[str]:
	if not url or not requests or not BeautifulSoup:
		return None
	try:
		resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(10, 20))
		resp.raise_for_status()
		soup = BeautifulSoup(resp.text, "html.parser")
		container = soup.select_one(".maincontent") or soup
		# popisdetail contains the description; flatten text with spaces
		desc_el = container.select_one("div.popisdetail") or container.select_one(".popisdetail")
		if not desc_el:
			return None
		return desc_el.get_text(" ", strip=True)
	except Exception:
		return None

class ReviewApp:
	def __init__(self, root: tk.Tk, listings: List[Any], auto_open: bool = True):
		self.root = root
		self.root.title("Review Listings")
		try:
			self.root.attributes("-topmost", True)
		except Exception:
			pass
		self.listings = listings
		self.auto_open = auto_open
		self.i = -1

		self.title_var = tk.StringVar()
		self.price_var = tk.StringVar()
		self.loc_var = tk.StringVar()
		self.url_var = tk.StringVar()

		tk.Label(root, textvariable=self.title_var, wraplength=600, font=("Segoe UI", 12, "bold")).pack(padx=12, pady=(12, 6))
		tk.Label(root, textvariable=self.price_var).pack(padx=12, pady=2)
		tk.Label(root, textvariable=self.loc_var).pack(padx=12, pady=2)
		tk.Label(root, textvariable=self.url_var, fg="blue").pack(padx=12, pady=6)

		btns = tk.Frame(root)
		btns.pack(pady=12)
		tk.Button(btns, text="Open", width=10, command=self.open_current).pack(side=tk.LEFT, padx=5)
		tk.Button(btns, text="Approve", width=10, command=self.approve_current).pack(side=tk.LEFT, padx=5)
		tk.Button(btns, text="Decline", width=10, command=self.next_item).pack(side=tk.LEFT, padx=5)
		tk.Button(btns, text="Quit", width=8, command=self.root.destroy).pack(side=tk.LEFT, padx=5)

		self.next_item()

	def current(self) -> Optional[Any]:
		if 0 <= self.i < len(self.listings):
			return self.listings[self.i]
		return None

	def open_current(self):
		l = self.current()
		if l and getattr(l, "url", ""):
			webbrowser.open_new_tab(l.url)

	def approve_current(self):
		l = self.current()
		if not l:
			return
		# Fetch description from detail page, then save to DB with all fields
		description = fetch_description(getattr(l, "url", None))
		try:
			ensure_db()
			insert_listing_with_details(
				title=getattr(l, "title", None),
				url=getattr(l, "url", None),
				price_value=getattr(l, "price_value", None),
				price_currency=getattr(l, "price_currency", None),
				description=description if description else getattr(l, "description", None),
				location=getattr(l, "location", None),
			)
		except Exception:
			# Fallback minimal insert if detailed insert fails
			try:
				insert_listing(getattr(l, "title", None), getattr(l, "url", None))
			except Exception:
				pass
		self.next_item()

	def next_item(self):
		self.i += 1
		if self.i >= len(self.listings):
			self.root.destroy()
			return
		l = self.listings[self.i]
		title = getattr(l, "title", "") or ""
		price_value = getattr(l, "price_value", None)
		price_currency = getattr(l, "price_currency", None)
		price = (f"{price_value:,}".replace(",", " ") if isinstance(price_value, int) else "—")
		if price_currency == "EUR":
			price += " €"
		elif price_currency == "CZK":
			price += " Kč"
		self.title_var.set(title)
		self.price_var.set(f"Price: {price}")
		self.loc_var.set(f"Location: {getattr(l, 'location', '-') or '-'}")
		self.url_var.set(getattr(l, "url", "") or "-")
		if self.auto_open and getattr(l, "url", ""):
			self.open_current()

def review_listings(listings: List[Any], auto_open: bool = True):
	if not listings:
		return
	root = tk.Tk()
	ReviewApp(root, listings, auto_open=auto_open)
	root.mainloop()
