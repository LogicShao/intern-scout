"""华为招聘适配器 — 通过 reccampportal API 直接调用。

API 端点: GET /reccampportal/services/portal/portalpub/getJob/newHr/page/10/1
需要先访问校招页面获取 session cookie。
"""

from typing import Optional
import requests
from intern_scout.models import Position, SearchResult
from intern_scout.platforms.base import BaseAdapter
from intern_scout.utils import random_user_agent, rate_limit


class HuaweiAdapter(BaseAdapter):
    def __init__(self):
        self.company = "huawei"
        self.display_name = "华为"
        self.api_root = "https://career.huawei.com"
        self.campus_url = f"{self.api_root}/reccampportal/portal5/campus-recruitment.html"
        self._page_size = 20
        self._max_pages = 17
        self._session = requests.Session()
        self._session_ready = False

    @property
    def source(self) -> str:
        return "career.huawei.com"

    def _ensure_session(self):
        if self._session_ready:
            return
        try:
            self._session.get(
                self.campus_url,
                headers={"User-Agent": random_user_agent()},
                timeout=15,
            )
            self._session_ready = True
        except requests.RequestException:
            pass

    def _get(self, params: dict) -> dict:
        self._ensure_session()
        url = f"{self.api_root}/reccampportal/services/portal/portalpub/getJob/newHr/page/10/1"
        rate_limit(self.source)
        headers = {
            "User-Agent": random_user_agent(),
            "Accept": "application/json",
            "Referer": self.campus_url,
        }
        try:
            resp = self._session.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    def search(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> SearchResult:
        ps = page_size or self._page_size
        params: dict = {"curPage": page, "pageSize": ps}
        if keyword:
            params["keyWords"] = keyword.strip()[:60]

        payload = self._get(params)
        if "error" in payload:
            return SearchResult(
                ok=False, source=self.source, total=0, fetched=0,
                positions=[], message=payload["error"], query=params,
            )

        page_vo = payload.get("pageVO") or {}
        rows = payload.get("result") or []
        positions = [self._parse_row(r) for r in rows]
        return SearchResult(
            ok=True, source=self.source,
            total=page_vo.get("totalRows", len(positions)),
            fetched=len(positions), positions=positions, query=params,
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
        params = {"curPage": 1, "pageSize": 200, "keyWords": post_id}
        payload = self._get(params)
        if "error" in payload:
            return None
        for r in payload.get("result") or []:
            if str(r.get("jobId")) == post_id:
                return self._parse_row(r)
        return None

    def _parse_row(self, row: dict) -> Position:
        pid = str(row.get("jobId") or "")
        return Position(
            post_id=pid,
            title=(row.get("nameCn") or row.get("jobname") or "").strip(),
            company=self.display_name,
            source_platform=self.source,
            source_url=f"{self.api_root}/reccampportal/portal5/campus-recruitment-detail.html?jobId={pid}",
            location=(row.get("jobAddress") or row.get("jobArea") or "").strip(),
            salary_range="",
            department=(row.get("jobFamilyName") or row.get("deptName") or "").strip(),
            job_category=(row.get("jobFamilyName") or "").strip(),
            recruit_type="校招",
            description=(row.get("mainBusiness") or "").strip(),
            requirements=(row.get("jobRequire") or "").strip(),
            posted_date=(row.get("releaseDate") or "")[:10],
        )

    def __repr__(self) -> str:
        return f"HuaweiAdapter({self.source})"


def create_huawei() -> HuaweiAdapter:
    return HuaweiAdapter()
