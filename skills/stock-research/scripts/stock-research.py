#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stock-research — A股股票信息与研报工具

用法: python3 ${CLAUDE_PLUGIN_ROOT}/skills/stock-research/scripts/stock-research.py '<JSON>'

所有行动公用一个 JSON 入参，按 stdout 输出 JSON 结果。
成功: {"code":0, "message":"ok", "data":...}
失败: {"error":"...", "exit_code":1}
"""

import json
import os
import sys
import time
import math
import random
import urllib.request
from pathlib import Path
from io import StringIO

try:
    import requests
except ImportError:
    print(json.dumps({"error": "pip install requests first", "exit_code": 1}, ensure_ascii=False))
    raise SystemExit(1)

try:
    import pandas as pd
except ImportError:
    pd = None  # 仅 eps_forecast / full_valuation 需要；其余 action 正常运行

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# 东财限流
EM_SESSION = requests.Session()
EM_SESSION.headers.update({"User-Agent": UA})
EM_MIN_INTERVAL = float(os.environ.get("RESEARCH_EM_INTERVAL", "1.0"))
_em_last = [0.0]

# 巨潮 orgId 缓存
_CNINFO_CACHE_FILE = Path.home() / ".a-stock-market" / "cninfo_orgid_cache.json"

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
        "skill": "stock-research",
        "actions": [
            "reports", "eps_forecast", "stock_info",
            "financial_report", "announcements",
            "valuation", "full_valuation",
        ],
        "example": json.dumps({"action": "reports", "code": "600519"}),
    }, ensure_ascii=False, indent=2))

def em_get(url: str, params: dict | None = None, headers: dict | None = None,
           timeout: int = 15):
    wait = EM_MIN_INTERVAL - (time.time() - _em_last[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        resp = EM_SESSION.get(url, params=params, headers=headers, timeout=timeout)
        return resp
    finally:
        _em_last[0] = time.time()

def normalize_code(code: str) -> str:
    code = code.strip().upper()
    for prefix in ("SH", "SZ", "BJ"):
        if code.startswith(prefix):
            code = code[len(prefix):]
    if "." in code:
        code = code.split(".")[0]
    return code

def market_code(code: str) -> int:
    return 1 if code.startswith("6") else 0

# ── 研报层 ────────────────────────────────────────────────

def action_reports(p: dict):
    """东财研报列表（含评级+EPS预测）。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    max_pages = int(p.get("pages", 3))
    REPORT_API = "https://reportapi.eastmoney.com/report/list"

    all_records = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*", "pageSize": "100", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": "2000-01-01", "endTime": "2030-01-01",
            "pageNo": str(page), "fields": "", "qType": "0",
            "orgCode": "", "code": code, "rcode": "",
            "p": str(page), "pageNum": str(page), "pageNumber": str(page),
        }
        try:
            resp = em_get(REPORT_API, params=params,
                         headers={"Referer": "https://data.eastmoney.com/"}, timeout=30)
            d = resp.json()
        except Exception as e:
            die(f"Reports API request failed: {e}")
        rows = d.get("data") or []
        if not rows:
            break
        all_records.extend(rows)
        if page >= (d.get("TotalPage", 1) or 1):
            break

    items = []
    for r in all_records:
        items.append({
            "title": r.get("title", ""),
            "date": str(r.get("publishDate", ""))[:10],
            "org": r.get("orgSName", ""),
            "info_code": r.get("infoCode", ""),
            "eps_this_year": r.get("predictThisYearEps"),
            "eps_next_year": r.get("predictNextYearEps"),
            "eps_two_year": r.get("predictNextTwoYearEps"),
            "rating": r.get("emRatingName", ""),
            "industry": r.get("indvInduName", ""),
        })
    return build_result({"reports": items, "total": len(items)})

def action_eps_forecast(p: dict):
    """同花顺机构一致预期EPS。"""
    if pd is None:
        die("pip install pandas first (required for eps_forecast/full_valuation)")
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
    headers = {"User-Agent": UA, "Referer": "https://basic.10jqka.com.cn/"}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = "gbk"
    except Exception as e:
        die(f"THS EPS forecast request failed: {e}")

    try:
        dfs = pd.read_html(StringIO(resp.text))
    except Exception as e:
        die(f"HTML table parse failed: {e}")

    result = {"periods": [], "raw_tables": len(dfs)}
    for df in dfs:
        cols = [str(c) for c in df.columns]
        if any("每股收益" in c or "均值" in c for c in cols):
            periods = []
            for _, row in df.iterrows():
                periods.append({
                    "year": str(row.iloc[0]) if len(row) > 0 else "",
                    "analyst_count": int(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else 0,
                    "eps_mean": float(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else None,
                    "eps_min": float(row.iloc[3]) if len(row) > 3 and pd.notna(row.iloc[3]) else None,
                    "eps_max": float(row.iloc[4]) if len(row) > 4 and pd.notna(row.iloc[4]) else None,
                })
            result["periods"] = periods
            break

    if result["periods"]:
        result["eps_current"] = result["periods"][0].get("eps_mean") if len(result["periods"]) > 0 else None
        result["eps_next"] = result["periods"][1].get("eps_mean") if len(result["periods"]) > 1 else None
        result["analyst_count"] = result["periods"][0].get("analyst_count") if result["periods"] else 0

    return build_result(result)

# ── 基础数据层 ────────────────────────────────────────────

def action_stock_info(p: dict):
    """东财个股基本面信息。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    mk = market_code(code)

    try:
        resp = em_get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={
                "fltt": "2", "invt": "2",
                "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
                "secid": f"{mk}.{code}",
            },
            headers={"User-Agent": UA},
            timeout=10
        )
        d = resp.json().get("data", {})
    except Exception as e:
        die(f"Stock info request failed: {e}")

    return build_result({
        "code": d.get("f57", code),
        "name": d.get("f58", ""),
        "industry": d.get("f127", ""),
        "total_shares": d.get("f84", 0),
        "float_shares": d.get("f85", 0),
        "mcap": d.get("f116", 0),
        "float_mcap": d.get("f117", 0),
        "list_date": str(d.get("f189", "")),
        "price": d.get("f43", 0),
    })

def action_financial_report(p: dict):
    """新浪财报三表（资产负债表/利润表/现金流量表）。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    report_type = p.get("type", "lrb")  # lrb=利润表, fzb=资产负债表, llb=现金流量表
    if report_type not in ("lrb", "fzb", "llb"):
        die("type must be lrb, fzb, or llb")
    num = int(p.get("periods", 8))

    prefix = "sh" if code.startswith("6") else "sz"
    paper_code = f"{prefix}{code}"
    url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
    params = {"paperCode": paper_code, "source": report_type, "type": "0", "page": "1", "num": str(num)}

    try:
        resp = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15)
        data = resp.json()
    except Exception as e:
        die(f"Sina financial report request failed: {e}")

    report_list = data.get("result", {}).get("data", {}).get("report_list", {}) or {}
    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec = {"period": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for it in obj.get("data", []) or []:
            title = it.get("item_title", "")
            if not title or it.get("item_value") is None:
                continue
            rec[title] = it.get("item_value")
            tongbi = it.get("item_tongbi")
            if tongbi not in (None, ""):
                rec[title + "_yoy"] = tongbi
        rows.append(rec)

    return build_result({"report_type": report_type, "periods": rows, "total": len(rows)})

# ── 公告层 ────────────────────────────────────────────────

def _load_cninfo_orgid_map():
    """加载巨潮 orgId 映射表（带缓存）。"""
    if _CNINFO_CACHE_FILE.exists():
        try:
            with open(_CNINFO_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.loads(f.read())
        except Exception:
            pass

    try:
        resp = requests.get("http://www.cninfo.com.cn/new/data/szse_stock.json",
                            headers={"User-Agent": UA}, timeout=15)
        data = resp.json()
        org_map = {s["code"]: s["orgId"] for s in data.get("stockList", [])}
        _CNINFO_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_CNINFO_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(org_map, f, ensure_ascii=False)
        return org_map
    except Exception:
        return {}

def action_announcements(p: dict):
    """巨潮公告全文检索。"""
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)
    page_size = int(p.get("size", 30))

    org_map = _load_cninfo_orgid_map()
    org_id = org_map.get(code)
    if not org_id:
        if code.startswith("6"):
            org_id = f"gssh0{code}"
        elif code.startswith("8") or code.startswith("4"):
            org_id = f"gsbj0{code}"
        else:
            org_id = f"gssz0{code}"

    payload = {
        "stock": f"{code},{org_id}",
        "tabName": "fulltext", "pageSize": str(page_size), "pageNum": "1",
        "column": "", "category": "", "plate": "", "seDate": "",
        "searchkey": "", "secid": "", "sortName": "", "sortType": "",
        "isHLtitle": "true",
    }
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.cninfo.com.cn/new/disclosure",
        "Origin": "https://www.cninfo.com.cn",
    }
    try:
        resp = requests.post("https://www.cninfo.com.cn/new/hisAnnouncement/query",
                            data=payload, headers=headers, timeout=15)
        d = resp.json()
    except Exception as e:
        die(f"cninfo announcements request failed: {e}")

    items = []
    for item in d.get("announcements", []) or []:
        ts = item.get("announcementTime")
        if isinstance(ts, (int, float)):
            date = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        else:
            date = str(ts)[:10] if ts else ""
        items.append({
            "title": item.get("announcementTitle", ""),
            "type": item.get("announcementTypeName", ""),
            "date": date,
            "url": f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={item.get('announcementId', '')}",
        })

    return build_result({"org_id": org_id, "announcements": items, "total": len(items)})

# ── 估值计算 ──────────────────────────────────────────────

def action_valuation(p: dict):
    """估值公式计算（前向PE / PEG / PE消化时间）。"""
    result = {}

    # 前向PE
    price = p.get("price")
    eps = p.get("eps")
    if price is not None and eps is not None:
        price = float(price)
        eps = float(eps)
        result["forward_pe"] = round(price / eps, 1) if eps > 0 else None
    else:
        result["forward_pe"] = None

    # PEG
    pe = p.get("pe", result.get("forward_pe"))
    cagr = p.get("cagr")
    if pe is not None and cagr is not None:
        pe = float(pe)
        cagr = float(cagr)
        result["peg"] = round(pe / (cagr * 100), 2) if cagr > 0 else None
    else:
        result["peg"] = None

    # PE消化时间
    current_pe = p.get("current_pe", result.get("forward_pe"))
    cagr_digest = p.get("cagr", cagr)
    target = float(p.get("target_pe", 30))
    if current_pe is not None and cagr_digest is not None:
        current_pe = float(current_pe)
        cagr_digest = float(cagr_digest)
        if current_pe <= target:
            result["digest_years"] = 0.0
        elif cagr_digest <= 0:
            result["digest_years"] = None
        else:
            result["digest_years"] = round(math.log(current_pe / target) / math.log(1 + cagr_digest), 1)
    else:
        result["digest_years"] = None

    return build_result(result)

def action_full_valuation(p: dict):
    """单票完整估值（腾讯行情+同花顺EPS一致预期）。"""
    if pd is None:
        die("pip install pandas first (required for eps_forecast/full_valuation)")
    code = p.get("code", "")
    if not code:
        die("code is required")
    code = normalize_code(code)

    # Step 1: 腾讯实时行情
    prefix = "sh" if code.startswith(("6","9")) else ("bj" if code.startswith("8") else "sz")
    try:
        url = f"https://qt.gtimg.cn/q={prefix}{code}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk")
        vals = data.split('"')[1].split("~")
        price = float(vals[3])
        mcap = float(vals[44])
        pe_ttm = float(vals[39]) if vals[39] else 0
        pb = float(vals[46]) if vals[46] else 0
        name = vals[1]
    except Exception as e:
        die(f"Tencent quote in valuation failed: {e}")

    # Step 2: 一致预期EPS
    eps_cur = eps_next = None
    analyst_count = 0
    try:
        url_ths = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
        resp_ths = requests.get(url_ths,
            headers={"User-Agent": UA, "Referer": "https://basic.10jqka.com.cn/"}, timeout=15)
        resp_ths.encoding = "gbk"
        dfs = pd.read_html(StringIO(resp_ths.text))
        for df in dfs:
            cols = [str(c) for c in df.columns]
            if any("每股收益" in c or "均值" in c for c in cols):
                try:
                    eps_cur = float(df.iloc[0, 2]) if pd.notna(df.iloc[0, 2]) else None
                    analyst_count = int(df.iloc[0, 1]) if pd.notna(df.iloc[0, 1]) else 0
                    if len(df) > 1:
                        eps_next = float(df.iloc[1, 2]) if pd.notna(df.iloc[1, 2]) else None
                except Exception:
                    pass
                break
    except Exception as e:
        pass  # EPS forecast is optional

    # Step 3: 估值指标
    pe_fwd = price / eps_cur if eps_cur else None
    cagr = (eps_next / eps_cur - 1) if (eps_cur and eps_next) else None
    peg = pe_fwd / (cagr * 100) if (pe_fwd and cagr and cagr > 0) else None
    digest = 0.0
    if pe_fwd and cagr and pe_fwd > 30 and cagr > 0:
        digest = round(math.log(pe_fwd / 30) / math.log(1 + cagr), 1)
    elif pe_fwd and pe_fwd <= 30:
        digest = 0.0

    return build_result({
        "name": name,
        "code": code,
        "price": price,
        "mcap_yi": mcap,
        "pe_ttm": round(pe_ttm, 1) if pe_ttm else None,
        "pb": round(pb, 2) if pb else None,
        "eps_current": eps_cur,
        "eps_next": eps_next,
        "pe_fwd": round(pe_fwd, 1) if pe_fwd else None,
        "cagr_pct": round(cagr * 100, 1) if cagr else None,
        "peg": round(peg, 2) if peg else None,
        "digest_years": digest,
        "analyst_count": analyst_count,
    })

# ── 主入口 ────────────────────────────────────────────────

from datetime import datetime  # noqa: E402 (used in announcements action)

ACTIONS = {
    "reports":           action_reports,
    "eps_forecast":      action_eps_forecast,
    "stock_info":        action_stock_info,
    "financial_report":  action_financial_report,
    "announcements":     action_announcements,
    "valuation":         action_valuation,
    "full_valuation":    action_full_valuation,
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
