"""飞书 ATSX API 自动发现 — 用 Playwright 拦截 XHR 请求，输出 API 签名。

用法:
    python discover_feishu_api.py nio
    python discover_feishu_api.py minimax
    python discover_feishu_api.py zhipu
"""

import asyncio
import json
import sys
from playwright.async_api import async_playwright


COMPANIES: dict[str, dict] = {
    "nio": {
        "name": "蔚来",
        "url": "https://nio.jobs.feishu.cn/campus/position",
    },
    "minimax": {
        "name": "MiniMax",
        "url": "https://vrfi1sk8a0.jobs.feishu.cn/379481/position",
    },
    "zhipu": {
        "name": "智谱AI",
        "url": None,
    },
    "iqiyi": {
        "name": "爱奇艺",
        "url": None,
    },
    "baichuan": {
        "name": "百川智能",
        "url": None,
    },
}


async def intercept(slug: str) -> list[dict]:
    info = COMPANIES.get(slug)
    if not info or not info["url"]:
        print(f"❌ {slug}: no known career URL — skip")
        return []

    captured: list[dict] = []

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
                    c["_response"] = {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": body[:8000],
                    }
                except Exception:
                    pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.on("request", on_request)
        page.on("response", on_response)

        print(f"\n{'='*60}")
        print(f"🔍 {info['name']}: {info['url']}")
        print(f"{'='*60}")
        start = asyncio.get_event_loop().time()
        await page.goto(info["url"], wait_until="networkidle", timeout=30000)
        elapsed = asyncio.get_event_loop().time() - start
        print(f"Page loaded in {elapsed:.1f}s, {len(captured)} XHR requests captured")
        await page.wait_for_timeout(3000)
        await browser.close()

    return captured


def analyze(captured: list[dict]):
    if not captured:
        print("\n⚠️  No XHR/Fetch requests captured. Page may be SSR or have no API calls.")
        return

    # Filter: job-list APIs
    job_apis = [
        c for c in captured
        if any(kw in c["url"] for kw in ["search/job", "position/list", "job/list", "ats-apply", "recruit"])
    ]

    if not job_apis:
        print(f"\n📋 All {len(captured)} XHR/Fetch requests (no job API detected):")
        for c in captured:
            print(f"  [{c['method']:4s}] {c['url'][:120]}")
        print("\n⚠️  Look for position-related URLs above and manually investigate.")
        return

    for i, api in enumerate(job_apis):
        print(f"\n{'='*60}")
        print(f"🎯 Job API #{i+1}")
        print(f"{'='*60}")
        print(f"Method:  {api['method']}")
        print(f"URL:     {api['url']}")

        # Key headers (skip noisy ones)
        noisy = {"user-agent", "accept", "accept-encoding", "accept-language",
                 "connection", "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site",
                 "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
                 "upgrade-insecure-requests", "cache-control", "pragma", "priority"}
        print(f"\n--- Key Headers ---")
        for k, v in api["headers"].items():
            if k.lower() not in noisy:
                print(f"  {k}: {v}")

        if api["post_data"]:
            try:
                body = json.loads(api["post_data"])
                print(f"\n--- Request Body ---")
                print(json.dumps(body, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(f"\n--- Raw Body ---\n{api['post_data'][:300]}")

        if api["_response"]:
            resp = api["_response"]
            print(f"\n--- Response (status={resp['status']}) ---")
            ct = resp.get("headers", {}).get("content-type", "")
            if "json" in ct:
                try:
                    data = json.loads(resp["body"])
                    count = (
                        data.get("data", {}).get("count")
                        or data.get("total")
                        or len(data.get("data", {}).get("job_post_list", []))
                        or len(data.get("data", []))
                    )
                    print(f"Total jobs: {count}")
                    posts = data.get("data", {}).get("job_post_list") or data.get("data") or []
                    if posts and isinstance(posts, list):
                        print(f"Example fields: {list(posts[0].keys())}")
                        print(json.dumps(posts[0], ensure_ascii=False, indent=2)[:1000])
                    else:
                        print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
                except Exception:
                    print(resp["body"][:500])
            else:
                print(resp["body"][:300])


async def main():
    slug = sys.argv[1] if len(sys.argv) > 1 else "nio"
    captured = await intercept(slug)
    analyze(captured)


if __name__ == "__main__":
    asyncio.run(main())
