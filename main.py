import re
import sys
import time
import random
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple, Dict, Any
from config import CONFIG  # externalized configuration
from db import ensure_db, insert_listing, insert_listing_with_details
from gui import review_listings
import unicodedata
import os
from urllib.parse import urlparse

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

 # radius-based geocoding removed

# Words that are not valid locations (avoid picking labels like 'Cena')
BAD_LOC_WORDS = {
	"cena", "stav", "ponuka", "nabidka", "nabídka", "kategoria", "kategória",
	"kategorie", "predaj", "prodej",
	# common non-location words seen in snippets (normalized comparisons)
	"predam", "predám", "predavam", "predávam", "kupim", "kúpim", "zdravim", "ahojte",
	"parametre", "konfiguracia", "konfigurácia", "model", "specialita",
	"zmazat", "upravit", "topovat", "zmazať", "upraviť", "topovať",
	"the crew", "sony", "lenovo", "hp", "dell", "gddr5", "elado", "volat", "volajte",
}

def _valid_location_text(s: Optional[str]) -> bool:
	if not s:
		return False
	t = _normalize_text(s)
	if len(t) < 3:
		return False
	if any(b in t for b in BAD_LOC_WORDS):
		return False
	return any(ch.isalpha() for ch in t)


@dataclass
class Listing:
	title: str
	url: str
	price_value: Optional[int]
	price_currency: Optional[str]
	description: Optional[str] = None
	location: Optional[str] = None


def _require_deps():
	if requests is None or BeautifulSoup is None:
		print(
			"Missing dependencies. Please install with: pip install -r requirements.txt",
			file=sys.stderr,
		)
		sys.exit(1)
	global SESSION
	if SESSION is None:
		try:
			SESSION = requests.Session()
		except Exception:
			SESSION = requests


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


def _respect_rate_limit(host: str, min_interval: float) -> None:
	if min_interval <= 0:
		return
	last = LAST_REQUEST_AT.get(host)
	if last is None:
		return
	elapsed = time.time() - last
	if elapsed < min_interval:
		sleep_for = min_interval - elapsed + random.uniform(0.05, 0.25)
		time.sleep(max(0.0, sleep_for))


def http_get(url: str, params: Optional[dict] = None, timeout: int = 20,
			retries: int = 3, backoff_start: float = 5.0, backoff_max: float = 60.0,
			min_interval: Optional[float] = None) -> Optional[str]:
	# Use a single session and polite pacing; add backoff on 429/503
	global SESSION
	if SESSION is None:
		_require_deps()
		# _require_deps creates SESSION
	host = urlparse(url).netloc
	min_gap = float(CONFIG.get("request_min_interval", 2.5)) if min_interval is None else float(min_interval)
	headers = {
		"User-Agent": USER_AGENT,
		"Accept-Language": "sk-SK,sk;q=0.9,cs;q=0.8,en-US;q=0.7,en;q=0.6",
	}
	attempt = 0
	while True:
		_respect_rate_limit(host, min_gap)
		try:
			resp = SESSION.get(url, params=params, headers=headers, timeout=timeout)
			LAST_REQUEST_AT[host] = time.time()
			status = resp.status_code
			if status == 200:
				return resp.text
			if status in (429, 503):
				# Rate limited or service unavailable: backoff with jitter, honor Retry-After
				retry_after = resp.headers.get("Retry-After")
				if retry_after:
					try:
						wait_s = float(retry_after)
					except ValueError:
						wait_s = backoff_start
				else:
					wait_s = min(backoff_max, backoff_start * (2 ** attempt)) + random.uniform(0.25, 0.75)
				print(f"HTTP {status} for {resp.url} — backing off {wait_s:.1f}s", file=sys.stderr)
				attempt += 1
				if attempt > retries:
					return None
				time.sleep(wait_s)
				continue
			# Other non-200
			print(f"HTTP {status} for {resp.url}", file=sys.stderr)
			return None
		except Exception as e:
			print(f"Request failed: {e}", file=sys.stderr)
			attempt += 1
			if attempt > retries:
				return None
			wait_s = min(backoff_max, backoff_start * (2 ** (attempt - 1))) + random.uniform(0.1, 0.4)
			time.sleep(wait_s)


LISTING_HREF_RE = re.compile(r"https?://(?:[a-z0-9-]+\.)?bazos\.(sk|cz)/inzerat/\d+/.+?\.php")
POSTAL_RE = re.compile(r"\b\d{3}\s?\d{2}\b")


def _extract_location_near_anchor(a_tag, title_hint: Optional[str] = None) -> Optional[str]:
	# Try to read the table row that contains the anchor; on Bazos, city is a separate line
	def _looks_like_city(s: str) -> bool:
		# Allow 1-3 words, each starting uppercase (diacritics ok), rest mostly lowercase
		words = [w for w in re.split(r"\s+", s.strip()) if w]
		if not (1 <= len(words) <= 3):
			return False
		for w in words:
			if any(ch.isdigit() for ch in w):
				return False
			# Accept hyphens in names like "Banská Bystrica" or "Uherské Hradiště" (no hyphens, but keep simple)
			w_clean = re.sub(r"[-'’]", "", w)
			if not w_clean:
				return False
			# Title case heuristic: first char uppercase, rest not all uppercase
			if not w_clean[0].isalpha() or not w_clean[0].isupper():
				return False
			rest = w_clean[1:]
			if rest and sum(c.isupper() for c in rest) > len(rest) // 2:
				return False
		return True

	def pick_from_text(text: str, title_norm: str) -> Optional[str]:
		if not text:
			return None
		lines = [ln.strip() for ln in text.split("\n") if ln and ln.strip()]
		# Precompute postal indices
		postal_idx = [i for i, ln in enumerate(lines) if POSTAL_RE.search(ln)]
		# Prefer the line next to a postal code like "010 01" (usually previous line is the city)
		for i in postal_idx:
			prev = lines[i - 1] if i > 0 else None
			nxt = lines[i + 1] if (i + 1) < len(lines) else None
			for cand in [prev, nxt]:
				if not cand:
					continue
				if not _valid_location_text(cand):
					continue
				ln_norm = _normalize_text(cand)
				if title_norm and (ln_norm == title_norm or title_norm in ln_norm or ln_norm in title_norm):
					continue
				# Prefer city-like formatting and short strings
				if _looks_like_city(cand) and len(cand) <= 32:
					return cand
		# Fallback: first plausible short line that isn't a price or views
		for idx, ln in enumerate(lines):
			if not _valid_location_text(ln):
				continue
			if PRICE_RE.search(ln):
				continue
			# avoid lines like "257 x"
			if re.search(r"\b\d+\s*x\b", _normalize_text(ln)):
				continue
			# avoid date tags like "[12.10. 2025]" or labels
			if re.search(r"\[\d{1,2}\.\d{1,2}\.\s*\d{4}\]", ln):
				continue
			ln_norm = _normalize_text(ln)
			if title_norm and (ln_norm == title_norm or title_norm in ln_norm or ln_norm in title_norm):
				continue
			# skip lines ending with colon/comma typical for labels or intros
			if ln.endswith(":") or ln.endswith(","):
				continue
			# Heuristic: locations are short and have 0 digits
			if len(ln) > 40 or any(ch.isdigit() for ch in ln):
				continue
			# If close to a postal code line, prefer it
			if any(abs(idx - pi) <= 2 for pi in postal_idx) and _looks_like_city(ln):
				return ln
			# Otherwise, accept only city-like TitleCase names
			if _looks_like_city(ln):
				return ln
		return None

	row = a_tag.find_parent("tr")
	if row is not None:
		txt = row.get_text("\n", strip=True)
		title_norm = _normalize_text(title_hint or a_tag.get_text(strip=True) or "")
		loc = pick_from_text(txt, title_norm)
		if loc:
			return loc
	# Walk up a few parents as a secondary attempt
	container = a_tag
	for _ in range(4):
		parent = getattr(container, "parent", None)
		if not parent or not getattr(parent, "get_text", None):
			break
		txt = parent.get_text("\n", strip=True)
		title_norm = _normalize_text(title_hint or a_tag.get_text(strip=True) or "")
		loc = pick_from_text(txt, title_norm)
		if loc:
			return loc
		container = parent
	return None


def extract_listings_from_search(html: str, site: str, max_price: Optional[int] = None) -> List[Listing]:
	soup = BeautifulSoup(html, "html.parser")

	anchors = soup.find_all("a", href=True)
	seen: Set[str] = set()
	listings: List[Listing] = []

	for a in anchors:
		href = a["href"].strip()
		# Normalize relative URLs if any
		if href.startswith("/") and "/inzerat/" in href:
			href = f"https://www.bazos.{site}{href}"
		elif href.startswith("inzerat/"):
			href = f"https://www.bazos.{site}/{href}"
		if not LISTING_HREF_RE.match(href):
			continue


		if href in seen:
			continue
		seen.add(href)

		title = a.get_text(strip=True)
		if not title:
			# Try title attribute
			title = (a.get("title") or "").strip()
		if not title:
			# Try parent heading
			h = a.find_parent(["h2", "h3"]) or a.find_next(["h2", "h3"]) or a.find_previous(["h2", "h3"]) 
			if h:
				title = h.get_text(strip=True)
		if not title:
			# Fallback to URL slug
			m = re.search(r"/inzerat/\d+/([^/]+)\.php", href)
			if m:
				slug = m.group(1)
				title = slug.replace("-", " ")
		# Try to find surrounding text to parse price (robust selection)
		price_value, price_currency = find_price_near_anchor(a, max_price=max_price, site=site)

		# Extract location near the anchor using postal code heuristic (avoid title duplication)
		location = _extract_location_near_anchor(a, title)

		listings.append(
			Listing(
				title=title,
				url=href,
				price_value=price_value,
				price_currency=price_currency,
				location=location,
			)
		)

	return listings


PRICE_RE = re.compile(
	r"(?P<value>\d{1,3}(?:[\u00A0\s]\d{3})*|\d+)(?:[\.,]\d{2})?\s*(?P<cur>€|eur|eura|Kč)",
	re.IGNORECASE,
)
SHIPPING_HINT_RE = re.compile(r"(?i)\b(postovne|poštovne|doprava|zaslanie|zasielka|odber|dobierka|kurier|kuriér|shipping|posta|pošta|osobny odber|osobný odber)\b")


def _parse_price_match(m: re.Match) -> Tuple[Optional[int], Optional[str]]:
	value_raw = m.group("value").replace("\u00A0", " ").replace(" ", "")
	try:
		value = int(value_raw.replace(",", ".").split(".")[0])
	except ValueError:
		value = None
	cur = m.group("cur")
	cur = "€" if isinstance(cur, str) and cur.lower() in ("eur", "eura") else cur
	return value, cur


def find_price_near_anchor(a_tag, max_price: Optional[int] = None, site: str = "sk") -> Tuple[Optional[int], Optional[str]]:
	# Walk up to a reasonable container and inspect its text; collect multiple candidates
	candidates: List[Tuple[int, str, float]] = []  # (value, currency, score)
	container = a_tag
	depth = 0
	while container is not None and depth < 4:
		parent = getattr(container, "parent", None)
		if parent is None:
			break
		container = parent
		text = container.get_text(" ", strip=True)
		if not text:
			depth += 1
			continue
		# Find all price occurrences in this text block
		for m in PRICE_RE.finditer(text):
			val, cur = _parse_price_match(m)
			if val is None:
				continue
			# currency sanity per site
			if site == "sk" and cur not in ("€", None, "eur", "eura"):
				continue
			if site == "cz" and cur not in ("Kč", None):
				continue
			# score baseline by value (prefer higher, assuming item price > shipping)
			score = float(val)
			# penalize if shipping-related words are near the match window
			window_start = max(0, m.start() - 25)
			window_end = min(len(text), m.end() + 25)
			window = text[window_start:window_end]
			if SHIPPING_HINT_RE.search(window):
				score *= 0.25
			# if max_price is provided and this is extremely low (< 70% of max), penalize hard
			if max_price is not None and val < 0.7 * max_price:
				score *= 0.5
			candidates.append((val, ("€" if (cur and str(cur).lower() in ("eur", "eura")) else (cur or ("€" if site == "sk" else "Kč"))), score))
		depth += 1
	if not candidates:
		return None, None
	# Choose the highest score; this typically selects the actual item price over shipping
	candidates.sort(key=lambda t: t[2], reverse=True)
	best_val, best_cur, _ = candidates[0]
	return best_val, best_cur


def fetch_description(url: str) -> Optional[str]:
	html = http_get(url)
	if not html:
		return None
	soup = BeautifulSoup(html, "html.parser")
	# Try common containers for description
	candidates = []
	candidates += soup.select("div.popis")
	candidates += soup.select("div#popis")
	candidates += soup.select("div.inzeratydetail")
	candidates += soup.select("div#wrap div.content")

	for node in candidates:
		text = node.get_text("\n", strip=True)
		if text and len(text) > 20:
			return text
	# Fallback: longest paragraph
	paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all(["p", "div"])]
	paragraphs = [p for p in paragraphs if len(p) > 40]
	return max(paragraphs, key=len) if paragraphs else None


def fetch_location(url: str) -> Optional[str]:
	html = http_get(url)
	if not html:
		return None
	soup = BeautifulSoup(html, "html.parser")
	# 1) Labeled table fields like 'Lokalita:'
	for td in soup.find_all("td"):
		label = td.get_text(" ", strip=True)
		if re.search(r"\b(lokalita|okres|kraj|mesto|mesto/obec)\b", label, re.IGNORECASE):
			sib = td.find_next_sibling("td")
			if sib:
				val = sib.get_text(" ", strip=True)
				if _valid_location_text(val):
					return val
	# 2) Labeled spans/divs
	for node in soup.find_all(string=re.compile(r"\b(lokalita|okres|kraj|mesto)\b", re.IGNORECASE)):
		parent = getattr(node, 'parent', None)
		if not parent:
			continue
		sib = parent.find_next_sibling()
		if sib:
			val = sib.get_text(" ", strip=True)
			if _valid_location_text(val):
				return val
	# 3) Regex over full text
	full = soup.get_text("\n", strip=True)
	m = re.search(r"(?i)Lokalita\s*:\s*([^\n\r|]+)", full)
	if m and _valid_location_text(m.group(1)):
		return m.group(1).strip()
	m = re.search(r"(?i)okres\s+([A-Za-zÀ-ÿ\-\s]{2,40})", full)
	if m and _valid_location_text(m.group(1)):
		return m.group(1).strip()
	# 4) Fallback: look for short plausible tokens near contact box
	candidates: List[str] = []
	for node in soup.select("div#wrap"):
		try:
			candidates.append(node.get_text("\n", strip=True))
		except Exception:
			pass
	for txt in candidates:
		for part in re.split(r"[\|\n,]", txt):
			p = part.strip()
			if 2 <= len(p) <= 48 and _valid_location_text(p):
				return p
	return None


# geocoding removed


def search_bazos(keyword: str, max_price: Optional[int], site: str = "sk", max_pages: int = 1,
				 include_content: bool = False, delay_range: tuple = (0.8, 1.6), min_price: Optional[int] = None) -> List[Listing]:
	if site not in ("sk", "cz"):
		raise ValueError("site must be 'sk' or 'cz'")

	base_url = BAZOS_SEARCH_URL[site]
	all_listings: List[Listing] = []
	seen_urls: Set[str] = set()

	for page in range(1, max_pages + 1):
		params = build_search_params(keyword, max_price, page, min_price=min_price)
		html = http_get(base_url, params, timeout=20)
		if not html:
			break

		page_listings = extract_listings_from_search(html, site, max_price=max_price)
		if not page_listings:
			# No more results
			break

		filtered: List[Listing] = []
		for lst in page_listings:
			if lst.url in seen_urls:
				continue
			seen_urls.add(lst.url)
			if lst.price_value is not None:
				# Respect currency per site
				if site == "sk" and (lst.price_currency not in ("€", None)):
					continue
				if site == "cz" and (lst.price_currency not in ("Kč", None)):
					continue
				# Apply min/max price bounds when parsed
				if max_price is not None and lst.price_value > max_price:
					continue
				if min_price is not None and lst.price_value < min_price:
					continue
			filtered.append(lst)

		if include_content:
			for lst in filtered:
				time.sleep(random.uniform(*delay_range))
				lst.description = fetch_description(lst.url)

		all_listings.extend(filtered)
		time.sleep(random.uniform(*delay_range))

	return all_listings


def print_listings(listings: Iterable[Listing], as_json: bool = False) -> None:
	if as_json:
		try:
			import json
			print(json.dumps([l.__dict__ for l in listings], ensure_ascii=False, indent=2))
		except Exception as e:
			print(f"Failed to serialize JSON: {e}", file=sys.stderr)
	else:
		count = 0
		for l in listings:
			price = f"{l.price_value}{l.price_currency or ''}" if l.price_value else "?"
			loc = f" | {l.location}" if l.location else ""
			line = f"- {price:>6}{loc} | {l.title} | {l.url}"
			print(line)
			if l.description:
				# Print a short preview
				desc = re.sub(r"\s+", " ", l.description).strip()
				if len(desc) > 200:
					desc = desc[:200] + "..."
				print(f"    {desc}")
			count += 1
		if count == 0:
			print("No listings found under the given criteria.")


def telegram_enabled() -> bool:
	return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def telegram_send_message(text: str) -> None:
	token = os.getenv("TELEGRAM_BOT_TOKEN")
	chat_id = os.getenv("TELEGRAM_CHAT_ID")
	if not token or not chat_id:
		return
	try:
		import requests as _rq
		url = f"https://api.telegram.org/bot{token}/sendMessage"
		payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
		_rq.post(url, json=payload, timeout=10)
	except Exception as e:
		print(f"Telegram send failed: {e}", file=sys.stderr)


def telegram_send_chunks(text: str, chunk_size: int = 3800) -> None:
	# Telegram max length ~4096; keep margin
	s = text.strip()
	while s:
		if len(s) <= chunk_size:
			telegram_send_message(s)
			break
		cut = s.rfind("\n", 0, chunk_size)
		if cut == -1 or cut < chunk_size // 2:
			cut = chunk_size
		telegram_send_message(s[:cut].rstrip())
		s = s[cut:].lstrip()


def load_env_file(path: str = ".env") -> None:
	try:
		if not os.path.isfile(path):
			return
		with open(path, "r", encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if not line or line.startswith("#"):
					continue
				if "=" not in line:
					continue
				k, v = line.split("=", 1)
				k = k.strip()
				v = v.strip().strip('"').strip("'")
				if k and (k not in os.environ):
					os.environ[k] = v
	except Exception as e:
		print(f"Failed to load {path}: {e}", file=sys.stderr)


def set_interval(seconds: int) -> None:
	CONFIG["interval"] = int(max(1, seconds))


def add_search(keyword: str, max_price: Optional[int], site: str = "sk", pages: int = 2, include_content: bool = False) -> None:
	CONFIG.setdefault("searches", []).append({
		"keyword": keyword,
		"max_price": max_price,
		"site": site,
		"pages": pages,
		"include_content": include_content,
	})


def clear_searches() -> None:
	CONFIG["searches"] = []


def _normalize_text(text: Optional[str]) -> str:
	if not text:
		return ""
	# Lowercase and strip accents for robust matching (e.g., 'Kúpim' -> 'kupim')
	t = unicodedata.normalize("NFKD", text.lower())
	return "".join(ch for ch in t if not unicodedata.combining(ch))


def matches_ignore(lst: Listing, patterns: List[str]) -> bool:
	if not patterns:
		return False
	title_norm = _normalize_text(lst.title)
	desc_norm = _normalize_text(lst.description)
	# Normalize patterns as well
	norm_patterns = [_normalize_text(p) for p in patterns if isinstance(p, str)]
	for p in norm_patterns:
		if p and (p in title_norm or (desc_norm and p in desc_norm)):
			return True
	return False


def matches_query(lst: Listing, query: str, mode: str = "title") -> bool:
	q = _normalize_text(query)
	if not q:
		return True
	title_norm = _normalize_text(lst.title)
	desc_norm = _normalize_text(lst.description)
	m = (mode or "title").lower()
	if m in ("title", "t"):
		return q in title_norm
	if m in ("description", "desc", "d", "text"):
		return bool(desc_norm) and q in desc_norm
	# default: title or description
	return (q in title_norm) or (bool(desc_norm) and q in desc_norm)


def _city_match(location_text: Optional[str], include: List[str], exclude: List[str]) -> bool:
	loc = _normalize_text(location_text)
	inc = [_normalize_text(x) for x in (include or []) if isinstance(x, str)]
	exc = [_normalize_text(x) for x in (exclude or []) if isinstance(x, str)]
	# If include provided, require at least one include token be present
	if inc:
		if not loc or not any(token and token in loc for token in inc):
			return False
	# Exclude wins if any token matches
	if exc and loc and any(token and token in loc for token in exc):
		return False
	return True


def load_json_file(path: Optional[str]) -> Optional[Dict[str, Any]]:
	if not path:
		return None
	try:
		import json
		with open(path, "r", encoding="utf-8") as f:
			return json.load(f)
	except FileNotFoundError:
		return None
	except Exception as e:
		print(f"Failed to read {path}: {e}", file=sys.stderr)
		return None


def save_json_file(path: Optional[str], data: Dict[str, Any]) -> None:
	if not path:
		# No-op when state file path is disabled
		return
	try:
		import json
		with open(path, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
	except Exception as e:
		print(f"Failed to write {path}: {e}", file=sys.stderr)


def ensure_state(path: Optional[str]) -> Dict[str, Any]:
	state = load_json_file(path) if path else None
	if not isinstance(state, dict):
		state = {"seen": {}}
	if "seen" not in state or not isinstance(state["seen"], dict):
		state["seen"] = {}
	return state


def dedupe_new(listings: List[Listing], state: Dict[str, Any], key: str, max_keep: int = 500) -> List[Listing]:
	seen: Dict[str, float] = state.get("seen", {}).get(key, {}) or {}
	new_items: List[Listing] = []
	now = time.time()
	for lst in listings:
		if lst.url in seen:
			continue
		new_items.append(lst)
		seen[lst.url] = now
	# prune
	if len(seen) > max_keep:
		# keep latest
		items = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:max_keep]
		seen = dict(items)
	# store back
	if "seen" not in state:
		state["seen"] = {}
	state["seen"][key] = seen
	return new_items


def run_config_cycle(config: Dict[str, Any], state: Dict[str, Any], state_path: str) -> None:
	searches = config.get("searches") or []
	if not isinstance(searches, list) or not searches:
		print("Config has no searches[]", file=sys.stderr)
		return

	# Order searches by ascending min_price (lowest first), then by max_price
	def _to_int(val, default):
		try:
			return int(val)
		except Exception:
			return default

	_ordered = sorted(
		[s for s in searches if isinstance(s, dict)],
		key=lambda s: (
			_to_int(s.get("min_price"), 0),
			_to_int(s.get("max_price"), 10**9),
		),
	)

	# Read pacing config
	gap_range = config.get("search_gap_range") or (7.0, 15.0)
	if not (isinstance(gap_range, (list, tuple)) and len(gap_range) == 2):
		gap_range = (7.0, 15.0)
	req_delay_range = config.get("request_delay_range") or (1.2, 2.4)
	if not (isinstance(req_delay_range, (list, tuple)) and len(req_delay_range) == 2):
		req_delay_range = (1.2, 2.4)

	for idx, s in enumerate(_ordered):
		if not isinstance(s, dict):
			continue
		keyword = str(s.get("keyword", "")).strip()
		if not keyword:
			continue
		site = s.get("site", "sk")
		try:
			max_price = int(s.get("max_price")) if s.get("max_price") is not None else None
		except Exception:
			max_price = None
		try:
			min_price = int(s.get("min_price")) if s.get("min_price") is not None else None
		except Exception:
			min_price = None
		pages = int(s.get("pages", 2))
		include_content = bool(s.get("include_content", False))

		listings = search_bazos(
			keyword=keyword,
			max_price=max_price,
			site=site,
			max_pages=max(1, pages),
			include_content=include_content,
			delay_range=tuple(req_delay_range),
			min_price=min_price,
		)
		# Match scope: title / description / both
		match_in = str(s.get("match_in", "title")).lower()
		need_desc = match_in in ("description", "desc", "d", "text", "title_or_description", "both")
		# If matching requires description but we didn't fetch it, fetch minimally
		if need_desc and not include_content:
			for lst in listings:
				if not lst.description:
					time.sleep(random.uniform(0.8, 1.6))
					lst.description = fetch_description(lst.url)
		# Apply query matching filter
		listings = [l for l in listings if matches_query(l, keyword, match_in)]
		# Apply ignore patterns (accent-insensitive) on title/description
		ignore_patterns = config.get("ignore") or []
		if isinstance(ignore_patterns, list) and ignore_patterns:
			listings = [l for l in listings if not matches_ignore(l, ignore_patterns)]
		# Optional: city filter from CONFIG
		cities_cfg = config.get("cities") or {}
		include_cities = cities_cfg.get("include") if isinstance(cities_cfg, dict) else None
		exclude_cities = cities_cfg.get("exclude") if isinstance(cities_cfg, dict) else None

		# Prefer include/exclude textual filtering when provided
		if (include_cities or exclude_cities):
			filtered_text: List[Listing] = []
			for lst in listings:
				# Always fetch detail-location to avoid snippet labels like 'Cena'
				time.sleep(random.uniform(0.2, 0.5))
				loc = fetch_location(lst.url)
				if loc:
					lst.location = loc
				if _city_match(lst.location, include_cities or [], exclude_cities or []):
					filtered_text.append(lst)
			listings = filtered_text
		# No radius fallback; radius filtering removed
		key = f"{site}:{keyword}:{min_price}:{max_price}:{pages}:{include_content}"
		new_listings = dedupe_new(listings, state, key)
		if new_listings:
			print(f"\n=== New listings for '{keyword}' ({site}, <= {max_price}) ===")
			print_listings(new_listings, as_json=False)
			# Optionally review in GUI and save accepted items to sqlite
			try:
				if bool(config.get("gui")):
					# Prepare DB
					db_path = config.get("db_file") or "gooddeal.db"
					ensure_db(db_path)
					# Guess a default type from the keyword (can be overridden in GUI)
					def _guess_type(s: str) -> str:
						s2 = _normalize_text(s)
						if any(tok in s2 for tok in ("rtx", "gtx", "rx ", "gpu", "grafika", "graphics")):
							return "gpu"
						if "iphone" in s2 or "apple iphone" in s2:
							return "iphone"
						if any(tok in s2 for tok in ("ps5", "playstation", "xbox", "switch", "steam deck")):
							return "console"
						if any(tok in s2 for tok in ("macbook", "ipad", "airpods", "apple watch")):
							return "apple"
						return "other"
					# Pack listings for GUI: include description, guessed type, and placeholder for rating
					gui_input = [(
						l.title,
						l.url,
						l.price_value,
						l.price_currency,
						l.location,
						l.description,
						_guess_type(keyword),
						None,  # rating to be filled in GUI
					) for l in new_listings]
					accepted = review_listings(gui_input)
					for title, url, price_val, cur, loc, type_val, rating_val in accepted:
						# Route to category tables with product_name (keyword) and rating
						insert_listing_with_details(
							db_path,
							title=title,
							url=url,
							location=loc,
							price=price_val,
							currency=cur,
							type_=type_val,
							product_name=keyword,
							listing_title=title,
							rating=rating_val,
							params_json=None,
						)
			except Exception as e:
				print(f"GUI/DB processing failed: {e}", file=sys.stderr)
			# Telegram summary (optional, single message)
			if telegram_enabled():
				lines = [f"New {keyword} ({site} <= {max_price}): {len(new_listings)} item(s)"]
				for l in new_listings:
					price = f"{l.price_value}{l.price_currency or ''}" if l.price_value else "?"
					loc = f" {l.location}" if l.location else ""
					lines.append(f"- {price}{loc} | {l.title}\n{l.url}")
				telegram_send_chunks("\n".join(lines))
		else:
			print(f"\n No new listings for '{keyword}' ({site}, <= {max_price}).")
		# Polite pause between searches
		if idx < len(_ordered) - 1:
			time.sleep(random.uniform(*gap_range))
def main() -> int:
	_require_deps()
	# Load .env for TELEGRAM_*/LOCATION_* if present
	load_env_file()
	config = CONFIG
	interval = int(config.get("interval", 300))
	# If state_file is None, persistence is disabled (no read/write)
	state_path = config.get("state_file")
	state = ensure_state(state_path)

    # No LOCATION_* env; radius filtering removed

	# Decide whether to run once or watch based on config
	watch = bool(config.get("watch", False))
	if not watch:
		run_config_cycle(config, state, state_path)
		save_json_file(state_path, state)
		return 0
	print(f"Starting watch loop: every {interval}s. Ctrl+C to stop.")
	try:
		while True:
			run_config_cycle(config, state, state_path)
			save_json_file(state_path, state)
			time.sleep(max(1, interval))
	except KeyboardInterrupt:
		print("\nStopped.")
		return 0


if __name__ == "__main__":
	sys.exit(main())