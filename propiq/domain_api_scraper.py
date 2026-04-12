import json, time, re, logging
from pathlib import Path

log = logging.getLogger("propiq.domain_api")
logging.basicConfig(level=logging.INFO, format="[domain_api] %(message)s")

try:
    from curl_cffi import requests as cf
except ImportError:
    import requests as cf

KEYS_FILE  = Path(__file__).parent.parent / "data" / "domain_api_keys.json"
TOKEN_URL  = "https://auth.domain.com.au/v1/connect/token"
SEARCH_URL = "https://api.domain.com.au/v1/listings/residential/_search"

def _get_token(client_id, client_secret):
    r = cf.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "scope": "api_listings_read",
        "client_id": client_id,
        "client_secret": client_secret,
    })
    r.raise_for_status()
    token = r.json().get("access_token","")
    log.info("Token obtained ✓")
    return token

def _price(s):
    if not s: return None
    s = str(s).replace(",","").upper()
    m = re.search(r"[0-9]+\.?[0-9]*", s.replace("$",""))
    if not m: return None
    v = float(m.group())
    if "M" in s and v < 200: v *= 1_000_000
    elif "K" in s and v < 5000: v *= 1_000
    return v if v > 50_000 else None

def _search(token, suburb, page=1):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "listingType": "Sale",
        "propertyTypes": ["House","ApartmentUnitFlat","Townhouse"],
        "locations": [{"state":"VIC","suburb":suburb,"includeSurroundingSuburbs":False}],
        "listingStatus": "Sold",
        "pageSize": 200,
        "page": page,
        "sort": {"sortKey":"SoldDate","direction":"Descending"},
    }
    r = cf.post(SEARCH_URL, headers=headers, json=body, timeout=20)
    log.info(f"  HTTP {r.status_code}")
    r.raise_for_status()
    return r.json() or []

def _parse(raw, suburb):
    try:
        listing = raw.get("listing", raw)
        addr    = listing.get("propertyDetails", {})
        street  = addr.get("displayableAddress","") or f"{addr.get('streetNumber','')} {addr.get('street','')}".strip()
        sub     = addr.get("suburb", suburb)
        pc      = str(addr.get("postcode",""))
        pd      = listing.get("priceDetails",{})
        praw    = pd.get("displayPrice","") or str(pd.get("price","") or "")
        sd      = listing.get("soldDetails",{})
        if sd: praw = str(sd.get("soldPrice","") or praw)
        price   = _price(praw)
        if not street or not price: return None
        ptype   = addr.get("propertyType","house").lower()
        if "townhouse" in ptype: ptype="townhouse"
        elif "unit" in ptype or "flat" in ptype: ptype="unit"
        else: ptype="house"
        media = listing.get("media",[])
        imgs  = [m["url"] for m in media if isinstance(m,dict) and m.get("url","").startswith("http")][:4]
        ads   = listing.get("advertiserIdentifiers",{})
        return {
            "address": street, "suburb": sub, "state": "VIC", "postcode": pc,
            "sale_price": price, "land_size_sqm": addr.get("landArea"),
            "house_type": ptype, "year_built": None,
            "bedrooms": addr.get("bedrooms"), "bathrooms": addr.get("bathrooms"),
            "agent_name": ads.get("agencyName","") if isinstance(ads,dict) else "",
            "agent_phone": "", "agency": ads.get("agencyName","") if isinstance(ads,dict) else "",
            "image_urls": json.dumps(imgs),
            "listing_url": f"https://www.domain.com.au/{listing.get('id','')}",
            "source": "domain_api",
        }
    except Exception as e:
        log.debug(f"parse err: {e}")
        return None

def run_domain_api(suburbs, max_pages=3):
    if not KEYS_FILE.exists():
        print(f"No keys at {KEYS_FILE}"); return []
    keys  = json.loads(KEYS_FILE.read_text())
    token = _get_token(keys["client_id"], keys["client_secret"])
    all_records = []
    for suburb in suburbs:
        log.info(f"Fetching: {suburb}")
        for pg in range(1, max_pages+1):
            try:
                raw_list = _search(token, suburb, pg)
                recs = [r for raw in raw_list for r in [_parse(raw,suburb)] if r]
                log.info(f"  page {pg} → {len(recs)} records")
                all_records.extend(recs)
                if len(raw_list) < 200: break
            except Exception as e:
                log.warning(f"  {suburb} p{pg}: {e}"); break
            time.sleep(1.0)
    log.info(f"Done — {len(all_records)} total")
    return all_records

if __name__ == "__main__":
    import sys
    subs = sys.argv[1:] or ["Fitzroy"]
    results = run_domain_api(subs)
    print(f"\nGot {len(results)} records")
    for r in results[:5]:
        print(f"  {r['suburb']} | {r['address']} | ${r['sale_price']:,.0f}")
    if results:
        Path("data").mkdir(exist_ok=True)
        Path("data/domain_api_test.json").write_text(json.dumps(results, indent=2))
        print("Saved → data/domain_api_test.json")
