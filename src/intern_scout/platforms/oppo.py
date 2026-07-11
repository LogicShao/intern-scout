"""OPPO 招聘适配器 — 通过 openapi 直接调用，无需浏览器。

API 端点: POST /openapi/position/pageNew (无需登录)
recruitmentType: "Intern" (实习生) / "Graduate" (应届生) / "doctor" (博士生)
"""

from typing import Optional
import requests
from intern_scout.models import Position, SearchResult
from intern_scout.platforms.base import BaseAdapter
from intern_scout.utils import random_user_agent, rate_limit


class OppoAdapter(BaseAdapter):
    def __init__(self):
        self.company = "oppo"
        self.display_name = "OPPO"
        self.api_root = "https://careers.oppo.com"
        self._page_size = 20
        self._max_pages = 5
        self._session = requests.Session()

    @property
    def source(self) -> str:
        return "careers.oppo.com"

    def _post(self, body: dict) -> dict:
        url = f"{self.api_root}/openapi/position/pageNew"
        rate_limit(self.source)
        headers = {
            "User-Agent": random_user_agent(),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": f"{self.api_root}/campus",
        }
        try:
            resp = self._session.post(url, json=body, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"code": -1, "msg": str(e)}

    def search(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> SearchResult:
        ps = page_size or self._page_size
        body: dict = {
            "pageNum": page,
            "pageSize": ps,
            "recruitmentType": "Intern",
        }
        if keyword:
            body["keyword"] = keyword.strip()[:60]

        payload = self._post(body)
        if payload.get("code") != 0:
            return SearchResult(
                ok=False, source=self.source, total=0, fetched=0,
                positions=[], message=payload.get("msg", "upstream error"), query=body,
            )

        data = payload.get("data") or {}
        rows = data.get("records") or []
        positions = [self._parse_row(r) for r in rows]
        return SearchResult(
            ok=True, source=self.source,
            total=data.get("total", len(positions)),
            fetched=len(positions), positions=positions, query=body,
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
        body = {"pageNum": 1, "pageSize": 100, "recruitmentType": "Intern"}
        payload = self._post(body)
        if payload.get("code") != 0:
            return None
        for r in (payload.get("data") or {}).get("records") or []:
            if str(r.get("idRecruitPosition") or r.get("idProjPosition")) == post_id:
                return self._parse_row(r)
        return None

    def _parse_row(self, row: dict) -> Position:
        pid = str(row.get("idRecruitPosition") or row.get("idProjPosition") or "")
        return Position(
            post_id=pid,
            title=(row.get("positionName") or row.get("projectPositionName", "")).strip(),
            company=self.display_name,
            source_platform=self.source,
            source_url=f"{self.api_root}/university/oppo/campus/post?recruitType={row.get('recruitmentType', 'Intern')}",
            location=(row.get("workCityName") or "").strip(),
            salary_range="",
            department=(row.get("positionTypeName") or "").strip(),
            job_category=(row.get("positionTypeName") or "").strip(),
            recruit_type=(row.get("recruitmentTypeName") or "实习生").strip(),
            description=(row.get("positionDesc") or row.get("projectPositionDesc", "")).strip(),
            requirements=(row.get("positionRequire") or row.get("projectPositionRequire", "")).strip(),
            posted_date=row.get("releaseTime") or "",
        )

    def __repr__(self) -> str:
        return f"OppoAdapter({self.source})"


def create_oppo() -> OppoAdapter:
    return OppoAdapter()
