import random
import time
from collections import OrderedDict


USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
]

_last_request_time: dict[str, float] = {}


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def rate_limit(source: str, min_interval: float = 2.0):
    now = time.time()
    last = _last_request_time.get(source, 0)
    elapsed = now - last
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_time[source] = time.time()


def deduplicate(positions: list, key: str = "post_id") -> list:
    seen: OrderedDict[str, object] = OrderedDict()
    for p in positions:
        pid = getattr(p, key, None) if hasattr(p, key) else p.get(key)
        if pid and pid not in seen:
            seen[pid] = p
    return list(seen.values())


def clean_html(html: str) -> str:
    if not html:
        return ""
    from html import unescape as html_unescape
    import re
    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+", " ", text)
    return html_unescape(text).strip()
