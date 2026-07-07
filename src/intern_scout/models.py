from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Position:
    post_id: str
    title: str
    company: str
    source_platform: str
    source_url: str
    location: str
    salary_range: str
    department: str
    job_category: str
    recruit_type: str
    description: str
    requirements: str
    head_count: Optional[int] = None
    posted_date: str = ""
    crawled_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "post_id": self.post_id,
            "title": self.title,
            "company": self.company,
            "source_platform": self.source_platform,
            "source_url": self.source_url,
            "location": self.location,
            "salary_range": self.salary_range,
            "department": self.department,
            "job_category": self.job_category,
            "recruit_type": self.recruit_type,
            "description": self.description,
            "requirements": self.requirements,
            "head_count": self.head_count,
            "posted_date": self.posted_date,
            "crawled_at": self.crawled_at.isoformat(),
        }


@dataclass
class SearchResult:
    ok: bool
    source: str
    total: int
    fetched: int
    positions: list[Position]
    message: str = ""
    query: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "source": self.source,
            "total": self.total,
            "fetched": self.fetched,
            "message": self.message,
            "query": self.query,
            "positions": [p.to_dict() for p in self.positions],
        }
