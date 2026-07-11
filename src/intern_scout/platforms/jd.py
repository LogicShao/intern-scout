"""京东招聘适配器 — 直接 API 调用。

API: POST https://zhaopin.jd.com/web/job/job_list
Body: pageIndex=N&pageSize=N&workCityJson=[]&jobTypeJson=[]&jobSearch=&depTypeJson=[]
Response: JSON array with full position details
"""

from typing import Optional
import requests
from urllib.parse import urlencode
from intern_scout.models import Position, SearchResult
from intern_scout.platforms.base import BaseAdapter
from intern_scout.utils import random_user_agent, rate_limit


class JdAdapter(BaseAdapter):
    def __init__(self):
        self.company = "jd"
        self.display_name = "京东"
        self.api_root = "https://zhaopin.jd.com"
        self._page_size = 20
        self._max_pages = 5
        self._session = requests.Session()

    @property
    def source(self) -> str:
        return "zhaopin.jd.com"

    def _post(self, body: dict) -> dict:
        url = f"{self.api_root}/web/job/job_list"
        rate_limit(self.source)
        headers = {
            "User-Agent": random_user_agent(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Referer": f"{self.api_root}/web/job/job_info_list/3",
        }
        try:
            resp = self._session.post(url, data=urlencode(body), headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return {"ok": True, "data": data}
            return {"ok": False, "error": str(data)}
        except requests.RequestException as e:
            return {"ok": False, "error": str(e)}

    def search(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> SearchResult:
        ps = page_size or self._page_size
        body = {
            "pageIndex": page,
            "pageSize": ps,
            "workCityJson": "[]",
            "jobTypeJson": "[]",
            "jobSearch": keyword.strip()[:60],
            "depTypeJson": "[]",
        }

        payload = self._post(body)
        if not payload.get("ok"):
            return SearchResult(
                ok=False, source=self.source, total=0, fetched=0,
                positions=[], message=payload.get("error", "upstream error"), query=body,
            )

        rows = payload["data"]
        positions = [self._parse_row(r) for r in rows]
        return SearchResult(
            ok=True, source=self.source,
            total=len(positions), fetched=len(positions),
            positions=positions, query=body,
        )

    def fetch_all(
        self,
        keyword: str = "",
        max_pages: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> SearchResult:
        return self.paginate_all(
            self.search, keyword=keyword,
            max_pages=max_pages or self._max_pages,
            page_size=page_size or self._page_size,
        )

    def fetch_detail(self, post_id: str) -> Optional[Position]:
        body = {"pageIndex": 1, "pageSize": 100, "workCityJson": "[]", "jobTypeJson": "[]", "jobSearch": post_id, "depTypeJson": "[]"}
        payload = self._post(body)
        if not payload.get("ok"):
            return None
        for r in payload["data"]:
            if str(r.get("id")) == post_id or str(r.get("positionId")) == post_id:
                return self._parse_row(r)
        return None

    def _parse_row(self, row: dict) -> Position:
        pid = str(row.get("id") or row.get("positionId") or "")
        return Position(
            post_id=pid,
            title=(row.get("positionName") or "").strip(),
            company=self.display_name,
            source_platform=self.source,
            source_url=f"{self.api_root}/web/job/job_info_list/{pid}",
            location=(row.get("workCity") or "").strip(),
            salary_range="",
            department=(row.get("positionDeptName") or "").strip(),
            job_category=(row.get("jobType") or "").strip(),
            recruit_type="社招",
            description=(row.get("workContent") or "").strip(),
            requirements=(row.get("qualification") or "").strip(),
            posted_date=row.get("formatPublishTime") or "",
        )

    def __repr__(self) -> str:
        return f"JdAdapter({self.source})"


def create_jd() -> JdAdapter:
    return JdAdapter()
