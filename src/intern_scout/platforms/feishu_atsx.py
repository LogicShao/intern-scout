"""Feishu ATSX (飞书招聘) 适配器。

支持所有使用 ByteDance ATSX 架构的飞书招聘门户。
已知租户: Xiaomi, NIO, MiniMax, 智谱AI, iQIYI, 01.AI, Baichuan, Agibot...

核心 API: POST /api/v1/search/job/posts (无需登录)

portal-channel 控制招聘池:
    "campus"     → 正式校招
    "internship" → 实习
    不设置        → 社招
"""

from typing import Optional
import requests
import random
from intern_scout.models import Position, SearchResult
from intern_scout.platforms.base import BaseAdapter
from intern_scout.utils import random_user_agent, rate_limit


class FeishuATSXAdapter(BaseAdapter):
    def __init__(
        self,
        company: str,
        display_name: str,
        api_root: str,
        site_root: str,
        default_channel: str = "internship",
        page_size: int = 20,
        max_pages: int = 15,
    ):
        self.company = company
        self.display_name = display_name
        self.api_root = api_root
        self.site_root = site_root
        self.channel = default_channel
        self._page_size = page_size
        self._max_pages = max_pages
        self._session = requests.Session()

    @property
    def source(self) -> str:
        host = self.api_root.replace("https://", "").replace("http://", "").replace("/api/v1", "")
        return f"{host}"

    def _headers(self) -> dict:
        h = {
            "User-Agent": random_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "portal-platform": "pc",
        }
        if self.channel != "social":
            h["portal-channel"] = self.channel
            h["website-path"] = self.channel
            h["Referer"] = f"{self.api_root.rsplit('/api/v1', 1)[0]}/{self.channel}/"
        return h

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.api_root}{path}"
        rate_limit(self.source)
        try:
            resp = self._session.post(url, json=body, headers=self._headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"code": -1, "message": str(e), "error": True}

    def search(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> SearchResult:
        ps = page_size or self._page_size
        ps = max(1, min(100, ps))
        offset = (page - 1) * ps

        body = {
            "keyword": (keyword or "").strip()[:60],
            "limit": ps,
            "offset": offset,
            "portal_type": 3,
            "portal_entrance": 1,
            "language": "zh",
        }

        if self.channel == "internship":
            body["recruitment_id_list"] = ["202"]
        elif self.channel == "campus":
            body["recruitment_id_list"] = ["201"]

        payload = self._post("/search/job/posts", body)
        if payload.get("error") or payload.get("code") != 0:
            return SearchResult(
                ok=False,
                source=self.source,
                total=0,
                fetched=0,
                positions=[],
                message=payload.get("message", "upstream error"),
                query=body,
            )

        data = payload.get("data") or {}
        rows = data.get("job_post_list") or []
        positions = [self._parse_row(r) for r in rows]
        return SearchResult(
            ok=True,
            source=self.source,
            total=data.get("count", len(positions)),
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
        for page in range(1, 6):
            body: dict = {
                "keyword": "",
                "limit": 100,
                "offset": (page - 1) * 100,
                "portal_type": 3,
                "portal_entrance": 1,
                "language": "zh",
            }
            if self.channel == "internship":
                body["recruitment_id_list"] = ["202"]
            elif self.channel == "campus":
                body["recruitment_id_list"] = ["201"]

            payload = self._post("/search/job/posts", body)
            if payload.get("error") or payload.get("code") != 0:
                return None
            rows = (payload.get("data") or {}).get("job_post_list") or []
            for r in rows:
                if str(r.get("id")) == post_id:
                    return self._parse_row(r)
            if len(rows) < 100:
                break
        return None

    def _parse_row(self, row: dict) -> Position:
        pid = str(row.get("id") or "")
        city_list = row.get("city_list") or []
        if city_list:
            location = " / ".join(c.get("name", "") for c in city_list if c.get("name"))
        else:
            location = (row.get("city_info") or {}).get("name", "")

        job_func = row.get("job_function") or {}
        job_cat = row.get("job_category") or {}
        recruit = row.get("recruit_type") or {}

        detail_prefix = (self.channel if self.channel != "social" else "campus")
        apply_url = f"{self.api_root.rsplit('/api/v1', 1)[0]}/{detail_prefix}/position/{pid}/detail"

        return Position(
            post_id=pid,
            title=(row.get("title") or "").strip(),
            company=self.display_name,
            source_platform=self.source,
            source_url=apply_url,
            location=location,
            salary_range="",
            department=job_func.get("name") or job_cat.get("name") or "",
            job_category=job_func.get("name") or "",
            recruit_type=recruit.get("name") or "",
            description=row.get("description") or "",
            requirements=row.get("requirement") or "",
            posted_date="",
        )

    def __repr__(self) -> str:
        return f"FeishuATSXAdapter({self.display_name}, channel={self.channel})"


XIAOMI_CONFIG = {
    "company": "xiaomi",
    "display_name": "小米",
    "api_root": "https://xiaomi.jobs.f.mioffice.cn/api/v1",
    "site_root": "https://xiaomi.jobs.f.mioffice.cn",
    "default_channel": "internship",
}


def create_xiaomi() -> FeishuATSXAdapter:
    return FeishuATSXAdapter(**XIAOMI_CONFIG)
