---
name: fetch_news
description: 查询 TradeHub 新闻数据库——财联社实时快讯、每日要闻简报、每周投研简报。当用户想看财经新闻、市场动态、每日/每周新闻摘要，或按关键词检索历史新闻时使用。触发词：财经新闻 / 市场动态 / 今日要闻 / 昨天新闻 / 财联社快讯 / 简报 / 周报 / 搜索新闻 / news / digest / newsflash。
---

# 获取财经新闻（TradeHub）

通过 **TradeHub news REST API** 获取：财联社（cls.cn）实时快讯 + AI 生成的每日 / 每周简报。

## 四个操作

| 命令 | 端点 | 用途 |
|------|------|------|
| `flash` | `/api/v1/news/flash` | 实时快讯（按时间范围 + 关键词过滤） |
| `digest` | `/api/v1/news/digest` | 每日要闻简报（Claude 生成的 markdown） |
| `weekly` | `/api/v1/news/weekly` | 每周投研简报（≥5 个日级简报聚合，允许缺 2 天） |
| `search` | `/api/v1/news/search` | 关键词搜索（走财联社搜索引擎） |

## 何时使用

用户问：最近财经新闻 / 市场动态、每日要闻简报、某主题或个股新闻、"今天/昨天市场发生了什么"、提到 财联社 / 快讯 / 要闻 / 简报 / 周报。

**不适用**：股价 K 线（用行情类 skill）、通用网络搜索（仅覆盖 TradeHub 的 CLS 频道）、非财经新闻。

## 调用约定

**直接执行命令，不要预检查配置**：不要用 Read 检查 key 文件、不要提前询问或检查环境变量。脚本会自动读取配置，**失败时再排查**（见「鉴权」一节）。

## 用法

```bash
# 今日快讯
python3 ${SKILL_ROOT}/scripts/fetch_news.py flash \
  --start "2026-06-28 00:00:00" --end "2026-06-28 23:59:59" --json

# 最近 30 天简报（默认）
python3 ${SKILL_ROOT}/scripts/fetch_news.py digest --json

# 指定日期简报
python3 ${SKILL_ROOT}/scripts/fetch_news.py digest --start 2026-06-27 --end 2026-06-27 --json

# 关键词搜索
python3 ${SKILL_ROOT}/scripts/fetch_news.py search --keyword "美联储" --json

# 最近 90 天周报（默认）
python3 ${SKILL_ROOT}/scripts/fetch_news.py weekly --json
```

### 参数

| 命令 | 必需 / 常用参数 |
|------|----------------|
| `flash` | `--start`（必需，'YYYY-MM-DD HH:mm:SS'）、`--end`、`--keyword`、`--page-size`(≤5000) |
| `digest` | `--start`、`--end`（YYYY-MM-DD）、`--full`（显示完整内容）、`--page-size`(≤180) |
| `weekly` | `--start`、`--end`、`--full`、`--page-size`(≤60) |
| `search` | `--keyword`（必需）、`--max-count`(≤100)、`--last-time` |

**通用 flag**：

- `--json` — **始终加**，输出 UTF-8 JSON，避免 Windows 编码问题
- `--url` — 覆盖服务器地址（默认 `https://tradehub.niotech.cc`，或读 `TRADEHUB_URL` 环境变量）
- `--page` — 页码

## 返回字段

- **flash**：`items[].{id, title, content, ctime(unix 秒, Asia/Shanghai), author, subjects[]}`、`total`
- **digest**：`items[].{digest_date, summary(完整 markdown), news_count, status}` —— `summary` 直接按 markdown 渲染
- **weekly**：`items[].{week_start_date(周一), week_end_date, day_count(5~7), summary(8 段二级标题), news_count, status}` —— 部分周（`day_count<7`）会在 summary 标注缺失日期，不臆测
- **search**：`list[].{title, content, ctime}`、`scanned`、`pages_fetched` —— `title/content` 可能含 `<em>` 高亮标签，自行剥离；服务端不保证严格截断 `max_count`

## 鉴权

所有请求带 `Authorization: Bearer th_xxx`（`th_` 前缀的 API Key）。脚本自动从 **环境变量 `TRADEHUB_API_KEY`** 或 **skill 根目录的 `TRADEHUB_API_KEY` 文件**读取。

**鉴权失败（exit code 2 / stderr 出现 "missing API key"）时，提示用户配置**：

```
需要配置 TradeHub API Key：
1. 登录 TradeHub Web → 头像 → Settings → "API Key" 生成
2. 二选一：
   - 环境变量：export TRADEHUB_API_KEY=th_xxx
   - 文件（推荐持久化）：把 th_xxx 写入 skills/fetch_news/TRADEHUB_API_KEY
```

其它错误码：`401` key 无效 / `422` 缺参数 / `502` 财联社上游反爬（仅 search）。

## Agent 提示

- 时区：`start`/`end` 均为 Asia/Shanghai，按用户本地时间换算后再查
- `flash` 必须传 `--start`；今日快讯 `--page-size 500` 通常够
- `search` 返回的是 CLS 格式（与 flash 不同），不要混用；若 search 返回 502，改用 `flash --keyword`
- **不要读取或回显 key 文件内容**，脚本会自动读取

