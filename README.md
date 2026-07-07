# intern-scout

中国科技公司官网实习岗位爬取工具。直接调用招聘站内部 API，无需登录，无需代理。

**14 家公司，500+ 实时实习岗位，一条命令全量搜索。**

```bash
intern-scout --all --keyword "后端" --limit 20 --output table
```

## 为什么 intern-scout

大多数招聘聚合器抓取 LinkedIn、第三方招聘平台（实习僧、BOSS直聘）——数据重复、虚假岗位多。

intern-scout **直连公司官方招聘系统的内部 API**，每一行数据来自公司自己的 ATS 平台：

-   **一手数据源** — 岗位名称、地点、薪资来自公司官方系统
-   **零重复** — 一个岗位 = 一条记录
-   **无需登录** — 所有 API 均为公开匿名端点
-   **MIT 协议** — 完全开源

## 安装

```bash
pip install -e .
```

需要 Python >= 3.11。可选依赖：

```bash
pip install playwright && playwright install chromium
# 仅华为、OPPO 需要浏览器自动化
```

## 使用

```bash
# 单公司搜索
intern-scout --company vivo --keyword "后端" --limit 20

# 多公司搜索
intern-scout --companies vivo,xiaomi,dahua --keyword "AI" --output table

# 全平台搜索
intern-scout --all --keyword "数据分析" --limit 30

# 列出所有支持的公司
intern-scout --list

# 输出格式
intern-scout --company xiaomi --output json     # JSON（默认）
intern-scout --company xiaomi --output table    # Markdown 表格
intern-scout --company xiaomi --output excel    # Excel 文件
```

JSON 输出示例：

```json
{
  "results": [
    {
      "ok": true,
      "source": "hr-campus.vivo.com",
      "total": 141,
      "fetched": 3,
      "positions": [
        {
          "post_id": "561263690",
          "title": "AI后端开发工程师-27届实习",
          "company": "vivo",
          "department": "AI产品部",
          "location": "浙江省·杭州市, 江苏省·南京市",
          "salary_range": "面议",
          "recruit_type": "实习生",
          "apply_url": "https://hr-campus.vivo.com/intern/detail?jobAdId=561263690"
        }
      ]
    }
  ]
}
```

## 已支持公司

### API 直连（14 家，无需浏览器）

| 公司 | ATS 平台 | 实习岗位数 |
| ---- | -------- | ---------- |
| **vivo** | 北森 iTalent | 141 |
| **小米** | 飞书 ATSX | 478 |
| 科大讯飞 | 北森 iTalent | 27 |
| 传音控股 | 北森 iTalent | 64 |
| 长鑫存储 | 北森 iTalent | 13 |
| 三一重工 | 北森 iTalent | 19 |
| **大华** | 北森 iTalent | 99 |
| 奇瑞汽车 | 北森 iTalent | 29 |
| 中国人保 | 北森 iTalent | 33 |
| **哈啰出行** | 北森 iTalent | 75 |
| 中国通用技术 | 北森 iTalent | 8 |
| 货拉拉 | 北森 iTalent | 2 |
| UCloud | 北森 iTalent | 11 |
| 中科曙光 | 北森 iTalent | 3 |

### Playwright 浏览器模式（2 家，需系统依赖）

| 公司 | 说明 |
| ---- | ---- |
| **华为** | 自研 portal5 架构，需 Playwright 拦截 XHR |
| **OPPO** | 自研 React SPA，不依赖任何已知 ATS |

> 浏览器模式需要系统库：`apt install libnspr4 libnss3 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2`

## 架构

### ATS 家族模式

中国科技公司招聘站复用标准 ATS 平台。一个适配器覆盖 N 家公司：

```
┌──────────────────────────────────────────┐
│                intern-scout               │
│           (crawler.py 主调度器)            │
└──────────────────┬───────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────────┐ ┌──▼───────┐ ┌───▼──────────┐
│ 北森 iTalent │ │ 飞书 ATSX │ │  自研 API    │
│ (zhiye.com) │ │(feishu.cn)│ │  (Playwright) │
│             │ │           │ │              │
│  13 家公司   │ │  小米      │ │  华为, OPPO  │
└─────────────┘ └───────────┘ └──────────────┘
```

**新增一家北森租户只需 6 行配置**：

```python
"newco": {
    "company": "newco", "display_name": "新公司",
    "api_root": "https://newco.zhiye.com",
    "site_root": "https://newco.zhiye.com",
    "category": ["3"],  # 3 = 实习生
}
```

### 数据流

```
用户命令
  │
  ▼
crawler.py ──► 选择适配器 ──► POST 内部 API ──► 解析 JSON
  │                                                  │
  ▼                                                  ▼
reporter.py ◄── SearchResult ◄── Position 模型 ◄── 归一化
  │
  ▼
JSON / Markdown 表格 / Excel
```

## 飞书 ATSX 扩展说明

飞书招聘（Feishu Recruiting）是字节跳动推出的 SaaS ATS 平台。多家 AI 公司使用此平台（小米、NIO、MiniMax、智谱、iQIYI、01.AI、百川、智元）。

### 域名迁移

```
旧域名 (已宕机):   {company}.jobs.f.mioffice.cn  (小米内部 Fork)
新域名:            {company}.jobs.feishu.cn       (标准飞书)
```

`mioffice.cn` 是小米的飞书分叉域名。2026 年中该 CDN 全面宕机，所有基于此域名的 API 返回 502。小米是唯一仍在此域名上活跃的租户。

### API 需要 CSRF Token

`nio.jobs.feishu.cn` 的 ATSX 平台已检测到，但 API 端点 `/api/v1/search/job/posts` 返回 405 Method Not Allowed。与字节跳动主站相同，飞书招聘 API 需要先获取 CSRF token：

```python
# 步骤 1: 获取 CSRF token
GET /api/v1/csrf/token
# → set-cookie: atsx-csrf-token=xxx

# 步骤 2: 带 token 查询
POST /api/v1/search/job/posts
Header: x-csrf-token: xxx
```

### 后续扩展路线

| 步骤 | 内容 |
| ---- | ---- |
| 1 | 实现 CSRF token 自动获取 |
| 2 | 验证 NIO (`nio.jobs.feishu.cn`) 的 API |
| 3 | 确定 MiniMax / 智谱 / iQIYI 的租户子域名 |
| 4 | 批量注册所有飞书 ATSX 租户 |

### 备选方案：Playwright 拦截

如果 CSRF 流程过于复杂，可回退到浏览器自动化：
1. 用 Playwright 打开公司招聘首页
2. 拦截并记录 POST `/api/v1/search/job/posts` 的完整请求（headers + body）
3. 在 Python 中复现该请求

## 项目结构

```
intern-scout/
├── pyproject.toml
├── README.md
├── src/intern_scout/
│   ├── crawler.py          # CLI 主入口
│   ├── models.py           # Position, SearchResult 数据模型
│   ├── reporter.py         # JSON/Markdown/Excel 输出
│   ├── utils.py            # rate_limit, deduplicate, clean_html
│   └── platforms/
│       ├── base.py         # BaseAdapter 基类
│       ├── beisen.py       # 北森 iTalent (13 家租户)
│       ├── feishu_atsx.py  # 飞书 ATSX (小米)
│       ├── huawei.py       # 华为 (Playwright)
│       └── oppo.py         # OPPO (Playwright)
└── .sisyphus/
    ├── specs/intern-crawler-skill.md
    └── skills/intern-crawler/
        ├── SKILL.md
        └── config.yaml
```

## 贡献指南

### 新增北森租户

1. 在 `beisen.py` 的 `BEISEN_TENANTS` 中添加配置
2. 添加工厂函数 lambda
3. 在 `crawler.py` 的 `ADAPTERS` 中注册

### 新增飞书 ATSX 租户

1. 确定公司域名和 `portal-channel` 值
2. 在 `feishu_atsx.py` 中按小米模板创建配置
3. 实现 CSRF token 流程

### 新增自研 API 公司

1. 继承 `BaseAdapter`
2. 实现 `search()`, `fetch_all()`, `fetch_detail()`
3. 注册到 `crawler.py`

## 致谢

-   [HA7CH/job-pro](https://github.com/HA7CH/job-pro) — 50 家中国公司 API 逆向成果（TypeScript 参考实现）
-   [kalil0321/ats-scrapers](https://github.com/kalil0321/ats-scrapers) — 47 个 ATS 平台数据集，北森 93+ 租户验证
-   [Aaron-Bushnell/internship-tracker](https://github.com/Aaron-Bushnell/internship-tracker) — Python 实习岗位采集器参考

## License

MIT
