---
name: fetch_news
description: Query TradeHub's news database — financial news flashes (财联社快讯, real-time) and AI-generated daily digests (每日要闻简报). Use this skill when the user wants to read financial news, get market updates, browse daily news summaries, or search historical news from TradeHub. Triggers include "show me today's financial news", "what happened in the market yesterday", "get the daily news digest", "search news about <topic>", "财联社快讯", "今日要闻", "市场动态".
---

# Fetch News from TradeHub

> **⚠️ Windows 编码注意（调用前必读）**：Windows Git Bash 默认非 UTF-8，中文输出会乱码。**优先使用 PowerShell 调用**，或写临时文件后读取。Git Bash 调用示例：
> ```bash
> # 方式1: PowerShell（推荐）
> powershell.exe -NoProfile -Command "python3 .../fetch_news.py digest --start 2026-06-26"
> # 方式2: 写文件再读
> python3 .../fetch_news.py digest --json > /tmp/digest.json && cat /tmp/digest.json
> # 方式3: 设置环境变量
> PYTHONUTF8=1 python3 .../fetch_news.py digest
> ```

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

**🔒 API Key 隐私原则**

1. **大模型绝对不要读取或显示 API Key** - 不要用 Read/Write 等工具读取 `TRADEHUB_API_KEY` 文件，不要在对话中询问或显示 key 内容
2. **脚本自动读取配置** - CLI 会自动从环境变量或 skill 目录下的 `TRADEHUB_API_KEY` 文件读取，无需大模型介入
3. **只在鉴权失败时提示用户** - 当命令返回 exit code 2 或 stderr 出现 "missing API key" 时，再引导用户配置

调用流程：
1. 直接执行命令（**不带 --api-key 参数**）
2. 若返回鉴权错误（exit code 2、HTTP 401、stderr 出现 "API Key" 字样），按 [配置 API Key](#配置-api-key) 引导用户配置后重试
3. 其他错误按正常排错流程处理

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
- `--json` — emit raw JSON (default: human-readable; **推荐使用此模式避免编码问题**)
- `--url https://your-host` — override server URL (default: `https://tradehub.niotech.cc`; also read from `TRADEHUB_URL` env)
- `--page-size N` — pagination (flash max 5000, digest max 180, weekly max 60, search max 100)
- `--page N` — page number

### Path B: PowerShell (Windows 推荐)

Windows PowerShell 能正确处理 UTF-8 编码：

```powershell
# Digest (带 JSON 输出，避免编码问题)
powershell.exe -NoProfile -Command "& python3 '${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py' digest --json --start 2026-06-26"

# Flash
powershell.exe -NoProfile -Command "& python3 '${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py' flash --start '2026-06-26 00:00:00' --end '2026-06-26 23:59:59' --json"

# Search
powershell.exe -NoProfile -Command "& python3 '${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py' search --keyword '美联储' --json"
```

### Path C: 临时文件中转 (通用方案)

```bash
# 先输出 JSON 到临时文件，再用 Read 工具读取
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fetch_news/scripts/fetch_news.py digest --json > /tmp/news_digest.json
# 然后用 Read 工具读取 /tmp/news_digest.json
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

**仅在鉴权失败时引导用户配置**。命令返回 exit code 2 或 stderr 出现 "missing API key" 时，提示用户：

```
需要配置 TradeHub API Key 才能使用此功能。

1. 登录 TradeHub Web → Avatar → Settings → "API Key" 卡片生成 key
2. 两种配置方式（任选其一）：

   方式1 - 环境变量：
   export TRADEHUB_API_KEY=th_xxx

   方式2 - 文件（推荐持久化）：
   echo "th_xxx" > skills/fetch_news/TRADEHUB_API_KEY
```

**文件位置说明**：脚本会自动从 `skills/fetch_news/TRADEHUB_API_KEY` 读取（相对路径，基于脚本安装位置，通常是 `~/.claude/skills/fetch_news/TRADEHUB_API_KEY`）。

**🔒 大模型注意事项**：
- 不要读取或显示 `TRADEHUB_API_KEY` 文件内容
- 不要在对话中询问用户 API Key 内容
- 脚本会自动读取配置，失败时再提示用户

## Tips for the Agent

- **Prefer `--json` mode** (`--json` flag) when you want to programmatically inspect / filter / reformat the data yourself. Human-readable mode is for direct user display.
- **Time zone**: `start_time` / `end_time` are Asia/Shanghai. The server and CLS use this zone. The user's local time may differ — convert before querying.
- **`start_time` is required for flash** but optional for digest. Don't forget it.
- **`page_size` caps**: flash=5000, digest=180, weekly=60, search=100. For "today's news" flash with `page_size=500` is usually enough.
- **Digest `summary` is full markdown** — render it as markdown when displaying to the user.
- **Search returns CLS-formatted items** (different shape from flash). Don't merge them blindly.
- **Rate limiting**: there is none on the REST side, but CLS search (502s) has its own anti-crawl. If search returns 502, fall back to flash with a keyword filter.

## Windows 编码 (🔥 调用前必读)

**问题**：Windows Git Bash / cmd 默认非 UTF-8，中文输出会乱码。

**推荐方案（按优先级）**：

1. **PowerShell 调用** - 正确处理 UTF-8
   ```powershell
   powershell.exe -NoProfile -Command "python3 .../fetch_news.py digest --json"
   ```

2. **临时文件中转** - 先输出 JSON 文件，再用 Read 工具读取
   ```bash
   python3 .../fetch_news.py digest --json > /tmp/digest.json
   # 然后 Read 工具读取 /tmp/digest.json
   ```

3. **设置环境变量** - 仅当使用 Git Bash 时
   ```bash
   PYTHONUTF8=1 python3 .../fetch_news.py digest --json
   ```

**大模型调用建议**：优先使用 PowerShell 方式，输出用 `--json` 模式避免终端编码问题。

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
