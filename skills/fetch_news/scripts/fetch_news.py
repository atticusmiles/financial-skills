#!/usr/bin/env python3
"""TradeHub news API CLI.

封装四个 news 工具:
  - list_news_flash   → flash
  - list_news_digest  → digest
  - list_news_weekly  → weekly
  - search_news       → search

依赖: 仅 Python 3 标准库 (urllib + json + argparse).
鉴权: Authorization: Bearer th_xxx (TradeHub API Key).

使用示例:

  # 列出今日快讯
  python3 fetch_news.py flash \\
    --start "2026-06-22 00:00:00" --end "2026-06-22 23:59:59" \\
    --api-key th_xxx

  # 列出最近 30 天简报
  python3 fetch_news.py digest --api-key th_xxx

  # 列出最近 90 天周报
  python3 fetch_news.py weekly --api-key th_xxx

  # 关键词搜索
  python3 fetch_news.py search --keyword "美联储" --api-key th_xxx
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# 仅当 stdout/stderr 被管道/重定向捕获时（非 tty）强制 UTF-8，
# 这样 subprocess 捕获拿到稳定字节；直连控制台时保持系统编码（如 Windows
# cmd 的 cp936），避免按 UTF-8 输出却被控制台按 cp936 显示而乱码。
for _stream in (sys.stdout, sys.stderr):
    if not _stream.isatty() and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


DEFAULT_URL = "https://tradehub-api.niotech.cc"
DEFAULT_TIMEOUT = 30

# skill 目录下的 API Key 文件 (脚本在 scripts/, 上一级是 skill 根)
_API_KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "TRADEHUB_API_KEY")

# 剥离 CLS 搜索结果里的 <em>...</em> 高亮标签
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _get_base_url() -> str:
    return os.environ.get("TRADEHUB_URL", DEFAULT_URL).rstrip("/")


def _read_api_key_file() -> str:
    """从 skill 目录的 TRADEHUB_API_KEY 文件读取 key. 失败返回空串.

    文件格式: 单行, 可选尾换行. 例如:
        th_MTWAr_xxxxxxxxxxxxxxxxxxxxxxxxxx
    """
    try:
        with open(_API_KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except (OSError, IOError):
        return None


def _resolve_api_key(explicit: str | None) -> str:
    """解析 + 验证 API key (不退出). 返回空串表示无效.

    优先级 (高 → 低):
      1. --api-key flag (explicit)
      2. TRADEHUB_API_KEY env var
      3. skill 目录下的 TRADEHUB_API_KEY 文件
    """
    raw = explicit or os.environ.get("TRADEHUB_API_KEY", "") or _read_api_key_file() or ""
    if not raw:
        return ""
    key = raw.strip()
    if not key.startswith("th_"):
        return ""
    return key


def _fetch_api_key(args: argparse.Namespace) -> str:
    """统一从 args / env / file 解析 API key, 失败时 sys.exit(2)."""
    # argparse 父子 parser 陷阱: 顶层传的 --api-key 可能被子命令的 default None 覆盖.
    # _resolve_api_key 内部已 fallback 到 env / file.
    explicit = getattr(args, "api_key", None)
    key = _resolve_api_key(explicit)
    if not key:
        if explicit and not explicit.startswith("th_"):
            sys.stderr.write(
                f"ERROR: API key must start with 'th_' (got {explicit[:6]}...). "
                "TradeHub API keys have the format th_<5 chars>_<27 chars>.\n"
            )
        else:
            sys.stderr.write(
                "ERROR: missing API key. Supply via --api-key flag, "
                "TRADEHUB_API_KEY env var, or skills/fetch_news/TRADEHUB_API_KEY file.\n"
            )
        sys.exit(2)
    return key


def _resolve_url(args: argparse.Namespace) -> str:
    """统一从 args / env 解析 base URL."""
    explicit = getattr(args, "url", None)
    if explicit:
        return explicit.rstrip("/")
    return _get_base_url()


def _resolve_json(args: argparse.Namespace) -> bool:
    """统一从 args 取 --json flag (兼容父子 parser)."""
    return bool(getattr(args, "json", False))


def _request(base_url: str, api_key: str, path: str, params: dict | None = None) -> dict:
    """发起 GET 请求, 返回解析后的 JSON dict.

    Raises SystemExit(1) on network / HTTP error.
    """
    qs = urllib.parse.urlencode(params or {}, doseq=True)
    url = f"{base_url}{path}" + (f"?{qs}" if qs else "")

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        sys.stderr.write(f"HTTP {e.code} from {url}\n  body: {err_body[:500]}\n")
        sys.exit(1)
    except urllib.error.URLError as e:
        sys.stderr.write(f"network error: {e.reason}\n  url: {url}\n")
        sys.exit(1)

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        sys.stderr.write(f"invalid JSON response (first 500 chars):\n{body[:500]}\n")
        sys.exit(1)


def _ts_to_str(ts: int | float | None) -> str:
    """unix 秒 → 'YYYY-MM-DD HH:mm:ss' (Asia/Shanghai = UTC+8)."""
    if not ts:
        return ""
    tz = dt.timezone(dt.timedelta(hours=8))
    return dt.datetime.fromtimestamp(int(ts), tz=tz).strftime("%Y-%m-%d %H:%M:%S")


def _strip_html(s: str) -> str:
    """剥离 CLS 搜索结果里的 <em>...</em> 等标签, 给人类可读模式用."""
    return _HTML_TAG_RE.sub("", s or "")


def _print_json(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ============================== commands ==============================

def cmd_flash(args: argparse.Namespace) -> int:
    """list_news_flash: 按时间范围列出财联社快讯."""
    if not args.start:
        sys.stderr.write("ERROR: --start is required (format: 'YYYY-MM-DD HH:mm:SS')\n")
        return 2

    params = {
        "start_time": args.start,
        "end_time": args.end or "",
        "keyword": args.keyword or "",
        "page": args.page,
        "page_size": args.page_size,
    }
    # 不传空 end_time (服务器会自动用 now)
    if not params["end_time"]:
        del params["end_time"]
    if not params["keyword"]:
        del params["keyword"]

    data = _request(
        _resolve_url(args),
        _fetch_api_key(args),
        "/api/v1/news/flash",
        params,
    )

    if _resolve_json(args):
        _print_json(data)
        return 0

    # 人类可读摘要
    items = data.get("items", [])
    print(f"# 财联社快讯 (共 {data.get('total', 0)} 条, 当前页 {len(items)} 条)")
    if args.keyword:
        print(f"# 过滤关键词: {args.keyword}")
    print()
    for it in items:
        ctime_str = _ts_to_str(it.get("ctime"))
        title = (it.get("title") or "").strip()
        content = (it.get("content") or "").strip()
        author = it.get("author") or "财联社"
        print(f"## [{ctime_str}] {title or '(无标题)'}")
        print(f"_{author}_\n")
        print(content)
        print("\n---\n")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    """list_news_digest: 列出每日要闻简报 (Claude 生成)."""
    params = {
        "page": args.page,
        "page_size": args.page_size,
    }
    if args.start:
        params["start_date"] = args.start
    if args.end:
        params["end_date"] = args.end

    data = _request(
        _resolve_url(args),
        _fetch_api_key(args),
        "/api/v1/news/digest",
        params,
    )

    if _resolve_json(args):
        _print_json(data)
        return 0

    items = data.get("items", [])
    print(f"# 每日要闻简报 (共 {data.get('total', 0)} 篇, 当前页 {len(items)} 篇)")
    print()
    if not items:
        print("_暂无简报_\n")
        return 0

    for it in items:
        date = it.get("digest_date", "?")
        status = it.get("status", "?")
        news_count = it.get("news_count", 0)
        print(f"## {date}  (status: {status}, news_count: {news_count})")
        if status == "success":
            summary = (it.get("summary") or "").strip()
            if args.full:
                print()
                print(summary)
            else:
                # 只显示前 500 字符作为预览
                preview = summary[:500]
                if len(summary) > 500:
                    preview += f"\n\n... (余 {len(summary) - 500} 字, 加 --full 展开)"
                print()
                print(preview)
        else:
            err = it.get("error_message") or ""
            print(f"  _生成失败: {err}_")
        print("\n---\n")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """search_news: 关键词搜索 (走财联社搜索)."""


def cmd_weekly(args: argparse.Namespace) -> int:
    """list_news_weekly: 列出每周投研简报 (基于 7 个日级简报 LLM 二次聚合)."""
    params = {
        "page": args.page,
        "page_size": args.page_size,
    }
    if args.start:
        params["start_date"] = args.start
    if args.end:
        params["end_date"] = args.end

    data = _request(
        _resolve_url(args),
        _fetch_api_key(args),
        "/api/v1/news/weekly",
        params,
    )

    if _resolve_json(args):
        _print_json(data)
        return 0

    items = data.get("items", [])
    print(f"# 每周投研简报 (共 {data.get('total', 0)} 篇, 当前页 {len(items)} 篇)")
    print()
    if not items:
        print("_暂无周报_\n")
        return 0

    for it in items:
        ws = it.get("week_start_date", "?")
        we = it.get("week_end_date", "?")
        status = it.get("status", "?")
        day_count = it.get("day_count", 0)
        news_count = it.get("news_count", 0)
        print(f"## {ws} ~ {we}  (status: {status}, {day_count}/7 天, {news_count} 条快讯)")
        if status == "success":
            summary = (it.get("summary") or "").strip()
            if args.full:
                print()
                print(summary)
            else:
                preview = summary[:500]
                if len(summary) > 500:
                    preview += f"\n\n... (余 {len(summary) - 500} 字, 加 --full 展开)"
                print()
                print(preview)
        else:
            err = it.get("error_message") or ""
            print(f"  _生成失败: {err}_")
        print("\n---\n")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """search_news: 关键词搜索 (走财联社搜索)."""
    params = {
        "keyword": args.keyword or "",
        "last_time": args.last_time,
        "max_count": args.max_count,
    }
    data = _request(
        _resolve_url(args),
        _fetch_api_key(args),
        "/api/v1/news/search",
        params,
    )

    if _resolve_json(args):
        _print_json(data)
        return 0

    items = data.get("list", [])
    # 服务端 max_count 不保证严格, skill 端按用户传的 --max-count 截断显示
    if args.max_count and len(items) > args.max_count:
        items = items[:args.max_count]
    print(f"# 财联社搜索 (scanned {data.get('scanned', 0)} 页, "
          f"返回 {len(items)} 条"
          + (f", 服务端实际 {len(data.get('list', []))} 条已截断" if len(items) < len(data.get('list', [])) else "")
          + ")")
    if args.keyword:
        print(f"# 关键词: {args.keyword}")
    print()
    for it in items:
        ctime_str = _ts_to_str(it.get("ctime"))
        title = _strip_html((it.get("title") or "").strip())
        content = _strip_html((it.get("content") or "").strip())
        print(f"## [{ctime_str}] {title or '(无标题)'}")
        print(content)
        print("\n---\n")
    return 0


# ============================== arg parsing ==============================

def _build_parser() -> argparse.ArgumentParser:
    """构建 CLI parser.

    设计: 把 --api-key / --url / --json 同时挂到顶层和每个子命令,
    让 `flash --api-key xxx` 和 `--api-key xxx flash` 都能 work.
    """
    common = argparse.ArgumentParser(add_help=False)
    # default=SUPPRESS: 未传该 flag 时, namespace 中不创建对应属性,
    # 避免子 parser 的 default 覆盖父 parser 已设置的值.
    common.add_argument("--url", default=argparse.SUPPRESS,
                        help=f"TradeHub server URL (default: {DEFAULT_URL} or $TRADEHUB_URL)")
    common.add_argument("--api-key", default=argparse.SUPPRESS,
                        help="API key th_xxx (or $TRADEHUB_API_KEY env, or skills/fetch_news/TRADEHUB_API_KEY file)")
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="emit raw JSON instead of human-readable summary")

    parser = argparse.ArgumentParser(
        prog="fetch_news",
        description="Query TradeHub news REST API (flash / digest / weekly / search).",
        parents=[common],
    )

    sub = parser.add_subparsers(dest="cmd", required=True, metavar="{flash|digest|weekly|search}")

    p_flash = sub.add_parser("flash", help="list_news_flash: 按时间范围列快讯", parents=[common])
    p_flash.add_argument("--start", required=False,
                         help="'YYYY-MM-DD HH:mm:SS' Asia/Shanghai (required)")
    p_flash.add_argument("--end", help="'YYYY-MM-DD HH:mm:SS' (default: now)")
    p_flash.add_argument("--keyword", help="在 title+content 上模糊匹配")
    p_flash.add_argument("--page", type=int, default=1)
    p_flash.add_argument("--page-size", type=int, default=500,
                         help="max 5000 (default 500)")
    p_flash.set_defaults(func=cmd_flash)

    p_digest = sub.add_parser("digest", help="list_news_digest: 每日要闻简报", parents=[common])
    p_digest.add_argument("--start", help="YYYY-MM-DD (default: end_date-29)")
    p_digest.add_argument("--end", help="YYYY-MM-DD (default: today-1)")
    p_digest.add_argument("--page", type=int, default=1)
    p_digest.add_argument("--page-size", type=int, default=60, help="max 180")
    p_digest.add_argument("--full", action="store_true",
                          help="显示完整 summary (默认只显示前 500 字符)")
    p_digest.set_defaults(func=cmd_digest)

    p_weekly = sub.add_parser("weekly", help="list_news_weekly: 每周投研简报", parents=[common])
    p_weekly.add_argument("--start", help="YYYY-MM-DD (default: end_date-90)")
    p_weekly.add_argument("--end", help="YYYY-MM-DD (default: today)")
    p_weekly.add_argument("--page", type=int, default=1)
    p_weekly.add_argument("--page-size", type=int, default=20, help="max 60")
    p_weekly.add_argument("--full", action="store_true",
                          help="显示完整 summary (默认只显示前 500 字符)")
    p_weekly.set_defaults(func=cmd_weekly)

    p_search = sub.add_parser("search", help="search_news: 财联社关键词搜索", parents=[common])
    p_search.add_argument("--keyword", default="", help="搜索词")
    p_search.add_argument("--last-time", type=int, default=0,
                          help="unix ts, 0 = 最新")
    p_search.add_argument("--max-count", type=int, default=20,
                          help="1-100 (default 20)")
    p_search.set_defaults(func=cmd_search)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    # 提前验证 API key 和 URL, 统一错误退出 (避免每个 cmd 重复处理)
    _fetch_api_key(args)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
