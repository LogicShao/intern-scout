"""ATS API 自动发现模块 — 可被 Agent 编程调用或通过 CLI 使用。

对任意公司招聘站 URL，用 Playwright 拦截 XHR 请求，
匹配已知 ATS 签名，输出适配器配置。

用法:
    from intern_scout.discover import discover
    result = discover("https://careers.oppo.com/campus")
    if result.matched:
        print(f"Matched: {result.ats_family}")
        print(result.suggested_config)

CLI:
    python -m intern_scout.discover https://careers.oppo.com/campus
    python -m intern_scout.discover --company vivo
"""

from dataclasses import dataclass, field
import asyncio
import json
import sys
from playwright.async_api import async_playwright


@dataclass
class DiscoverResult:
    url: str
    matched: bool
    ats_family: str = ""
    confidence: str = ""
    captured_endpoints: list[dict] = field(default_factory=list)
    suggested_config: dict = field(default_factory=dict)
    note: str = ""


# ============================================================
# ATS 签名库 — 每个 ATS 家族的 API 特征
# ============================================================
# Entry format:
#   family_name: {
#       "domain_pattern": regex for matching URL domain,
#       "api_pattern":   regex for matching API endpoint path,
#       "body_keys":     set of JSON keys that must appear in request body,
#       "resp_keys":     set of JSON keys that must appear in response body,
#       "config_template": lambda name, domain → suggested adapter config
#   }

ATS_SIGNATURES: dict[str, dict] = {
    "beisen": {
        "domain_pattern": r"\.zhiye\.com",
        "api_pattern": r"/api/Jobad/GetJobAdPageList",
        "body_keys": {"SpecialType", "PortalId"},
        "resp_keys": {"Code", "Data", "Count"},
        "config_template": lambda name, domain: {
            "company": name,
            "display_name": name,
            "api_root": f"https://{domain}",
            "site_root": f"https://{domain}",
            "category": ["3"],
            "ats_family": "beisen",
            "note": "Beisen iTalent tenant. Category: 3=intern, 4=social, 5=campus",
        },
    },
    "feishu_atsx": {
        "domain_pattern": r"(?:\.feishu\.cn|\.f\.mioffice\.cn)",
        "api_pattern": r"/api/v1/search/job/posts",
        "body_keys": {"portal_type", "portal_entrance"},
        "resp_keys": {"code", "data", "message"},
        "config_template": lambda name, domain: {
            "company": name,
            "display_name": name,
            "api_root": f"https://{domain}/api/v1",
            "site_root": f"https://{domain}",
            "default_channel": "saas-career",
            "website_path": "campus",
            "portal_type": 6,
            "requires_csrf": True,
            "ats_family": "feishu_atsx",
            "note": "Feishu ATSX tenant. CSRF required: POST /api/v1/csrf/token",
        },
    },
    "openapi": {
        "domain_pattern": r"",
        "api_pattern": r"/openapi/position/",
        "body_keys": set(),
        "resp_keys": {"code", "data"},
        "config_template": lambda name, domain: {
            "company": name,
            "display_name": name,
            "api_root": f"https://{domain}",
            "ats_family": "bespoke",
            "endpoint": f"https://{domain}/openapi/position/pageNew",
            "note": "Self-hosted openapi. List endpoint: POST /openapi/position/pageNew",
        },
    },
    "reccampportal": {
        "domain_pattern": r"career\.huawei\.com",
        "api_pattern": r"/reccampportal/services/.*getJob",
        "body_keys": set(),
        "resp_keys": {"pageVO", "result"},
        "config_template": lambda name, domain: {
            "company": name,
            "display_name": name,
            "api_root": f"https://{domain}",
            "ats_family": "bespoke",
            "endpoint": f"https://{domain}/reccampportal/services/portal/portalpub/getJob/newHr/page/10/1",
            "note": "Huawei reccampportal. Requires session cookie from campus page.",
        },
    },
}


def match_ats(domain: str, endpoints: list[dict]) -> list[dict]:
    import re
    matches = []
    for family, sig in ATS_SIGNATURES.items():
        if sig["domain_pattern"]:
            if not re.search(sig["domain_pattern"], domain):
                continue
        for ep in endpoints:
            url = ep.get("url", "")
            if not re.search(sig["api_pattern"], url):
                continue
            body = {}
            if ep.get("post_data"):
                try:
                    body = json.loads(ep["post_data"])
                except json.JSONDecodeError:
                    pass
            resp = ep.get("_response", {})
            resp_body = {}
            if resp.get("body"):
                try:
                    resp_body = json.loads(resp["body"])
                except json.JSONDecodeError:
                    pass

            body_hit = sig["body_keys"].issubset(set(body.keys())) if sig["body_keys"] else True
            resp_hit = sig["resp_keys"].issubset(
                set(resp_body.keys())
            ) if sig["resp_keys"] else True

            if body_hit and resp_hit:
                matches.append({
                    "family": family,
                    "domain": domain,
                    "confidence": "high" if ep.get("_response", {}).get("status") == 200 else "medium",
                    "endpoint": url,
                    "method": ep.get("method", "GET"),
                    "body": body,
                    "resp_sample": resp_body,
                    "config": sig["config_template"](_extract_name(domain), domain),
                })
    return matches


def _extract_name(domain: str) -> str:
    return domain.replace("https://", "").replace("http://", "").split(".")[0]


async def _intercept(url: str, timeout_ms: int = 30000) -> list[dict]:
    captured = []

    async def on_request(request):
        if request.resource_type in ("xhr", "fetch"):
            captured.append({
                "url": request.url,
                "method": request.method,
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
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass
        await page.wait_for_timeout(5000)
        await browser.close()

    return captured


def discover(url: str, timeout_ms: int = 30000) -> DiscoverResult:
    if not url.startswith("http"):
        return DiscoverResult(
            url=url,
            matched=False,
            note=f"Not a valid URL: {url}. Must start with http:// or https://",
        )

    try:
        endpoints = asyncio.run(_intercept(url, timeout_ms))
    except Exception as e:
        return DiscoverResult(
            url=url,
            matched=False,
            note=f"Playwright error: {e}. Ensure playwright and system deps are installed.",
        )

    from urllib.parse import urlparse
    domain = urlparse(url).netloc

    matches = match_ats(domain, endpoints)
    if matches:
        best = matches[0]
        return DiscoverResult(
            url=url,
            matched=True,
            ats_family=best["family"],
            confidence=best["confidence"],
            captured_endpoints=[{"url": best["endpoint"], "method": best["method"]}],
            suggested_config=best["config"],
        )

    return DiscoverResult(
        url=url,
        matched=False,
        captured_endpoints=[{"url": e["url"], "method": e["method"]} for e in endpoints],
        note=f"No known ATS signature matched. Found {len(endpoints)} XHR endpoints. Check captured_endpoints for manual analysis.",
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m intern_scout.discover <url>")
        print("       python -m intern_scout.discover --company <name>")
        sys.exit(1)

    arg = sys.argv[1]
    if arg == "--company" and len(sys.argv) > 2:
        name = sys.argv[2]
        known = {
            "vivo": "https://hr-campus.vivo.com",
            "xiaomi": "https://xiaomi.jobs.f.mioffice.cn",
            "oppo": "https://careers.oppo.com/campus",
            "huawei": "https://career.huawei.com/reccampportal/portal5/campus-recruitment.html",
            "nio": "https://nio.jobs.feishu.cn/campus/position",
        }
        url = known.get(name.lower())
        if not url:
            print(f"Unknown company: {name}. Provide a full URL instead.")
            sys.exit(1)
    else:
        url = arg

    result = discover(url)

    if result.matched:
        print(f"✅ Matched: {result.ats_family} (confidence: {result.confidence})")
        print(f"   Captured: {json.dumps(result.captured_endpoints[0], ensure_ascii=False)}")
        print(f"\nSuggested config for beisen.py / feishu_atsx.py:")
        print(json.dumps(result.suggested_config, indent=2, ensure_ascii=False))
    else:
        print(f"❌ Not matched. {result.note}")
        if result.captured_endpoints:
            print(f"\nCaptured {len(result.captured_endpoints)} XHR endpoints:")
            for ep in result.captured_endpoints[:10]:
                print(f"  [{ep['method']}] {ep['url'][:120]}")


if __name__ == "__main__":
    main()
