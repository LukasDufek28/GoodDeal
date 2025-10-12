import re
import sys
import time
import random
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple, Dict, Any
from config import CONFIG  # externalized configuration
import unicodedata

try:
	import requests
	from bs4 import BeautifulSoup
except Exception as e:
	# Defer import error until runtime with a clear message
	requests = None  # type: ignore
	BeautifulSoup = None  # type: ignore

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


def _require_deps():
	if requests is None or BeautifulSoup is None:
		print(
			"Missing dependencies. Please install with: pip install -r requirements.txt",
			file=sys.stderr,
		)
		sys.exit(1)


def build_search_params(keyword: str, max_price: Optional[int], page: int) -> dict:
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
	return params


def http_get(url: str, params: Optional[dict] = None, timeout: int = 20) -> Optional[str]:
	headers = {"User-Agent": USER_AGENT}
	try:
		resp = requests.get(url, params=params, headers=headers, timeout=timeout)
		if resp.status_code == 200:
			return resp.text
		else:
			print(f"HTTP {resp.status_code} for {resp.url}", file=sys.stderr)
			return None
	except requests.RequestException as e:
		print(f"Request failed: {e}", file=sys.stderr)
		return None


LISTING_HREF_RE = re.compile(r"https?://(?:[a-z0-9-]+\.)?bazos\.(sk|cz)/inzerat/\d+/.+?\.php")


def extract_listings_from_search(html: str, site: str) -> List[Listing]:
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
		# Try to find surrounding text to parse price
		price_value, price_currency = find_price_near_anchor(a)

		listings.append(
			Listing(
				title=title,
				url=href,
				price_value=price_value,
				price_currency=price_currency,
			)
		)

	return listings


PRICE_RE = re.compile(
	r"(?P<value>\d{1,3}(?:[\u00A0\s]\d{3})*|\d+)(?:[\.,]\d{2})?\s*(?P<cur>€|eur|eura|Kč)",
	re.IGNORECASE,
)


def find_price_near_anchor(a_tag) -> Tuple[Optional[int], Optional[str]]:
	# Walk up to a reasonable container and inspect its text
	container = a_tag
	for _ in range(4):
		if container.parent is None:
			break
		container = container.parent
		text = container.get_text(" ", strip=True)
		m = PRICE_RE.search(text)
		if m:
			value_raw = m.group("value").replace("\u00A0", " ").replace(" ", "")
			try:
				value = int(value_raw.replace(",", ".").split(".")[0])
			except ValueError:
				value = None
			cur = m.group("cur")
			cur = "€" if cur.lower() in ("eur", "eura") else cur
			return value, cur
	return None, None


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


def search_bazos(keyword: str, max_price: Optional[int], site: str = "sk", max_pages: int = 1,
				 include_content: bool = False, delay_range: tuple = (0.8, 1.6)) -> List[Listing]:
	if site not in ("sk", "cz"):
		raise ValueError("site must be 'sk' or 'cz'")

	base_url = BAZOS_SEARCH_URL[site]
	all_listings: List[Listing] = []
	seen_urls: Set[str] = set()

	for page in range(1, max_pages + 1):
		params = build_search_params(keyword, max_price, page)
		html = http_get(base_url, params)
		if not html:
			break

		page_listings = extract_listings_from_search(html, site)
		if not page_listings:
			# No more results
			break

		# Filter price if we couldn't parse it from snippet (since 'cenado' is already applied, this is a safety)
		filtered: List[Listing] = []
		for lst in page_listings:
			if lst.url in seen_urls:
				continue
			seen_urls.add(lst.url)
			if max_price is not None and lst.price_value is not None:
				# Respect currency per site
				if site == "sk" and (lst.price_currency not in ("€", None)):
					# Skip mismatched currency when parsed
					continue
				if site == "cz" and (lst.price_currency not in ("Kč", None)):
					continue
				if lst.price_value > max_price:
					continue
			filtered.append(lst)

		if include_content:
			for lst in filtered:
				# Be polite with rate limiting
				time.sleep(random.uniform(*delay_range))
				lst.description = fetch_description(lst.url)

		all_listings.extend(filtered)

		# Rate limiting between pages
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
			line = f"- {price:>6} | {l.title} | {l.url}"
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


def load_json_file(path: str) -> Optional[Dict[str, Any]]:
	try:
		import json
		with open(path, "r", encoding="utf-8") as f:
			return json.load(f)
	except FileNotFoundError:
		return None
	except Exception as e:
		print(f"Failed to read {path}: {e}", file=sys.stderr)
		return None


def save_json_file(path: str, data: Dict[str, Any]) -> None:
	try:
		import json
		with open(path, "w", encoding="utf-8") as f:
			json.dump(data, f, ensure_ascii=False, indent=2)
	except Exception as e:
		print(f"Failed to write {path}: {e}", file=sys.stderr)


def ensure_state(path: str) -> Dict[str, Any]:
	state = load_json_file(path)
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
	for s in searches:
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
		pages = int(s.get("pages", 2))
		include_content = bool(s.get("include_content", False))

		listings = search_bazos(
			keyword=keyword,
			max_price=max_price,
			site=site,
			max_pages=max(1, pages),
			include_content=include_content,
			delay_range=(0.8, 1.6),
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
		# Resolve ignore patterns: global + per-search
		ignore_patterns: List[str] = []
		if isinstance(config.get("ignore"), list):
			ignore_patterns.extend([str(x) for x in config.get("ignore", [])])
		if isinstance(s.get("ignore"), list):
			ignore_patterns.extend([str(x) for x in s.get("ignore", [])])
		if ignore_patterns:
			listings = [l for l in listings if not matches_ignore(l, ignore_patterns)]
		key = f"{site}:{keyword}:{max_price}:{pages}:{include_content}"
		new_listings = dedupe_new(listings, state, key)
		if new_listings:
			print(f"\n=== New listings for '{keyword}' ({site}, <= {max_price}) ===")
			print_listings(new_listings, as_json=False)
			# Save state after each search to avoid loss
			save_json_file(state_path, state)
		else:
			print(f"No new listings for '{keyword}' ({site}, <= {max_price}).")


def main() -> int:
	_require_deps()
	config = CONFIG
	interval = int(config.get("interval", 300))
	# Use default state file if config provides None or empty
	state_path = config.get("state_file")
	state = ensure_state(state_path)

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

