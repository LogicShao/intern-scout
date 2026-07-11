"""OPPO 校招 API 自动发现 — Playwright XHR 拦截。

用法: python discover_oppo_api.py
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def intercept_oppo():
    captured = []

    async def on_request(request):
        if request.resource_type in ("xhr", "fetch"):
            captured.append({
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
                "post_data": request.post_data,
                "_response": None,
            })

    async def on_response(response):
        for c in captured:
            if c["url"] == response.url and c["_response"] is None:
                try:
                    body = await response.text()
                    c["_response"] = {"status": response.status, "headers": dict(response.headers), "body": body[:10000]}
                except Exception:
                    pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.on("request", on_request)
        page.on("response", on_response)

        print("Opening OPPO campus page...")
        await page.goto("https://careers.oppo.com/university/oppo/campus/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # Try clicking on job cards to trigger detail API
        cards = await page.query_selector_all('[class*="job"], [class*="position"], [class*="card"], [class*="item"], a[href*="detail"], a[href*="position"]')
        print(f"Found {len(cards)} potential job elements")

        # Click first card if exists
        if cards:
            try:
                await cards[0].click()
                await page.wait_for_timeout(3000)
                print("Clicked first job card")
            except Exception as e:
                print(f"Click failed: {e}")

        await browser.close()

    return captured


async def main():
    entries = await intercept_oppo()

    if not entries:
        print("No XHR requests captured")
        return

    print(f"\n{'='*60}")
    print(f"All {len(entries)} XHR/Fetch requests:")
    print(f"{'='*60}")
    for e in entries:
        resp_status = e["_response"]["status"] if e["_response"] else "?"
        url_short = e["url"].replace("https://careers.oppo.com", "")[:100]
        print(f"  [{e['method']:4s}] {resp_status:3s} {url_short}")

    # Filter job-related APIs
    job_keywords = ["job", "position", "recruit", "campus", "career", "delivery", "api/"]
    job_apis = [e for e in entries if any(kw in e["url"].lower() for kw in job_keywords)]

    print(f"\n{'='*60}")
    print(f"Job-related APIs ({len(job_apis)}):")
    print(f"{'='*60}")

    for api in job_apis:
        print(f"\n--- [{api['method']}] {api['url'][:120]}")
        if api["post_data"]:
            try:
                print(f"Body: {json.dumps(json.loads(api['post_data']), ensure_ascii=False)[:300]}")
            except Exception:
                print(f"Raw: {api['post_data'][:200]}")

        if api["_response"]:
            resp = api["_response"]
            ct = resp.get("headers", {}).get("content-type", "")
            if "json" in ct:
                try:
                    data = json.loads(resp["body"])
                    code = data.get("code", "?")
                    total = data.get("data", {}).get("total") or data.get("total") or len(data.get("data", {}).get("list", data.get("data", [])))
                    print(f"Response: code={code}, total={total}")
                    items = data.get("data", {}).get("list") or data.get("data", {}).get("records") or data.get("data") or []
                    if isinstance(items, list) and items:
                        print(f"Fields: {list(items[0].keys())}")
                        print(json.dumps(items[0], ensure_ascii=False, indent=2)[:1000])
                except Exception:
                    print(resp["body"][:500])
            else:
                print(resp["body"][:300])


if __name__ == "__main__":
    asyncio.run(main())
