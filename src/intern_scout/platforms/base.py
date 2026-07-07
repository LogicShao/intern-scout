from abc import ABC, abstractmethod
from typing import Optional
from intern_scout.models import Position, SearchResult


class BaseAdapter(ABC):
    @property
    @abstractmethod
    def source(self) -> str:
        ...

    @abstractmethod
    def search(
        self,
        keyword: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResult:
        ...

    @abstractmethod
    def fetch_all(
        self,
        keyword: str = "",
        max_pages: int = 10,
        page_size: int = 30,
    ) -> SearchResult:
        ...

    @abstractmethod
    def fetch_detail(self, post_id: str) -> Optional[Position]:
        ...

    def paginate_all(
        self,
        search_fn,
        keyword: str,
        max_pages: int,
        page_size: int,
    ) -> SearchResult:
        bucket: list[Position] = []
        total: Optional[int] = None
        for page in range(1, max_pages + 1):
            result = search_fn(keyword=keyword, page=page, page_size=page_size)
            if not result.ok:
                return SearchResult(
                    ok=False,
                    source=self.source,
                    total=0,
                    fetched=len(bucket),
                    positions=bucket,
                    message=result.message,
                )
            if total is None:
                total = result.total
            if not result.positions:
                break
            bucket.extend(result.positions)
            if total is not None and len(bucket) >= total:
                break
        return SearchResult(
            ok=True,
            source=self.source,
            total=total or len(bucket),
            fetched=len(bucket),
            positions=bucket,
        )
