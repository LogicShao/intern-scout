"""intern-scout — 中国科技公司官网实习岗位爬取工具。

用法:
    python -m intern_scout.crawler --company vivo --keyword "后端" --limit 20
    python -m intern_scout.crawler --companies vivo,xiaomi --keyword "AI" --output table
    python -m intern_scout.crawler --all --keyword "数据分析" --limit 30
"""

from intern_scout.platforms.beisen import (
    create_vivo, create_iflytek, create_transsion, create_cxmt,
    create_sany, create_dahua, create_chery, create_picc,
    create_hellobike, create_genertec, create_huolala,
    create_ucloud, create_sugon,
)
from intern_scout.platforms.feishu_atsx import create_xiaomi, create_nio
from intern_scout.platforms.huawei import create_huawei
from intern_scout.platforms.oppo import create_oppo
from intern_scout.reporter import format_output
from intern_scout.models import SearchResult

ADAPTERS = {
    "vivo":       create_vivo,
    "xiaomi":     create_xiaomi,
    "nio":        create_nio,
    "iflytek":    create_iflytek,
    "transsion":  create_transsion,
    "cxmt":       create_cxmt,
    "sany":       create_sany,
    "dahua":      create_dahua,
    "chery":      create_chery,
    "picc":       create_picc,
    "hellobike":  create_hellobike,
    "genertec":   create_genertec,
    "huolala":    create_huolala,
    "ucloud":     create_ucloud,
    "sugon":      create_sugon,
    "huawei":     create_huawei,
    "oppo":       create_oppo,
}


def crawl_one(company: str, keyword: str = "", limit: int = 20) -> SearchResult:
    factory = ADAPTERS.get(company)
    if not factory:
        return SearchResult(
            ok=False, source=company, total=0, fetched=0,
            positions=[], message=f"Unknown company: {company}. Supported: {list(ADAPTERS)}",
        )
    adapter = factory()
    page_size = getattr(adapter, "_page_size", 20)
    for attempt in range(2):
        result = adapter.fetch_all(keyword=keyword, max_pages=1, page_size=limit)
        if result.ok or attempt == 1:
            if result.ok and len(result.positions) > limit:
                result.positions = result.positions[:limit]
                result.fetched = len(result.positions)
            return result
        import time
        time.sleep(2)
    return result


def crawl(companies: list[str], keyword: str = "", limit: int = 20) -> list[SearchResult]:
    results: list[SearchResult] = []
    for c in companies:
        r = crawl_one(c, keyword=keyword, limit=limit)
        results.append(r)
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="中国科技公司实习岗位爬取")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--company", help="单公司")
    group.add_argument("--companies", help="多公司 (逗号分隔)")
    group.add_argument("--all", action="store_true", help="所有已支持公司")
    group.add_argument("--list", action="store_true", help="列出已支持公司")
    parser.add_argument("--keyword", default="", help="搜索关键词")
    parser.add_argument("--limit", type=int, default=20, help="最大返回数 (default: 20)")
    parser.add_argument("--output", choices=["json", "table", "excel"], default="json")
    parser.add_argument("--output-file", default="", help="输出文件路径")

    args = parser.parse_args()

    if args.list:
        print("Supported companies:", ", ".join(ADAPTERS.keys()))
        return

    if args.all:
        companies = list(ADAPTERS.keys())
    elif args.companies:
        companies = [c.strip() for c in args.companies.split(",")]
    else:
        companies = [args.company]

    results = crawl(companies, keyword=args.keyword, limit=args.limit)
    output = format_output(results, fmt=args.output, filepath=args.output_file)
    print(output)


if __name__ == "__main__":
    main()
