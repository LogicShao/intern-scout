"""华为招聘适配器 — 通过 Playwright 浏览器自动化实现。

华为招聘系统 (career.huawei.com) 为自研 SPA，API 端点已部分逆向：
  - 详情: GET /reccampportal/services/portal/portalpub/getJobDetail/newHr?jobId=
  - 列表: 需通过浏览器拦截 XHR 发现

华为校招页使用 portal5/reccampportal 架构，岗位列表 API 通过 AJAX 动态加载。
由于 API 需要 session cookie 或 CSRF token，直接 HTTP 调用返回空数据。
本适配器使用 Playwright 在浏览器中加载页面并拦截 API 响应。
"""

from intern_scout.models import Position, SearchResult
from intern_scout.platforms.base import BaseAdapter
from typing import Optional


class HuaweiAdapter(BaseAdapter):
    def __init__(self):
        self.company = "huawei"
        self.display_name = "华为"
        self.api_root = "https://career.huawei.com"
        self.site_root = "https://career.huawei.com/reccampportal/portal5/campus-recruitment.html"

    @property
    def source(self) -> str:
        return "career.huawei.com"

    def _check_browser(self) -> Optional[str]:
        try:
            from playwright.sync_api import sync_playwright
            try:
                with sync_playwright() as p:
                    p.chromium.launch(headless=True).close()
                return None
            except Exception as e:
                msg = str(e)
                if "libnspr4" in msg or "shared libraries" in msg:
                    return "Chrome system dependencies missing. Install: apt-get install libnspr4 libnss3 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2"
                return f"playwright launch failed: {msg}"
        except ImportError:
            return "playwright not installed. Run: pip install playwright && playwright install chromium"

    def search(self, keyword: str = "", page: int = 1, page_size: int = 20) -> SearchResult:
        err = self._check_browser()
        if err:
            return SearchResult(ok=False, source=self.source, total=0, fetched=0, positions=[], message=err)

        try:
            from playwright.sync_api import sync_playwright
            positions: list[Position] = []

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page_obj = context.new_page()

                intercepted: list[dict] = []

                def on_response(response):
                    if "/services/" in response.url and response.headers.get("content-type", "").startswith("application/json"):
                        try:
                            body = response.json()
                            if isinstance(body, dict) and any(k in str(body).lower() for k in ["job", "recruit", "position"]):
                                intercepted.append({"url": response.url, "body": body})
                        except Exception:
                            pass

                page_obj.on("response", on_response)

                url = f"{self.site_root}?keywords={keyword}" if keyword else self.site_root
                page_obj.goto(url, wait_until="networkidle", timeout=30000)
                page_obj.wait_for_timeout(3000)

                browser.close()

                for item in intercepted:
                    body = item["body"]
                    rows = self._extract_job_list(body)
                    for r in rows:
                        try:
                            positions.append(self._parse_huawei_row(r))
                        except Exception:
                            continue

            total = len(positions)
            start = (page - 1) * page_size
            positions = positions[start:start + page_size]

            return SearchResult(ok=True, source=self.source, total=total,
                                fetched=len(positions), positions=positions)
        except Exception as e:
            return SearchResult(ok=False, source=self.source, total=0, fetched=0,
                                positions=[], message=str(e))

    def fetch_all(self, keyword: str = "", max_pages: int = 5, page_size: int = 30) -> SearchResult:
        return self.search(keyword=keyword, page=1, page_size=max_pages * page_size)

    def fetch_detail(self, post_id: str) -> Optional[Position]:
        import requests
        try:
            r = requests.get(
                f"{self.api_root}/reccampportal/services/portal/portalpub/getJobDetail/newHr?jobId={post_id}",
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                         "Referer": self.site_root},
                timeout=10,
            )
            d = r.json()
            if d.get("jobId") or d.get("jobName"):
                return self._parse_huawei_row(d)
        except Exception:
            pass
        return None

    def _extract_job_list(self, body: dict) -> list:
        for key in ["jobList", "data", "result", "list", "rows", "jobData", "records"]:
            if key in body and isinstance(body[key], list):
                return body[key]
        for key, val in body.items():
            if isinstance(val, dict):
                inner = self._extract_job_list(val)
                if inner:
                    return inner
        return []

    def _parse_huawei_row(self, row: dict) -> Position:
        pid = str(row.get("jobId") or row.get("id") or row.get("postId", ""))
        return Position(
            post_id=pid,
            title=(row.get("jobName") or row.get("jobTitle") or row.get("title", "")).strip(),
            company=self.display_name,
            source_platform=self.source,
            source_url=f"{self.api_root}/reccampportal/portal5/campus-recruitment-detail.html?jobId={pid}",
            location=row.get("workLocName") or row.get("cityName") or row.get("location", ""),
            salary_range="",
            department=(row.get("deptName") or row.get("orgName") or row.get("department", "")).strip(),
            job_category=(row.get("jobFamily") or row.get("jobCategory", "")).strip(),
            recruit_type=(row.get("recruitType") or row.get("recruitClassName", "")).strip(),
            description=row.get("jobDesc") or row.get("description", ""),
            requirements=row.get("jobReq") or row.get("requirement", ""),
        )


def create_huawei() -> HuaweiAdapter:
    return HuaweiAdapter()
