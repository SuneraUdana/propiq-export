import time
import json
import random
import hashlib
import re
import logging
from typing import Optional
from datetime import datetime

import requests
import cloudscraper as _cs
_session = _cs.create_scraper()
import cloudscraper as _cs
_session = _cs.create_scraper()
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.domain.com.au/",
}

SUBURB_SLUGS = {
    "Fitzroy":     "fitzroy-vic-3065",
    "Richmond":    "richmond-vic-3121",
    "Hawthorn":    "hawthorn-vic-3122",
    "Brunswick":   "brunswick-vic-3056",
    "South Yarra": "south-yarra-vic-3141",
    "Collingwood": "collingwood-vic-3066",
    "St Kilda":    "st-kilda-vic-3182",
    "Prahran":     "prahran-vic-3181",
    "Northcote":   "northcote-vic-3070",
    "Footscray":   "footscray-vic-3011",
}

PROPERTY_TYPE_MAP = {
    "ApartmentUnitFlat": "unit",
    "House":             "house",
    "Townhouse":         "townhouse",
    "Terrace":           "house",
    "Villa":             "unit",
    "Studio":            "unit",
    "DuplexSemiDetached":"house",
    "NewApartments":     "unit",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get(url: str, retries: int = 3) -> Optional[requests.Response]:
    """Polite GET with retries and random delay."""
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(1.8, 3.2))
            resp = _session.get(url, headers=BASE_HEADERS, timeout=20)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                wait = 30 * (attempt + 1)
                logger.warning(f"Rate limited — waiting {wait}s")
                time.sleep(wait)
            else:
                logger.warning(f"HTTP {resp.status_code} for {url}")
        except requests.RequestException as e:
            logger.warning(f"Request error ({attempt+1}/{retries}): {e}")
            time.sleep(5)
    return None


def _extract_next_data(html: str) -> Optional[dict]:
    """Extract __NEXT_DATA__ JSON blob from Domain page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    tag  = soup.find("script", {"id": "__NEXT_DATA__"})
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        return None


def _parse_price(price_str: str) -> float:
    """Parse price strings like '$1,250,000' or 'Contact agent' → float."""
    if not price_str:
        return 0.0
    nums = re.findall(r"[\d]+", price_str.replace(",", ""))
    if not nums:
        return 0.0
    values = [int(n) for n in nums if len(n) >= 5]
    if not values:
        return 0.0
    return float(sum(values) / len(values))  # avg if range given


def _make_listing_id(address: str, suburb: str) -> str:
    raw = f"{address}_{suburb}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ── Parsers ──────────────────────────────────────────────────────────────────

def _parse_listing_node(node: dict, suburb: str) -> Optional[dict]:
    """Map a Domain listing JSON node → PropIQ record schema."""
    try:
        listing = node.get("listingModel") or node.get("listing") or node
        details  = listing.get("address", {})
        features = listing.get("features", {}) or listing.get("landDetails", {})
        price_d  = listing.get("price", {}) or {}
        advert   = listing.get("advertiser", {}) or {}
        media    = listing.get("media", []) or []

        address_str = (
            listing.get("address", {}).get("street", "")
            or listing.get("displayableAddress", "")
            or listing.get("address", "") or ""
        )
        if isinstance(address_str, dict):
            address_str = address_str.get("street","") or ""

        prop_types = listing.get("propertyTypes", []) or [listing.get("propertyType","house")]
        raw_type   = prop_types[0] if prop_types else "house"
        house_type = PROPERTY_TYPE_MAP.get(raw_type, "house")

        price_raw  = (price_d.get("display") or price_d.get("from") or
                      listing.get("priceLabel","") or "")
        sale_price = _parse_price(str(price_raw))

        bedrooms   = int(listing.get("bedrooms")   or features.get("bedrooms",   2) or 2)
        bathrooms  = int(listing.get("bathrooms")  or features.get("bathrooms",  1) or 1)
        land_sqm   = float(listing.get("landAreaSqm") or features.get("landArea", 0) or 0)

        agent_name  = advert.get("name") or advert.get("agentName") or ""
        agency_name = advert.get("agency") or advert.get("agencyName") or ""

        listing_id = (str(listing.get("id") or listing.get("listingId") or
                      _make_listing_id(address_str, suburb)))

        # Skip if no useful price or address
        if not address_str:
            return None

        return {
            "listing_id":    listing_id,
            "suburb":        suburb,
            "address":       address_str.strip(),
            "sale_price":    sale_price,
            "land_size_sqm": land_sqm,
            "house_type":    house_type,
            "year_built":    None,
            "bedrooms":      bedrooms,
            "bathrooms":     bathrooms,
            "agent_name":    agent_name,
            "agency":        agency_name,
            "agent_phone":   "",
            "source":        "domain",
            "scraped_at":    datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.debug(f"Parse error on node: {e}")
        return None


def _walk_next_data(data: dict, suburb: str) -> list[dict]:
    """Walk __NEXT_DATA__ tree to find listing nodes."""
    records = []

    def _recurse(obj):
        if isinstance(obj, list):
            for item in obj:
                _recurse(item)
        elif isinstance(obj, dict):
            # Domain wraps listings in various keys
            if any(k in obj for k in ("listingModel","listing","propertyTypes","bedrooms")):
                r = _parse_listing_node(obj, suburb)
                if r:
                    records.append(r)
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    _recurse(v)

    _recurse(data)

    # Deduplicate by listing_id
    seen = set()
    unique = []
    for r in records:
        if r["listing_id"] not in seen:
            seen.add(r["listing_id"])
            unique.append(r)
    return unique


# ── Main scrape functions ────────────────────────────────────────────────────

def scrape_for_sale(suburb: str, pages: int = 3) -> list[dict]:
    """Scrape active for-sale listings for a suburb."""
    slug     = SUBURB_SLUGS.get(suburb, suburb.lower().replace(" ","-") + "-vic")
    results  = []

    for page in range(1, pages + 1):
        url = f"https://www.domain.com.au/sale/{slug}/?page={page}"
        logger.info(f"[scraper] FOR SALE {suburb} page {page} → {url}")
        resp = _get(url)
        if not resp:
            break

        data = _extract_next_data(resp.text)
        if not data:
            logger.warning(f"No __NEXT_DATA__ found for {url}")
            break

        batch = _walk_next_data(data, suburb)
        if not batch:
            break

        results.extend(batch)
        logger.info(f"[scraper]   ↳ {len(batch)} listings found (total {len(results)})")

    return results


def scrape_sold(suburb: str, pages: int = 3) -> list[dict]:
    """Scrape recently sold listings for a suburb."""
    slug     = SUBURB_SLUGS.get(suburb, suburb.lower().replace(" ","-") + "-vic")
    results  = []

    for page in range(1, pages + 1):
        url = f"https://www.domain.com.au/sold-listings/{slug}/?page={page}"
        logger.info(f"[scraper] SOLD {suburb} page {page} → {url}")
        resp = _get(url)
        if not resp:
            break

        data = _extract_next_data(resp.text)
        if not data:
            logger.warning(f"No __NEXT_DATA__ found for {url}")
            break

        batch = _walk_next_data(data, suburb)
        if not batch:
            break

        # Tag sold listings
        for r in batch:
            r["source"] = "domain_sold"

        results.extend(batch)
        logger.info(f"[scraper]   ↳ {len(batch)} sold listings (total {len(results)})")

    return results


def run_scraper(suburbs: list[str], sold_pages: int = 2, sale_pages: int = 2) -> list[dict]:
    """
    Main entry point — scrapes both for-sale and sold listings
    for all target suburbs. Returns cleaned, deduplicated records.
    """
    from propiq.simulator import clean_records

    all_records = []
    logging.basicConfig(level=logging.INFO)

    for suburb in suburbs:
        print(f"  [scraper] Scraping {suburb}...")

        # For-sale listings
        sale = scrape_for_sale(suburb, pages=sale_pages)
        print(f"  [scraper]   For sale : {len(sale)}")
        all_records.extend(sale)

        # Sold listings (confirmed prices — better for scoring)
        sold = scrape_sold(suburb, pages=sold_pages)
        print(f"  [scraper]   Sold     : {len(sold)}")
        all_records.extend(sold)

    # Deduplicate across suburbs
    seen = set()
    unique = []
    for r in all_records:
        if r["listing_id"] not in seen:
            seen.add(r["listing_id"])
            unique.append(r)

    print(f"  [scraper] Total unique records: {len(unique)}")

    # Fall back to simulator if scraper got nothing (e.g. blocked)
    if len(unique) < 10:
        print("  [scraper] ⚠️  Too few results — falling back to simulator")
        from propiq.simulator import simulate_listings
        unique = simulate_listings()

    return clean_records(unique)


# ── CLI test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_suburbs = ["Fitzroy", "Richmond", "Hawthorn"]
    records = run_scraper(test_suburbs, sold_pages=1, sale_pages=1)
    print(f"Scraped {len(records)} records:")
    for r in records[:5]:
        print(f" - {r['address']}, {r['suburb']} : ${r['sale_price']}")