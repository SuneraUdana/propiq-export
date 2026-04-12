#!/usr/bin/env python3
"""
PropIQ — Scraper Diagnostic
Run: python propiq/debug_scraper.py
Shows exactly what REA returns so we can fix the path.
"""
import asyncio, json, re
from pathlib import Path
from playwright.async_api import async_playwright

async def diagnose():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,  # VISIBLE so you can see what happens
            args=["--no-sandbox","--disable-blink-features=AutomationControlled"]
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width":1280,"height":900},
            locale="en-AU", timezone_id="Australia/Melbourne"
        )
        page = await ctx.new_page()

        print("\n[1] Trying REA services JSON API (no HTML parsing)...")
        url = "https://services.realestate.com.au/services/listings/search?query={%22channel%22:%22sold%22,%22filters%22:{%22surroundingSuburbs%22:false},%22localities%22:[{%22searchLocation%22:%22Fitzroy+VIC+3065%22}]}&pageSize=25&page=1"
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            print(f"   Status: {resp.status}")
            body = await page.content()
            # Try parse JSON from body
            m = re.search(r"<pre.*?>(.*?)</pre>", body, re.DOTALL)
            raw = m.group(1) if m else body
            data = json.loads(raw)
            results = data.get("results", data.get("data", {}).get("results", []))
            print(f"   Records from JSON API: {len(results)}")
            if results:
                print(f"   Sample keys: {list(results[0].keys())[:10]}")
                Path("data").mkdir(exist_ok=True)
                Path("data/api_sample.json").write_text(json.dumps(data, indent=2)[:5000])
                print("   Saved first 5000 chars → data/api_sample.json")
        except Exception as e:
            print(f"   API failed: {e}")

        print("\n[2] Trying REA HTML page...")
        try:
            resp2 = await page.goto(
                "https://www.realestate.com.au/sold/in-fitzroy,+vic/list-1?sortType=soldDate-desc",
                wait_until="networkidle", timeout=30000
            )
            print(f"   Status: {resp2.status}")
            await page.wait_for_timeout(3000)
            html = await page.content()

            # Check for captcha
            if "captcha" in html.lower() or "robot" in html.lower():
                print("   ⚠ CAPTCHA detected — site is blocking headless Chromium")
            elif "No results" in html or "no properties" in html.lower():
                print("   ⚠ Page loaded but no results found")
            else:
                print("   ✓ Page loaded normally")

            # Check NEXT_DATA
            m2 = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if m2:
                nd = json.loads(m2.group(1))
                pp = nd.get("props",{}).get("pageProps",{})
                print(f"   ✓ NEXT_DATA found — pageProps keys: {list(pp.keys())[:8]}")
                # Dump full structure keys 3 levels deep
                def show_keys(d, depth=0, prefix=""):
                    if depth > 3 or not isinstance(d, dict): return
                    for k, v in list(d.items())[:6]:
                        vtype = type(v).__name__
                        vlen  = len(v) if isinstance(v,(list,dict,str)) else ""
                        print(f"   {'  '*depth}{prefix}{k}: {vtype}({vlen})")
                        show_keys(v, depth+1)
                show_keys(pp)
                Path("data").mkdir(exist_ok=True)
                Path("data/next_data_keys.json").write_text(json.dumps(list(pp.keys()), indent=2))
                print("   Saved keys → data/next_data_keys.json")
            else:
                print("   ✗ No __NEXT_DATA__ found in page")
                print(f"   Page length: {len(html)} chars")
                Path("data").mkdir(exist_ok=True)
                Path("data/rea_page_dump.html").write_text(html[:20000])
                print("   Saved first 20KB → data/rea_page_dump.html")

        except Exception as e:
            print(f"   HTML page failed: {e}")

        await browser.close()
        print("\n[done] Check data/ folder for dumps")

asyncio.run(diagnose())
