"""Beisen iTalent (北森) SPA 门户适配器。

支持所有使用 *.zhiye.com 域名的北森 2022 版门户。
已知租户: vivo, iFlytek, Transsion, CXMT, Sany, BYD, 喜茶... (93+ 已验证)

核心 API: POST /api/Jobad/GetJobAdPageList (无需登录)

Category 映射:
    "3" = 实习生
    "4" = 员工社招
    "5" = 员工校招
    "2" = 校园招聘
    "1" = 全部
"""

from typing import Optional
import requests
from intern_scout.models import Position, SearchResult
from intern_scout.platforms.base import BaseAdapter
from intern_scout.utils import random_user_agent, rate_limit, clean_html


class BeisenAdapter(BaseAdapter):
    def __init__(
        self,
        company: str,
        display_name: str,
        api_root: str,
        site_root: str,
        category: Optional[list[str]] = None,
        page_size: int = 20,
        max_pages: int = 10,
    ):
        self.company = company
        self.display_name = display_name
        self.api_root = api_root
        self.site_root = site_root
        self.default_category = category or ["3"]
        self._page_size = page_size
        self._max_pages = max_pages
        self._session = requests.Session()

    @property
    def source(self) -> str:
        host = self.api_root.replace("https://", "").replace("http://", "")
        return f"{host}"

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.api_root}{path}"
        rate_limit(self.source)
        headers = {
            "User-Agent": random_user_agent(),
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Referer": self.site_root,
            "Origin": self.api_root,
            "x-requested-with": "xmlhttprequest",
            "langtype": "zh_CN",
        }
        try:
            resp = self._session.post(url, json=body, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"Code": -1, "Message": str(e), "error": True}

    def search(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> SearchResult:
        ps = page_size or self._page_size
        ps = max(1, min(50, ps))
        body = {
            "PageIndex": page - 1,
            "PageSize": ps,
            "KeyWords": (keyword or "").strip()[:60],
            "SpecialType": 0,
            "PortalId": "",
            "Category": self.default_category,
            "DisplayFields": ["Category", "Kind", "LocId", "Org", "HeadCount", "PostDate", "Salary"],
        }

        payload = self._post("/api/Jobad/GetJobAdPageList", body)
        if payload.get("error") or payload.get("Code") != 200:
            return SearchResult(
                ok=False,
                source=self.source,
                total=0,
                fetched=0,
                positions=[],
                message=payload.get("Message", "upstream error"),
                query=body,
            )

        rows = payload.get("Data") or []
        positions = [self._parse_row(r) for r in rows]
        return SearchResult(
            ok=True,
            source=self.source,
            total=payload.get("Count", len(positions)),
            fetched=len(positions),
            positions=positions,
            query=body,
        )

    def fetch_all(
        self,
        keyword: str = "",
        max_pages: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> SearchResult:
        return self.paginate_all(
            self.search,
            keyword=keyword,
            max_pages=max_pages or self._max_pages,
            page_size=page_size or self._page_size,
        )

    def fetch_detail(self, post_id: str) -> Optional[Position]:
        body = {
            "PageIndex": 0,
            "PageSize": 1,
            "KeyWords": "",
            "SpecialType": 0,
            "PortalId": "",
            "JobAdIds": [int(post_id) if post_id.isdigit() else post_id],
            "DisplayFields": [
                "Category", "Kind", "LocId", "Org", "HeadCount",
                "PostDate", "Salary", "DetailAddress", "Duty", "Require",
            ],
        }
        payload = self._post("/api/Jobad/GetJobAdPageList", body)
        if payload.get("error") or payload.get("Code") != 200:
            return None
        rows = payload.get("Data") or []
        if not rows:
            return None
        return self._parse_row(rows[0])

    def _parse_row(self, row: dict) -> Position:
        pid = str(row.get("JobAdId") or row.get("Id") or "")
        cities = row.get("LocNames") or []
        location = ", ".join(cities) if isinstance(cities, list) else str(cities)
        category = (row.get("Category") or "").strip()
        detail_path = ("intern" if "实习" in category else
                       "campus" if ("校园" in category or "校招" in category) else
                       "social")
        apply_url = f"{self.site_root}/{detail_path}/detail?jobAdId={pid}" if pid else self.site_root

        return Position(
            post_id=pid,
            title=(row.get("JobAdName") or "").strip(),
            company=self.display_name,
            source_platform=self.source,
            source_url=apply_url,
            location=location,
            salary_range=row.get("Salary") or "",
            department=(row.get("Org") or "").strip(),
            job_category=category,
            recruit_type=category,
            description=clean_html(row.get("Duty") or ""),
            requirements=clean_html(row.get("Require") or ""),
            head_count=row.get("HeadCount"),
            posted_date=row.get("PostDate") or "",
        )

    def __repr__(self) -> str:
        return f"BeisenAdapter({self.display_name}, {self.source})"


VIVO_CONFIG = {
    "company": "vivo",
    "display_name": "vivo",
    "api_root": "https://hr-campus.vivo.com",
    "site_root": "https://hr-campus.vivo.com",
    "category": ["3"],
}


def create_vivo() -> BeisenAdapter:
    return BeisenAdapter(**VIVO_CONFIG)
