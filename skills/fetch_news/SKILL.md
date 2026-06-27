---
name: fetch_news
description: Query TradeHub's news database — financial news flashes (财联社快讯, real-time) and AI-generated daily digests (每日要闻简报). Use this skill when the user wants to read financial news, get market updates, browse daily news summaries, or search historical news from TradeHub. Triggers include "show me today's financial news", "what happened in the market yesterday", "get the daily news digest", "search news about <topic>", "财联社快讯", "今日要闻", "市场动态".
---

# Fetch News from TradeHub

This skill queries the **TradeHub news REST API** to retrieve financial news collected from 财联社 (cls.cn) and AI-generated daily digests produced by Claude.

Three operations are available (these mirror the previous MCP tools that have been removed):

| Operation | Endpoint | Use case |
|-----------|----------|----------|
| `list_news_flash` | `GET /api/v1/news/flash` | 实时快讯列表（按时间范围 + 关键词过滤） |
| `list_news_digest` | `GET /api/v1/news/digest` | 每日要闻简报列表（Claude 生成的 markdown 摘要） |
| `list_news_weekly` | `GET /api/v1/news/weekly` | 每周投研简报列表（基于 ≥5 个日级简报 LLM 二次聚合，允许缺失 2 天） |
| `search_news` | `GET /api/v1/news/search` | 关键词搜索（走财联社搜索引擎） |

## When to Use

Use this skill when the user:

- Asks for recent financial news / market updates
- Wants the daily news digest (要闻 / 简报)
- Searches for news on a specific topic / stock / company
- Mentions 财联社、快讯、要闻、简报、新闻、市场动态、digest、newsflash
- Wants to know "what happened today / yesterday in the market"

**Do NOT use this skill for:**

- Stock prices or charts (use stock-quote skills instead)
- General web search (this only covers TradeHub's curated CLS feed)
- Non-financial news

## Calling Convention (重要)

**直接调用，不要预先检查或询问 API Key、URL 等配置。** CLI 会自动从环境变量 `TRADEHUB_API_KEY`、或 skill 目录下的 `TRADEHUB_API_KEY` 文件读取凭证。绝大多数用户已配置好持久化凭证，预先询问只会徒增打扰。

调用流程：
1. 直接执行命令（**不要带 `--api-key` 参数**，让 CLI 自动读取已配置的 key）
2. 若返回鉴权错误（exit code 2、HTTP 401、或 stderr 出现 "API Key" 字样），再按本文档末尾的 [配置 API Key](#配置-api-key) 引导用户一次性完成配置，然后重试
3. 其他错误按正常排错流程处理

参数示例中**不再出现 `--api-key th_xxx`**，因为它应来自环境/文件而非命令行。

## How to Use

Two equivalent paths — pick whichever fits the runtime.

### Path A: Bundled Python CLI (`fetch_news.py`)

Best for agents with shell access. Pure-stdlib Python 3 (no dependencies).

```bash
# List today's news flash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py flash \
  --start "2026-06-22 00:00:00" \
  --end   "2026-06-22 23:59:59"

# List recent digests (default: last 30 days)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py digest

# Get a specific digest by date
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py digest \
  --start 2026-06-21 --end 2026-06-21

# Search news (keyword)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py search \
  --keyword "美联储" --max-count 10

# List weekly digests (default: last 90 days)
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py weekly

# Get a specific week by week_start date
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py weekly \
  --start 2026-06-15 --end 2026-06-15
```

Useful flags:
- `--url https://your-host` — override server URL (default: `https://tradehub.niotech.cc`; also read from `TRADEHUB_URL` env)
- `--page-size N` — pagination (flash max 5000, digest max 180, weekly max 60, search max 100)
- `--page N` — page number
- `--json` — emit raw JSON (default is human-readable summary)
- `--api-key th_xxx` — only pass this when debugging auth issues; normally rely on `TRADEHUB_API_KEY` env var or `TRADEHUB_API_KEY` file in skill dir

### Path B: Direct curl (for agents without Python)

```bash
# Flash
curl -H "Authorization: Bearer th_xxx" \
  "https://tradehub.niotech.cc/api/v1/news/flash?start_time=2026-06-22%2000:00:00&end_time=2026-06-22%2023:59:59&page_size=20"

# Digest
curl -H "Authorization: Bearer th_xxx" \
  "https://tradehub.niotech.cc/api/v1/news/digest?page_size=10"

# Search
curl -H "Authorization: Bearer th_xxx" \
  "https://tradehub.niotech.cc/api/v1/news/search?keyword=美联储&max_count=10"

# Weekly digest (default: last 90 days)
curl -H "Authorization: Bearer th_xxx" \
  "https://tradehub.niotech.cc/api/v1/news/weekly?page_size=5"
```

## Response Schemas

### `list_news_flash` response

```json
{
  "items": [
    {
      "id": 12345,
      "source": "cls",
      "source_id": 2404974,
      "title": "...",
      "content": "...",
      "ctime": 1782061469,           // unix seconds
      "author": "央视新闻" | null,
      "subjects": [{"subject_name": "中东冲突", ...}]
    }
  ],
  "total": 1234,
  "page": 1,
  "page_size": 500
}
```

### `list_news_digest` response

```json
{
  "items": [
    {
      "id": 89,
      "digest_date": "2026-06-21",
      "summary": "# 2026-06-21 要闻\n\n## 地缘政治\n...",  // full markdown
      "news_count": 312,
      "status": "success",
      "duration_ms": 8421
    }
  ],
  "total": 30,
  "page": 1,
  "page_size": 60
}
```

### `list_news_weekly` response

```json
{
  "items": [
    {
      "id": 12,
      "week_start_date": "2026-06-15",
      "week_end_date": "2026-06-21",
      "summary": "# 2026-06-15 ~ 2026-06-21 周报\n\n## 本周总览\n...",  // full markdown
      "day_count": 7,
      "news_count": 2184,
      "status": "success",
      "duration_ms": 180000
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 20
}
```

**Field semantics:**
- `week_start_date` / `week_end_date`: 自然周范围 (`week_start_date` 始终是周一)
- `day_count`: 实际覆盖天数 (5~7)，service 允许缺失 2 天以内（<5 则不生成周报）。完整周=7，部分周=5 或 6
- `summary`: 完整 markdown, 8 个二级标题 (本周总览 / 宏观与政策 / 资金与流动性 / 行业与产业 / 公司与个股 / 海外与外部 / 情绪与主题 / 下周关注)
- 部分周 (`day_count < 7`) 的 `summary` 会标注缺失日期，LLM 基于已有内容总结, 不臆测缺失天

### `search_news` response

```json
{
  "list": [
    {"title": "...", "content": "...", "ctime": 1782061469, ...}
  ],
  "scanned": 3,
  "pages_fetched": 1
}
```

**Field semantics:**
- `scanned`: number of CLS pages fetched from upstream (may report `0` when results come from a warm cache; treat as informational only)
- `pages_fetched`: total CLS pages traversed during the search
- `list[].ctime`: unix seconds; convert to Asia/Shanghai for display
- `list[].title` / `list[].content`: may contain `<em>...</em>` HTML highlight tags from CLS — strip them for human display (the bundled CLI does this in human-readable mode, but `--json` mode preserves them for downstream agents that want highlight info)

**Note on `max_count`:** the server treats this as a best-effort hint and may return more items than requested. The bundled CLI truncates display to `--max-count` in human-readable mode. If you call the REST API directly, truncate client-side if you need strict limits.

## Authentication

All requests require an `Authorization: Bearer th_xxx` header. The server recognizes API Keys by the `th_` prefix and routes them through the dual-auth path (JWT also accepted, but skills should always use API Key).

Failure modes:
- **`exit code 2` (CLI)** — no API Key found in `--api-key` / `TRADEHUB_API_KEY` env / `TRADEHUB_API_KEY` file. See [配置 API Key](#配置-api-key) below.
- `401` — invalid / revoked / wrong-case API Key
- `422` — missing required params (e.g. `start_time` for flash)
- `502` — CLS upstream unavailable or anti-crawl triggered (search only)

## 配置 API Key

**仅在调用失败（exit code 2 或 401）时才引导用户配置。** 平时不要主动检查或询问。

API Key 格式 `th_<5>_<27>`（共 36 字符，例如 `th_MTWArmpi...`），用户在 TradeHub Web → Avatar → Settings → "API Key" 卡片生成。

提供 key 的方式（优先级从高到低）：

1. `--api-key th_xxx` 命令行参数（仅调试用，会暴露在 shell history）
2. `TRADEHUB_API_KEY` 环境变量
3. **`TRADEHUB_API_KEY` 文件** — 推荐的持久化方式，放在 skill 目录下（即 `${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/TRADEHUB_API_KEY`），内容仅一行 key（可带尾换行），已被 `.gitignore` 忽略

服务器 URL 默认 `https://tradehub.niotech.cc`，本地开发可通过 `TRADEHUB_URL=http://localhost:8000` 或 `--url` 覆盖。

**安全提醒：** 永远不要把 API Key 文件提交到仓库，也不要在日志里明文打印。

## Tips for the Agent

- **Prefer `--json` mode** (`--json` flag) when you want to programmatically inspect / filter / reformat the data yourself. Human-readable mode is for direct user display.
- **Time zone**: `start_time` / `end_time` are Asia/Shanghai. The server and CLS use this zone. The user's local time may differ — convert before querying.
- **`start_time` is required for flash** but optional for digest. Don't forget it.
- **`page_size` caps**: flash=5000, digest=180, weekly=60, search=100. For "today's news" flash with `page_size=500` is usually enough.
- **Digest `summary` is full markdown** — render it as markdown when displaying to the user.
- **Search returns CLS-formatted items** (different shape from flash). Don't merge them blindly.
- **Rate limiting**: there is none on the REST side, but CLS search (502s) has its own anti-crawl. If search returns 502, fall back to flash with a keyword filter.

## Windows 编码 (重要)

pipe 输出到另一个 python 进程时，消费端默认按 cp936 解码 stdin，会把 UTF-8 中文读成乱码。**Windows 上务必先 `set PYTHONUTF8=1`（cmd）或 `$env:PYTHONUTF8=1`（PowerShell）再调用。** 例：

```cmd
set PYTHONUTF8=1 && python3 .../fetch_news.py digest --json | python3 -c "import sys,json; print(json.load(sys.stdin))"
```

其他方案：消费端用 `python3 -X utf8`，或写临时文件后用 `open(...,encoding='utf-8')` 读。

## Examples

### User: "今天市场有什么新闻？"

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py flash \
  --start "2026-06-22 00:00:00" --end "2026-06-22 23:59:59" \
  --page-size 50
```

Summarize the top items by subject cluster.

### User: "昨天的重要新闻汇总"

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py digest \
  --start 2026-06-21 --end 2026-06-21
```

Render the returned `summary` markdown directly.

### User: "搜一下美联储相关新闻"

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py search \
  --keyword "美联储" --max-count 15
```

Group results by time and mention source attribution.

### User: "过去 90 天有什么投资机会？"

```bash
# 周报一次消费 13 周数据 (90 天 ≈ 13 周), 效率远高于逐日看 90 份日报
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py weekly \
  --page-size 20
```

逐周阅读 `summary` markdown, 提取跨周主题演变、当前主线、下周关注。日级细节按需用 `digest --start <date> --end <date>` 回查。
