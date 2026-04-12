import json, re
from pathlib import Path

COOKIE_FILE = Path(__file__).parent.parent / "data" / "rea_cookies.json"

try:
    from curl_cffi import requests as cf
except ImportError:
    raise SystemExit("Run: pip install curl_cffi")

cookies_list = json.loads(COOKIE_FILE.read_text())
cookies = {c["name"]: c["value"] for c in cookies_list if isinstance(c, dict)}
print(f"Loaded {len(cookies)} cookies")

r = cf.get(
    "https://www.realestate.com.au/sold/in-fitzroy,+vic/list-1?sortType=soldDate-desc",
    cookies=cookies, impersonate="chrome120", timeout=20
)
print(f"Status: {r.status_code}")

m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
if m:
    data = json.loads(m.group(1))
    pp = data.get("props",{}).get("pageProps",{})
    print(f"NEXT_DATA keys: {list(pp.keys())[:6]}")
    print("✓ Cookies working! Run: python propiq/scraper.py Fitzroy")
else:
    print("✗ No NEXT_DATA — saving page dump...")
    Path("data/rea_test.html").write_text(r.text[:15000])
    print("  Check: data/rea_test.html")
