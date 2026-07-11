"""拼多多招聘适配器 — Playwright DOM 提取 (anti_content 反爬)。

PDD API 需要 anti_content 参数 (由混淆 JS 生成)，无法直接调用。
适配器使用 Playwright 渲染页面后从 .recruit-card_card DOM 提取岗位。
"""

from typing import Optional
from intern_scout.models import Position, SearchResult
from intern_scout.platforms.base import BaseAdapter


class PddAdapter(BaseAdapter):
    def __init__(self):
        self.company = "pdd"
        self.display_name = "拼多多"
        self.base_url = "https://careers.pddglobalhr.com/campus/grad"

    @property
    def source(self) -> str:
        return "careers.pddglobalhr.com"

    def _error(self, msg: str) -> SearchResult:
        return SearchResult(ok=False, source=self.source, total=0, fetched=0, positions=[], message=msg)

    def search(self, keyword: str = "", page: int = 1, page_size: int = 20) -> SearchResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._error("playwright required: pip install playwright && playwright install chromium")

        positions: list[Position] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page_obj = browser.new_page()
                page_obj.goto(self.base_url, wait_until="domcontentloaded", timeout=20000)
                page_obj.wait_for_timeout(10000)

                cards = page_obj.query_selector_all(".recruit-card_card__P6WRU")
                for card in cards:
                    try:
                        title_el = card.query_selector(".recruit-card_title__yxRoN")
                        title = title_el.inner_text().strip() if title_el else ""
                        href = title_el.get_attribute("href") if title_el else ""
                        full_text = card.inner_text()
                        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
                        detail_url = (
                            href if href and href.startswith("http")
                            else f"https://careers.pddglobalhr.com{href}" if href
                            else self.base_url
                        )

                        dept = ""
                        location = ""
                        batch = ""
                        for l in lines:
                            if l in ("技术", "产品", "运营", "设计", "市场", "职能", "数据", "区域业务", "语言", "视觉类", "市场营销"):
                                dept = l
                            elif any(c in l for c in ("上海", "北京", "深圳", "广州", "杭州", "成都", "武汉")):
                                location = l
                            elif "届" in l:
                                batch = l

                        if title:
                            positions.append(Position(
                                post_id="",
                                title=title,
                                company=self.display_name,
                                source_platform=self.source,
                                source_url=detail_url,
                                location=location,
                                salary_range="",
                                department=dept,
                                job_category=dept,
                                recruit_type=f"校招{batch}",
                                description=full_text,
                                requirements="",
                            ))
                    except Exception:
                        continue
                browser.close()
        except Exception as e:
            return self._error(str(e))

        if keyword:
            kw = keyword.lower()
            positions = [p for p in positions if kw in p.title.lower() or kw in p.department.lower()]

        total = len(positions)
        start = (page - 1) * page_size
        return SearchResult(ok=True, source=self.source, total=total,
                           fetched=min(page_size, max(0, total - start)),
                           positions=positions[start:start + page_size])

    def fetch_all(self, keyword: str = "", max_pages: int = 1, page_size: int = 100) -> SearchResult:
        return self.search(keyword=keyword, page=1, page_size=page_size or 100)

    def fetch_detail(self, post_id: str) -> Optional[Position]:
        return None

    def __repr__(self) -> str:
        return f"PddAdapter({self.source})"


def create_pdd() -> PddAdapter:
    return PddAdapter()
