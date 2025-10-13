import re
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
from config import CONFIG  # externalized configuration
import unicodedata
import os
from urllib.parse import urlparse, urljoin

try:
	import requests
	from bs4 import BeautifulSoup
except Exception as e:
	# Defer import error until runtime with a clear message
	requests = None  # type: ignore
	BeautifulSoup = None  # type: ignore

# Reused HTTP session and per-host rate limiting
SESSION = None  # type: ignore
LAST_REQUEST_AT: Dict[str, float] = {}

# CONFIG is now imported from config.py

BAZOS_SEARCH_URL = {
	"sk": "https://www.bazos.sk/search.php",
	"cz": "https://www.bazos.cz/search.php",
}


USER_AGENT = (
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
	"AppleWebKit/537.36 (KHTML, like Gecko) "
	"Chrome/127.0.0.0 Safari/537.36"
)

@dataclass
class Listing:
	title: str
	url: str
	price_value: Optional[int]
	price_currency: Optional[str]
	description: Optional[str] = None
	location: Optional[str] = None

def build_search_params(keyword: str, max_price: Optional[int], page: int, min_price: Optional[int] = None) -> dict:
	params = {
		"hledat": keyword,
		"rubriky": "0",  # search all sections (we'll post-filter to pc)
		"hlokalita": "",
		"humkreis": "0",
		"order": "2",  # sort by price asc (observed behavior)
		"strana": str(page),
	}
	if max_price is not None:
		params["cenado"] = str(max_price)
	if min_price is not None:
		params["cenaod"] = str(min_price)
	# Optional region filter via environment or CONFIG
	try:
		hlok_env = os.getenv("HLOKALITA")
		hlok_cfg = CONFIG.get("hlokalita") if isinstance(CONFIG, dict) else None
		hlok = (hlok_env if hlok_env is not None else (str(hlok_cfg) if hlok_cfg is not None else "")).strip()
		if hlok:
			# Normalize '+' to space in case value is pasted as '811+01'
			params["hlokalita"] = hlok.replace("+", " ")
			hum_env = os.getenv("HUMKREIS")
			hum_cfg = CONFIG.get("humkreis") if isinstance(CONFIG, dict) else None
			hum = (hum_env if hum_env is not None else (str(hum_cfg) if hum_cfg is not None else "")).strip()
			if hum:
				params["humkreis"] = hum
	except Exception:
		# Non-fatal if env/config parsing fails
		pass
	return params

def _get_session():
	# create/reuse a single requests session with headers
	global SESSION
	if SESSION is None:
		SESSION = requests.Session()
		SESSION.headers.update({
			"User-Agent": USER_AGENT,
			"Accept-Language": "en-US,en;q=0.9,sk;q=0.8,cs;q=0.8",
		})
	return SESSION

def _throttled_get(url: str, params: Optional[Dict[str, Any]] = None, min_delay: float = 1.0) -> str:
	# rate-limit per host and GET the page
	host = urlparse(url).netloc or ""
	now = time.time()
	last = LAST_REQUEST_AT.get(host, 0.0)
	wait = min_delay - (now - last)
	if wait > 0:
		time.sleep(wait)
	session = _get_session()
	resp = session.get(url, params=params, timeout=(10, 20))
	resp.raise_for_status()
	LAST_REQUEST_AT[host] = time.time()
	return resp.text

def parse_price(raw: str) -> Tuple[Optional[int], Optional[str]]:
	# Normalize spaces and common forms like '1 500 €' or '1.500 Kč'
	if not raw:
		return None, None
	s = unicodedata.normalize("NFKC", raw)
	for sp in ("\u00A0", "\u202F", "\u2009"):
		s = s.replace(sp, " ")
	s = s.strip()
	low = s.lower()
	# Skip non-numeric price labels
	if any(w in low for w in ["dohodou", "ponúknite", "ponuknite", "zadarmo", "free"]):
		return None, None
	currency: Optional[str] = None
	if "€" in s or " eur" in low:
		currency = "EUR"
	elif "kč" in low or "czk" in low:
		currency = "CZK"
	# Keep only digits and separators, then read the first number block
	num_part = re.sub(r"[^\d.,\s]", " ", s)  # drop currency/symbols like '€', ',-'
	m = re.search(r"(\d[\d\s.,]*)", num_part)
	if not m:
		return None, currency
	num = re.sub(r"[^\d]", "", m.group(1))  # remove spaces, dots, commas
	if not num:
		return None, currency
	return int(num), currency

def fetch_listings(site: str, keyword: str, min_price: Optional[int], max_price: Optional[int], pages: int, include_content: bool, match_in: str) -> List[Listing]:
	base_url = BAZOS_SEARCH_URL.get(site.lower())
	if not base_url:
		raise ValueError(f"Unknown site '{site}'. Use one of: {', '.join(BAZOS_SEARCH_URL.keys())}")
	results: List[Listing] = []
	pages = max(1, int(pages or 1))
	for page in range(1, pages + 1):
		params = build_search_params(keyword=keyword, max_price=max_price, page=page, min_price=min_price)
		html = _throttled_get(base_url, params=params)
		soup = BeautifulSoup(html, "html.parser")
		container = soup.select_one(".maincontent") or soup

		for block in container.select("div.inzeraty.inzeratyflex"):
			title_el = block.select_one("div.inzeratynadpis h2.nadpis")
			if not title_el:
				continue
			title = title_el.get_text(" ", strip=True)
			link_el = block.select_one("div.inzeratynadpis a")
			url = urljoin(base_url, link_el.get("href", "")) if link_el and link_el.get("href") else ""
			# price parsing (handles '1 500 €', '1.500 Kč', etc.)
			price_el = block.select_one("div.inzeratycena") or block.select_one("div.inzeratycena b")
			price_value, price_currency = parse_price(price_el.get_text(" ", strip=True) if price_el else "")
			# get location text like "Košice<br/>040 01" -> "Košice 040 01"
			location_el = block.select_one("div.inzeratylok")
			location = location_el.get_text(" ", strip=True) if location_el else None
			results.append(Listing(
				title=title,
				url=url,
				price_value=price_value,
				price_currency=price_currency,
				description=None,
				location=location
			))
	return results

def format_price_for_display(value: Optional[int], currency: Optional[str]) -> str:
	if value is None:
		return "—"
	num = f"{value:,}".replace(",", " ")
	if currency == "EUR":
		return f"{num} €"
	if currency == "CZK":
		return f"{num} Kč"
	return f"{num} {currency}" if currency else num

def render_listings(listings: List[Listing]) -> str:
	lines: List[str] = []
	for l in listings:
		lines.append(f"{l.title} | Price: {format_price_for_display(l.price_value, l.price_currency)} | Location: {l.location or '-'}| Link: {l.url or '-'}")
	return "\n".join(lines)

def dedupe_listings(listings: List[Listing]) -> List[Listing]:
	seen: set[str] = set()
	unique: List[Listing] = []
	for l in listings:
		key = (l.url or "").strip().lower()
		if not key:
			title_key = re.sub(r"\s+", " ", (l.title or "").strip().lower())
			loc_key = re.sub(r"\s+", " ", (l.location or "").strip().lower())
			key = f"{title_key}|{loc_key}|{l.price_value or ''}|{(l.price_currency or '').lower()}"
		if key in seen:
			continue
		seen.add(key)
		unique.append(l)
	return unique


# Replace the hardcoded single search with config-driven searches
searches = CONFIG.get("searches", [])
if not searches:
	print("No searches configured in CONFIG['searches']. Please add at least one search item.")
	sys.exit(1)

for s in searches:
	site = s.get("site") or CONFIG.get("site", "sk")
	keyword = s.get("keyword", "").strip()
	if not keyword:
		continue
	min_price = s.get("min_price")
	max_price = s.get("max_price")
	pages = s.get("pages", CONFIG.get("default_pages", 1))

	results = fetch_listings(site, keyword, min_price, max_price, pages, False, "title")
	results = dedupe_listings(results)
	header = (
		f"=== {keyword} ({site}) | min={min_price or '—'} | max={max_price or '—'} | "
		f"PSC={CONFIG.get('hlokalita','')} | okolie={CONFIG.get('humkreis','0')} km ==="
	)
	print(header)
	print(render_listings(results))
	print()