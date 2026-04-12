import json, re, time, random, logging
from pathlib import Path

log = logging.getLogger("propiq.scraper")
logging.basicConfig(level=logging.INFO, format="[scraper] %(message)s")

try:
    from curl_cffi import requests as cf
    CURL_OK = True
except ImportError:
    import requests as cf
    CURL_OK = False

HEADERS = {
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer":         "https://www.realestate.com.au/",
    "Cache-Control":   "no-cache",
}

MAX_429_WAITS = 3   # max times to wait on rate-limit per page


def _load_cookies():
    f = Path(__file__).parent.parent / "data" / "rea_cookies.json"
    if not f.exists():
        log.warning("No rea_cookies.json found — requests may be blocked")
        return {}
    c = json.loads(f.read_text())
    cookies = {x["name"]: x["value"] for x in c if isinstance(x, dict)}
    log.info(f"Loaded {len(cookies)} cookies")
    return cookies


def _price(raw):
    if not raw: return None
    s = str(raw).replace(",", "").upper()
    m = re.search(r"[0-9]+\.?[0-9]*", s.replace("$", ""))
    if not m: return None
    v = float(m.group())
    if "M" in s and v < 200:    v *= 1_000_000
    elif "K" in s and v < 5000: v *= 1_000
    return v if v > 50_000 else None


def _land(raw):
    if not raw: return None
    s = str(raw).lower().replace(",", "")
    if "ha" in s:
        m = re.search(r"[0-9.]+", s)
        return float(m.group()) * 10_000 if m else None
    m = re.search(r"[0-9.]+", s)
    v = float(m.group()) if m else None
    return v if v and 20 < v < 500_000 else None


def _extract_listings(pp):
    """Try every known NEXT_DATA path REA has used and return raw listing list."""
    raw_list = []
    paths = [
        ["componentProps", "listingsResult", "data", "tieredResults"],
        ["componentProps", "listingsResult", "data", "exactResults"],
        ["searchResults", "results"],
        ["initialProps",  "results"],
        ["componentProps", "results"],
    ]
    for path in paths:
        node = pp
        for k in path:
            node = node.get(k, {}) if isinstance(node, dict) else {}
        if isinstance(node, list) and node:
            for item in node:
                if isinstance(item, dict) and "results" in item:
                    raw_list.extend(item["results"])
                elif isinstance(item, dict) and "id" in item:
                    raw_list.append(item)
            if raw_list:
                log.info(f"  Found listings at path: {' > '.join(path)}")
                break
    return raw_list


def _parse_record(raw, suburb):
    addr   = raw.get("address", {})
    street = addr.get("streetAddress", "") if isinstance(addr, dict) else ""
    sub    = addr.get("suburb", suburb)    if isinstance(addr, dict) else suburb
    pc     = str(addr.get("postcode", "")) if isinstance(addr, dict) else ""

    pnode  = raw.get("price", {})
    praw   = pnode.get("display", "") if isinstance(pnode, dict) else str(pnode or "")
    # Also check soldDetails
    if not praw:
        sd = raw.get("soldDetails", {})
        praw = sd.get("soldPrice", "") or sd.get("display", "") if isinstance(sd, dict) else ""
    price = _price(praw)
    if not street or not price:
        return None

    feats = raw.get("generalFeatures", {}) or {}
    beds  = feats.get("bedrooms",  {}).get("value") if isinstance(feats, dict) else None
    baths = feats.get("bathrooms", {}).get("value") if isinstance(feats, dict) else None

    ptype = (raw.get("propertyType", "") or "house").lower()
    if   "townhouse" in ptype:               ptype = "townhouse"
    elif "unit" in ptype or "apart" in ptype: ptype = "unit"
    else:                                     ptype = "house"

    ags   = raw.get("agents", raw.get("listers", [])) or []
    ag    = ags[0] if isinstance(ags, list) and ags else {}
    aname = ag.get("name", "")       if isinstance(ag, dict) else ""
    agenc = ag.get("agencyName", "") if isinstance(ag, dict) else ""

    lraw = ""
    for key in ["landSize", "land"]:
        nd = raw.get(key)
        if isinstance(nd, dict):
            lraw = nd.get("displayValue", "") or nd.get("value", "")
        elif nd:
            lraw = str(nd)
        if lraw: break

    imgs = []
    for img in (raw.get("images") or [])[:4]:
        u = img.get("url", "") if isinstance(img, dict) else ""
        if u.startswith("http"): imgs.append(u)

    lurl = raw.get("canonicalUrl", "")
    if lurl and not lurl.startswith("http"):
        lurl = "https://www.realestate.com.au" + lurl

    return {
        "address":       str(street),
        "suburb":        str(sub),
        "state":         "VIC",
        "postcode":      pc,
        "sale_price":    price,
        "land_size_sqm": _land(lraw),
        "house_type":    ptype,
        "year_built":    None,
        "bedrooms":      int(beds)  if beds  else None,
        "bathrooms":     int(baths) if baths else None,
        "agent_name":    aname,
        "agent_phone":   "",
        "agency":        agenc,
        "image_urls":    json.dumps(imgs),
        "listing_url":   lurl,
        "source":        "rea",
    }


def _scrape_suburb(session, cookies, suburb, max_pages):
    records = []
    slug    = suburb.lower().replace(" ", "-")
    pg      = 1

    while pg <= max_pages:
        url = (f"https://www.realestate.com.au/sold/in-{slug},+vic/list-{pg}"
               f"?sortType=soldDate-desc")
        log.info(f"  {suburb} page {pg}")

        waits = 0
        while True:   # retry loop for 429
            try:
                if CURL_OK:
                    r = session.get(url, headers=HEADERS, cookies=cookies,
                                    impersonate="chrome120", timeout=25)
                else:
                    r = session.get(url, headers=HEADERS, cookies=cookies, timeout=25)
            except Exception as e:
                log.warning(f"  Request error: {e}")
                break

            log.info(f"  HTTP {r.status_code}")

            # ── Rate limited: wait and retry SAME page ──────────────
            if r.status_code == 429:
                waits += 1
                if waits > MAX_429_WAITS:
                    log.warning(f"  429 repeated {waits}x — giving up on {suburb}")
                    return records
                wait = 60 * waits          # 60s, 120s, 180s
                log.warning(f"  429 — waiting {wait}s (attempt {waits}/{MAX_429_WAITS})")
                time.sleep(wait)
                continue                   # retry same page

            # ── Non-200 other than 429: skip suburb ──────────────────
            if r.status_code != 200:
                log.warning(f"  HTTP {r.status_code} — stopping {suburb}")
                return records

            break   # got a 200 — exit retry loop

        # ── Parse NEXT_DATA ──────────────────────────────────────────
        nd_match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            r.text, re.DOTALL
        )
        if not nd_match:
            log.warning("  No NEXT_DATA in response")
            Path("data").mkdir(exist_ok=True)
            Path("data/debug_page.html").write_text(r.text[:20000])
            log.info("  Saved dump → data/debug_page.html")
            break

        try:
            data     = json.loads(nd_match.group(1))
            pp       = data.get("props", {}).get("pageProps", {})
            raw_list = _extract_listings(pp)
        except (json.JSONDecodeError, Exception) as e:
            log.warning(f"  JSON parse error: {e}")
            break

        log.info(f"  {len(raw_list)} raw listings on page {pg}")
        if not raw_list:
            break   # no more pages

        for raw in raw_list:
            try:
                rec = _parse_record(raw, suburb)
                if rec:
                    records.append(rec)
            except Exception as e:
                log.debug(f"  row err: {e}")

        pg += 1
        time.sleep(random.uniform(3.0, 6.0))

    log.info(f"[{suburb}] {len(records)} valid records")
    return records


def run_scraper(suburbs, max_pages=3, headless=True):
    """Public entry point called from agent.py."""
    cookies     = _load_cookies()
    session     = cf.Session()
    all_records = []

    for suburb in suburbs:
        recs = _scrape_suburb(session, cookies, suburb, max_pages)
        all_records.extend(recs)
        time.sleep(random.uniform(4.0, 8.0))

    log.info(f"Scrape complete — {len(all_records)} total records")
    return all_records


if __name__ == "__main__":
    import sys
    subs    = sys.argv[1:] or ["Fitzroy"]
    results = run_scraper(subs, max_pages=2)

    print(f"\nGot {len(results)} records")
    for r in results[:5]:
        print(f"  {r['suburb']} | {r['address']} | ${r['sale_price']:,.0f}")

    if results:
        Path("data").mkdir(exist_ok=True)
        Path("data/scrape_test.json").write_text(json.dumps(results, indent=2))
        print("Saved → data/scrape_test.json")
    else:
        print("0 records — check data/debug_page.html for what REA returned")