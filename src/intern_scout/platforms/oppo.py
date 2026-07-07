"""OPPO 招聘适配器 — 通过 Playwright 浏览器自动化实现。

OPPO 招聘系统 (careers.oppo.com) 为自研 React SPA。
校招岗位页: https://careers.oppo.com/university/oppo/campus/

OPPO 不使用标准 ATS 平台（非北森、非 Moka、非飞书 ATSX），
其 API 端点隐藏在 React 前端代码中，需要通过浏览器拦截 XHR 请求发现。

本适配器使用 Playwright 在浏览器中加载页面并拦截 API 响应。
"""

from intern_scout.models import Position, SearchResult
from intern_scout.platforms.base import BaseAdapter
from typing import Optional


class OppoAdapter(BaseAdapter):
    def __init__(self):
        self.company = "oppo"
        self.display_name = "OPPO"
        self.api_root = "https://careers.oppo.com"
        self.campus_url = "https://careers.oppo.com/university/oppo/campus/"

    @property
    def source(self) -> str:
        return "careers.oppo.com"

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
                    url = response.url
                    ct = response.headers.get("content-type", "")
                    if "json" in ct and any(kw in url for kw in ["api", "job", "position", "recruit", "campus", "delivery"]):
                        try:
                            body = response.json()
                            if isinstance(body, dict):
                                intercepted.append({"url": url, "body": body})
                        except Exception:
                            pass

                page_obj.on("response", on_response)
                page_obj.goto(self.campus_url, wait_until="networkidle", timeout=30000)
                page_obj.wait_for_timeout(3000)
                browser.close()

                for item in intercepted:
                    body = item["body"]
                    rows = self._extract_job_list(body)
                    for r in rows:
                        try:
                            positions.append(self._parse_oppo_row(r))
                        except Exception:
                            continue

            total = len(positions)
            start = (page - 1) * page_size
            positions = positions[start:start + page_size]

            if keyword:
                kw = keyword.lower()
                positions = [p for p in positions if kw in p.title.lower() or kw in p.department.lower()]

            return SearchResult(ok=True, source=self.source, total=total,
                                fetched=len(positions), positions=positions)
        except Exception as e:
            return SearchResult(ok=False, source=self.source, total=0, fetched=0,
                                positions=[], message=str(e))

    def fetch_all(self, keyword: str = "", max_pages: int = 5, page_size: int = 30) -> SearchResult:
        return self.search(keyword=keyword, page=1, page_size=page_size)

    def fetch_detail(self, post_id: str) -> Optional[Position]:
        return None

    def _extract_job_list(self, body: dict) -> list:
        for key in ["data", "result", "list", "rows", "records", "items", "jobList", "positionList"]:
            if key in body and isinstance(body[key], list):
                return body[key]
        for key, val in body.items():
            if isinstance(val, dict):
                inner = self._extract_job_list(val)
                if inner:
                    return inner
        return []

    def _parse_oppo_row(self, row: dict) -> Position:
        pid = str(row.get("id") or row.get("positionId") or row.get("jobId", ""))
        return Position(
            post_id=pid,
            title=(row.get("title") or row.get("name") or row.get("positionName", "")).strip(),
            company=self.display_name,
            source_platform=self.source,
            source_url=f"{self.campus_url}#/detail/{pid}" if pid else self.campus_url,
            location=(row.get("city") or row.get("location") or row.get("workCity", "")).strip(),
            salary_range=row.get("salary") or row.get("salaryRange", ""),
            department=(row.get("department") or row.get("dept") or row.get("orgName", "")).strip(),
            job_category=(row.get("category") or row.get("jobType") or row.get("type", "")).strip(),
            recruit_type=(row.get("recruitType") or row.get("employmentType", "")).strip(),
            description=row.get("description") or row.get("jobDesc", ""),
            requirements=row.get("requirements") or row.get("qualification", ""),
        )


def create_oppo() -> OppoAdapter:
    return OppoAdapter()
