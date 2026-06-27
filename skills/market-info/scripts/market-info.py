#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""market-info — A股实时市场行情数据工具

用法: python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-info/scripts/market-info.py '<JSON>'

所有行动公用一个 JSON 入参，按 stdout 输出 JSON 结果。
成功: {"code":0, "message":"ok", "data":...}
失败: {"error":"...", "exit_code":1}
"""

import json
import os
import sys
import time
import random
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# 仅当 stdout/stderr 被管道/重定向捕获时（非 tty）强制 UTF-8，让 subprocess
# 拿到稳定字节；直连控制台时保持系统编码，避免 Windows cmd 显示乱码。
for _stream in (sys.stdout, sys.stderr):
    if not _stream.isatty() and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

try:
    import requests
except ImportError:
    print(json.dumps({"error": "pip install requests first", "exit_code": 1}, ensure_ascii=False))
    raise SystemExit(1)

# ── 全局配置 ──────────────────────────────────────────────
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# 东财限流
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = float(os.environ.get("MARKET_EM_INTERVAL", "1.0"))
_em_last = [0.0]

# 北向缓存路径
_NORTHBOUND_CACHE = Path.home() / ".a-stock-market" / "northbound_daily.csv"

# ── 工具函数 ──────────────────────────────────────────────

def die(msg: str, exit_code: int = 1):
    print(json.dumps({"error": msg, "exit_code": exit_code}, ensure_ascii=False))
    raise SystemExit(exit_code)

def build_result(data, item_count=None):
    if item_count is None:
        if isinstance(data, list):
            item_count = len(data)
        elif isinstance(data, dict):
            item_count = data.get("total", len(data))
        else:
            item_count = 1
    return {"code": 0, "message": "ok", "data": data, "item_count": item_count}

def parse_payload():
    if len(sys.argv) < 2:
        print_usage()
        raise SystemExit(1)
    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        die("Invalid JSON payload")
    if not isinstance(payload, dict):
        die("Payload must be a JSON object")
    return payload

def print_usage():
    print(json.dumps({
        "skill": "market-info",
        "actions": [
            "doctor",
            "quote", "kline_baidu", "hot_stocks", "northbound",
            "concept_blocks", "fund_flow_minute", "dragon_tiger",
            "daily_dragon_tiger", "lockup_expiry", "industry_compare",
            "margin_trading", "block_trade", "holders", "dividend",
            "fund_flow_120d",
        ],
        "example": json.dumps({"action": "quote", "codes": ["600519"]}),
    }, ensure_ascii=False, indent=2))

def em_get(url: str, params: dict | None = None, headers: dict | None = None,
           timeout: int = 15):
    """东财统一限流 GET。"""
    wait = EM_MIN_INTERVAL - (time.time() - _em_last[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        resp = EM_SESSION.get(url, params=params, headers=headers, timeout=timeout)
        return resp
    finally:
        _em_last[0] = time.time()

def em_datacenter(report_name: str, filter_str: str = "", page_size: int = 50,
                  sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
    """东财 datacenter 统一查询。"""
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": report_name, "columns": "ALL",
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    resp = em_get(url, params=params, timeout=15)
    d = resp.json()
    data = d.get("result") or {}
    return data.get("data") or []

def normalize_code(code: str) -> str:
    """归一化为纯6位数字。"""
    code = code.strip().upper()
    for prefix in ("SH", "SZ", "BJ"):
        if code.startswith(prefix):
            code = code[len(prefix):]
    if "." in code:
        code = code.split(".")[0]
    return code

def market_code(code: str) -> int:
    """6位代码 → 东财 market code: 1=沪, 0=深/京。"""
    return 1 if code.startswith("6") else 0

# ── 行情层 ────────────────────────────────────────────────

def action_quote(p: dict):
    """腾讯财经实时行情（PE/PB/市值/换手率）。"""
    codes = p.get("codes", p.get("code", []))
    if isinstance(codes, str):
        codes = [codes]
    if not codes or not isinstance(codes, list):
        die("codes is required (list of 6-digit tickers)")

    prefixed = []
    for c in codes:
        c = normalize_code(c)
        if c.startswith(("6", "9")):
            prefixed.append(f"sh{c}")
        elif c.startswith("8"):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")

    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        die(f"Tencent quote request failed: {e}")
    data = resp.read().decode("gbk")

    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name":         vals[1],
            "price":        float(vals[3]) if vals[3] else 0,
            "last_close":   float(vals[4]) if vals[4] else 0,
            "open":         float(vals[5]) if vals[5] else 0,
            "change_pct":   float(vals[32]) if vals[32] else 0,
            "high":         float(vals[33]) if vals[33] else 0,
            "low":          float(vals[34]) if vals[34] else 0,
            "amount_wan":   float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm":       float(vals[39]) if vals[39] else 0,
            "mcap_yi":      float(vals[44]) if vals[44] else 0,
            "float_mcap_yi":float(vals[45]) if vals[45] else 0,
            "pb":           float(vals[46]) if vals[46] else 0,
            "limit_up":     float(vals[47]) if vals[47] else 0,
            "limit_down":   float(vals[48]) if vals[48] else 0,
            "pe_static":    float(vals[52]) if vals[52] else 0,
        }
    return build_result(result)

def action_kline_baidu(p: dict):
    """百度股市通K线（带MA均价）。"""
    code = normalize_code(p.get("code", ""))
    if not code:
        die("code is required")
    start_time = p.get("start_time", "")

    url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
    params = {
        "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
        "isFutures": "false", "isStock": "true", "newFormat": "1",
        "group": "quotation_kline_ab", "finClientType": "pc",
        "code": code, "start_time": start_time, "ktype": "1",
    }
    headers = {
        "User-Agent": UA,
        "Accept": "application/vnd.finance-web.v1+json",
        "Origin": "https://gushitong.baidu.com",
        "Referer": "https://gushitong.baidu.com/",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        d = resp.json()
    except Exception as e:
        die(f"Baidu K-line request failed: {e}")

    rc = str(d.get("ResultCode", -1))
    if rc != "0":
        return build_result({"keys": [], "rows": [], "error": f"ResultCode={rc}"}, 0)

    result = d.get("Result", {})
    if isinstance(result, list) or not result:
        return build_result({"keys": [], "rows": [], "error": "empty result"}, 0)

    md = result.get("newMarketData", {})
    keys = md.get("keys", [])
    rows = md.get("marketData", "").split(";") if md.get("marketData") else []

    # 解析每行数据
    parsed_rows = []
    for row in rows:
        if row.strip():
            parsed_rows.append(row.split(","))

    return build_result({"keys": keys, "rows": parsed_rows, "row_count": len(parsed_rows)})

# ── 信号层 ────────────────────────────────────────────────

def action_hot_stocks(p: dict):
    """同花顺当日强势股+题材归因。"""
    date = p.get("date", datetime.now().strftime("%Y-%m-%d"))
    url = (f"http://zx.10jqka.com.cn/event/api/getharden/"
           f"date/{date}/orderby/date/orderway/desc/charset/GBK/")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
    except Exception as e:
        die(f"THS hot stocks request failed: {e}")

    if data.get("errocode", 0) != 0:
        die(data.get("errormsg", "Unknown THS error"))

    rows = data.get("data") or []
    items = []
    for r in rows:
        items.append({
            "code": r.get("code", ""),
            "name": r.get("name", ""),
            "reason": r.get("reason", ""),
            "close": r.get("close", 0),
            "change_pct": r.get("zhangfu", 0),
            "turnover_pct": r.get("huanshou", 0),
            "volume": r.get("chengjiaoliang", 0),
            "amount": r.get("chengjiaoe", 0),
            "dde_net": r.get("ddejingliang", 0),
            "market": r.get("market", ""),
        })
    return build_result(items)

def action_northbound(p: dict):
    """同花顺北向资金（实时分钟+历史缓存）。"""
    mode = p.get("mode", "realtime")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/117.0.0.0 Safari/537.36",
        "Host": "data.hexin.cn",
        "Referer": "https://data.hexin.cn/",
    }

    if mode == "history":
        n = p.get("days", 20)
        if _NORTHBOUND_CACHE.exists():
            rows = []
            for line in _NORTHBOUND_CACHE.read_text(encoding="utf-8").strip().split("\n")[1:]:
                parts = line.split(",")
                if len(parts) == 3:
                    rows.append({"date": parts[0], "hgt_yi": float(parts[1]), "sgt_yi": float(parts[2])})
            return build_result(rows[-n:])
        return build_result([])

    try:
        resp = requests.get("https://data.hexin.cn/market/hsgtApi/method/dayChart/",
                            headers=headers, timeout=10)
        d = resp.json()
    except Exception as e:
        die(f"Northbound request failed: {e}")

    times = d.get("time", [])
    hgt = d.get("hgt", [])
    sgt = d.get("sgt", [])
    n = len(times)

    items = []
    for i in range(n):
        items.append({
            "time": times[i],
            "hgt_yi": hgt[i] if i < len(hgt) else None,
            "sgt_yi": sgt[i] if i < len(sgt) else None,
        })

    # 自动缓存收盘数据
    if items:
        last = [x for x in items if x["hgt_yi"] is not None]
        if last:
            l = last[-1]
            _NORTHBOUND_CACHE.parent.mkdir(parents=True, exist_ok=True)
            cur_date = datetime.now().strftime("%Y-%m-%d")
            existing = {}
            if _NORTHBOUND_CACHE.exists():
                for line in _NORTHBOUND_CACHE.read_text(encoding="utf-8").strip().split("\n")[1:]:
                    parts = line.split(",")
                    if len(parts) == 3:
                        existing[parts[0]] = line
            existing[cur_date] = f"{cur_date},{l['hgt_yi']},{l['sgt_yi']}"
            with open(_NORTHBOUND_CACHE, "w", encoding="utf-8") as f:
                f.write("date,hgt,sgt\n")
                for d_key in sorted(existing.keys()):
                    f.write(existing[d_key] + "\n")

    return build_result(items)

def action_concept_blocks(p: dict):
    """东财个股板块/概念归属。"""
    code = normalize_code(p.get("code", ""))
    if not code:
        die("code is required")
    mk = market_code(code)
    params = {
        "fltt": "2", "invt": "2",
        "secid": f"{mk}.{code}",
        "spt": "3", "pi": "0", "pz": "200", "po": "1",
        "fields": "f12,f14,f3,f128",
    }
    headers = {"User-Agent": UA, "Referer": "https://quote.eastmoney.com/"}
    try:
        resp = em_get("https://push2.eastmoney.com/api/qt/slist/get",
                      params=params, headers=headers, timeout=15)
        d = resp.json()
    except Exception as e:
        die(f"Concept blocks request failed: {e}")

    diff = (d.get("data") or {}).get("diff") or {}
    items = list(diff.values()) if isinstance(diff, dict) else diff
    boards = []
    for it in items:
        boards.append({
            "name": it.get("f14", ""),
            "code": it.get("f12", ""),
            "change_pct": it.get("f3", ""),
            "lead_stock": it.get("f128", ""),
        })
    return build_result({"boards": boards, "concept_tags": [b["name"] for b in boards], "total": len(boards)})

def action_fund_flow_minute(p: dict):
    """东财个股资金流向（分钟级）。"""
    code = normalize_code(p.get("code", ""))
    if not code:
        die("code is required")
    secid = f"{market_code(code)}.{code}"
    try:
        resp = em_get(
            "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get",
            params={
                "secid": secid, "klt": 1,
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
            },
            headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/",
                     "Origin": "https://quote.eastmoney.com"},
            timeout=10
        )
        d = resp.json()
    except Exception as e:
        die(f"Fund flow minute request failed: {e}")

    items = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            items.append({
                "time": parts[0],
                "main_net": float(parts[1]),
                "small_net": float(parts[2]),
                "mid_net": float(parts[3]),
                "large_net": float(parts[4]),
                "super_net": float(parts[5]),
            })
    return build_result(items)

def action_dragon_tiger(p: dict):
    """龙虎榜（个股上榜记录+席位）。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    trade_date = p.get("date", datetime.now().strftime("%Y-%m-%d"))
    look_back = p.get("look_back", 30)
    start = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back)
    start_str = start.strftime("%Y-%m-%d")

    records = em_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        f"(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')(SECURITY_CODE=\"{code}\")",
        page_size=50,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    items = []
    for row in records:
        items.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "reason": row.get("EXPLANATION", ""),
            "net_buy_wan": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
            "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
            "close": row.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
        })

    return build_result({"records": items, "total": len(items)})

def action_daily_dragon_tiger(p: dict):
    """全市场龙虎榜（每日汇总）。"""
    trade_date = p.get("date", datetime.now().strftime("%Y-%m-%d"))
    min_net = p.get("min_net_buy")

    data = em_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        page_size=500,
        sort_columns="BILLBOARD_NET_AMT", sort_types="-1",
    )

    actual_date = str(data[0].get("TRADE_DATE", ""))[:10] if data else trade_date
    items = []
    for row in data:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
        if min_net is not None and net_buy < min_net:
            continue
        items.append({
            "code": row.get("SECURITY_CODE", ""),
            "name": row.get("SECURITY_NAME_ABBR", ""),
            "reason": row.get("EXPLANATION", ""),
            "close": row.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
            "net_buy_wan": round(net_buy, 1),
            "buy_wan": round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000, 1),
            "sell_wan": round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000, 1),
            "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
        })
    return build_result({"date": actual_date, "stocks": items, "total": len(items)})

def action_lockup_expiry(p: dict):
    """限售解禁日历。"""
    code = normalize_code(p.get("code", ""))
    if not code:
        die("code is required")
    trade_date = p.get("date", datetime.now().strftime("%Y-%m-%d"))
    forward_days = p.get("forward_days", 90)

    # 历史解禁
    hist = em_datacenter(
        "RPT_LIFT_STAGE",
        f'(SECURITY_CODE="{code}")',
        page_size=15,
        sort_columns="FREE_DATE", sort_types="-1",
    )
    history = []
    for row in hist:
        history.append({
            "date": str(row.get("FREE_DATE", ""))[:10],
            "type": row.get("LIMITED_STOCK_TYPE", ""),
            "shares": row.get("FREE_SHARES_NUM", 0),
            "ratio": row.get("FREE_RATIO", 0),
        })

    # 未来待解禁
    end_date = datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)
    end_str = end_date.strftime("%Y-%m-%d")
    upcoming_data = em_datacenter(
        "RPT_LIFT_STAGE",
        f'(SECURITY_CODE="{code}")(FREE_DATE>=\'{trade_date}\')(FREE_DATE<=\'{end_str}\')',
        page_size=20,
        sort_columns="FREE_DATE", sort_types="1",
    )
    upcoming = []
    for row in upcoming_data:
        upcoming.append({
            "date": str(row.get("FREE_DATE", ""))[:10],
            "type": row.get("LIMITED_STOCK_TYPE", ""),
            "shares": row.get("FREE_SHARES_NUM", 0),
            "ratio": row.get("FREE_RATIO", 0),
        })

    return build_result({"history": history, "upcoming": upcoming})

def action_industry_compare(p: dict):
    """行业板块排名。"""
    top_n = p.get("top_n", 20)
    try:
        resp = em_get(
            "https://push2.eastmoney.com/api/qt/clist/get",
            params={
                "pn": "1", "pz": "100", "po": "1", "np": "1",
                "fltt": "2", "invt": "2", "fs": "m:90+t:2",
                "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
            },
            headers={"User-Agent": UA}, timeout=15
        )
        d = resp.json()
    except Exception as e:
        die(f"Industry compare request failed: {e}")

    items = d.get("data", {}).get("diff", [])
    rows = []
    for i, item in enumerate(items):
        rows.append({
            "rank": i + 1,
            "name": item.get("f14", ""),
            "change_pct": item.get("f3", 0),
            "code": item.get("f12", ""),
            "up_count": item.get("f104", 0),
            "down_count": item.get("f105", 0),
            "leader": item.get("f140", ""),
            "leader_change": item.get("f136", 0),
        })

    return build_result({
        "top": rows[:top_n],
        "bottom": rows[-top_n:] if len(rows) > top_n else [],
        "total_industries": len(rows),
    })

# ── 资金面 ────────────────────────────────────────────────

def action_margin_trading(p: dict):
    """融资融券明细。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    page_size = p.get("size", 30)

    data = em_datacenter(
        "RPTA_WEB_RZRQ_GGMX",
        f'(SCODE="{code}")',
        page_size=page_size,
        sort_columns="DATE", sort_types="-1",
    )
    items = []
    for row in data:
        items.append({
            "date": str(row.get("DATE", ""))[:10],
            "rzye": row.get("RZYE", 0),
            "rzmre": row.get("RZMRE", 0),
            "rzche": row.get("RZCHE", 0),
            "rqye": row.get("RQYE", 0),
            "rqmcl": row.get("RQMCL", 0),
            "rqchl": row.get("RQCHL", 0),
            "rzrqye": row.get("RZRQYE", 0),
        })
    return build_result(items)

def action_block_trade(p: dict):
    """大宗交易记录。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    page_size = p.get("size", 20)

    data = em_datacenter(
        "RPT_DATA_BLOCKTRADE",
        f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="TRADE_DATE", sort_types="-1",
    )
    items = []
    for row in data:
        close = row.get("CLOSE_PRICE") or 0
        deal_price = row.get("DEAL_PRICE") or 0
        premium = ((deal_price / close - 1) * 100) if close else 0
        items.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "price": deal_price,
            "close": close,
            "premium_pct": round(premium, 2),
            "vol": row.get("DEAL_VOLUME", 0),
            "amount": row.get("DEAL_AMT", 0),
            "buyer": row.get("BUYER_NAME", ""),
            "seller": row.get("SELLER_NAME", ""),
        })
    return build_result(items)

def action_holders(p: dict):
    """股东户数变化。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    page_size = p.get("size", 10)

    data = em_datacenter(
        "RPT_HOLDERNUMLATEST",
        f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="END_DATE", sort_types="-1",
    )
    items = []
    for row in data:
        items.append({
            "date": str(row.get("END_DATE", ""))[:10],
            "holder_num": row.get("HOLDER_NUM", 0),
            "change_num": row.get("HOLDER_NUM_CHANGE", 0),
            "change_ratio": row.get("HOLDER_NUM_RATIO", 0),
            "avg_shares": row.get("AVG_FREE_SHARES", 0),
        })
    return build_result(items)

def action_dividend(p: dict):
    """分红送转历史。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    page_size = p.get("size", 20)

    data = em_datacenter(
        "RPT_SHAREBONUS_DET",
        f'(SECURITY_CODE="{code}")',
        page_size=page_size,
        sort_columns="EX_DIVIDEND_DATE", sort_types="-1",
    )
    items = []
    for row in data:
        items.append({
            "date": str(row.get("EX_DIVIDEND_DATE", ""))[:10],
            "bonus_rmb": row.get("PRETAX_BONUS_RMB", 0),
            "transfer_ratio": row.get("TRANSFER_RATIO", 0),
            "bonus_ratio": row.get("BONUS_RATIO", 0),
            "plan": row.get("ASSIGN_PROGRESS", ""),
        })
    return build_result(items)

def action_fund_flow_120d(p: dict):
    """个股资金流（120日日级）。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    mk = market_code(code)
    size = p.get("size", 120)

    try:
        resp = em_get(
            "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
            params={
                "secid": f"{mk}.{code}",
                "fields1": "f1,f2,f3,f7",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
                "lmt": str(size),
            },
            headers={"User-Agent": UA, "Referer": "https://quote.eastmoney.com/",
                     "Origin": "https://quote.eastmoney.com"},
            timeout=15
        )
        d = resp.json()
    except Exception as e:
        die(f"Fund flow 120d request failed: {e}")

    items = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 7:
            items.append({
                "date": parts[0],
                "main_net": float(parts[1]) if parts[1] != "-" else 0,
                "small_net": float(parts[2]) if parts[2] != "-" else 0,
                "mid_net": float(parts[3]) if parts[3] != "-" else 0,
                "large_net": float(parts[4]) if parts[4] != "-" else 0,
                "super_net": float(parts[5]) if parts[5] != "-" else 0,
            })
    return build_result(items)

# ── 主入口 ────────────────────────────────────────────────

def action_doctor(_payload):
    """环境自检：Python 版本、依赖、各数据源连通性、样本调用。"""
    checks = []

    # 1. Python 版本
    pv = sys.version_info
    py_ok = pv >= (3, 9)
    checks.append({
        "name": "python_version",
        "ok": py_ok,
        "detail": f"{pv.major}.{pv.minor}.{pv.micro}",
        "hint": "需要 Python 3.9+" if not py_ok else "",
    })

    # 2. requests 依赖
    try:
        import requests as _r
        checks.append({
            "name": "requests",
            "ok": True,
            "detail": getattr(_r, "__version__", "unknown"),
            "hint": "",
        })
    except ImportError:
        checks.append({
            "name": "requests",
            "ok": False,
            "detail": "missing",
            "hint": "运行: pip install requests",
        })

    # 3. 各数据源连通性（HEAD/GET 任一即可）
    endpoints = [
        ("tencent_quote", "https://qt.gtimg.cn/q=sh000001", "腾讯行情"),
        ("em_datacenter", "https://push2.eastmoney.com/api/qt/stock/get?secid=1.000001", "东财行情"),
    ]
    for key, url, label in endpoints:
        try:
            r = _r.get(url, timeout=8, headers={"User-Agent": UA}) if "requests" in sys.modules else None
            ok = bool(r and r.status_code < 500)
            checks.append({
                "name": key,
                "ok": ok,
                "detail": f"{label} HTTP {r.status_code if r else 'skipped'}",
                "hint": "" if ok else "网络/DNS 问题或源站暂时不可达，稍后重试",
            })
        except Exception as e:
            checks.append({
                "name": key,
                "ok": False,
                "detail": f"{label} {type(e).__name__}: {e}",
                "hint": "检查网络/防火墙/DNS",
            })

    # 4. 样本调用：腾讯 quote
    try:
        sample = action_quote({"codes": ["600519"]})
        sample_ok = sample.get("code") == 0 and "600519" in sample.get("data", {})
        checks.append({
            "name": "sample_quote",
            "ok": sample_ok,
            "detail": "600519 → " + str(sample.get("data", {}).get("600519", {}).get("name", "?")),
            "hint": "" if sample_ok else "样本调用失败，请检查网络",
        })
    except Exception as e:
        checks.append({
            "name": "sample_quote", "ok": False,
            "detail": f"{type(e).__name__}: {e}", "hint": "样本调用异常",
        })

    all_ok = all(c["ok"] for c in checks)
    return {
        "code": 0 if all_ok else 1,
        "message": "all checks passed" if all_ok else "some checks failed",
        "data": {
            "platform": sys.platform,
            "plugin_root": os.environ.get("CLAUDE_PLUGIN_ROOT", ""),
            "checks": checks,
            "next_step": "环境正常，可正常调用其它 action" if all_ok else "按 hint 修复后再调用其它 action",
        },
    }

ACTIONS = {
    "doctor":              action_doctor,
    "quote":               action_quote,
    "kline_baidu":         action_kline_baidu,
    "hot_stocks":          action_hot_stocks,
    "northbound":          action_northbound,
    "concept_blocks":      action_concept_blocks,
    "fund_flow_minute":    action_fund_flow_minute,
    "dragon_tiger":        action_dragon_tiger,
    "daily_dragon_tiger":  action_daily_dragon_tiger,
    "lockup_expiry":       action_lockup_expiry,
    "industry_compare":    action_industry_compare,
    "margin_trading":      action_margin_trading,
    "block_trade":         action_block_trade,
    "holders":             action_holders,
    "dividend":            action_dividend,
    "fund_flow_120d":      action_fund_flow_120d,
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print_usage()
        return
    payload = parse_payload()
    action = payload.get("action", "")
    if not action:
        die("action is required. Valid actions: " + ", ".join(ACTIONS.keys()))
    handler = ACTIONS.get(action)
    if not handler:
        die(f"Unknown action: {action}. Valid: {', '.join(ACTIONS.keys())}")
    try:
        result = handler(payload)
        print(json.dumps(result, ensure_ascii=False))
    except SystemExit:
        raise
    except Exception as e:
        die(f"Handler error ({action}): {e}")

if __name__ == "__main__":
    main()
