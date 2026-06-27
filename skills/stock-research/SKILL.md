---
name: stock-research
description: A股股票信息与研报工具 — 覆盖研报(东财研报列表+评级+EPS预测+同花顺一致预期)、基础数据(东财个股基本面+新浪财报三表)、公告(巨潮全文检索)、估值计算(前向PE+PEG+PE消化时间+单票完整估值)。适用于个股调研、研报检索、财务分析、估值建模、批量对比等场景。关键词：研报、机构评级、EPS预测、一致预期、财报、季报、资产负债表、利润表、现金流量表、公告、估值、PE消化、前向PE、PEG、ROE、净利润、主营收入。
origin: custom
version: 2.0.0
---

> 📦 源项目：https://github.com/simonlin1212/a-stock-data

# A股股票信息与研报工具

覆盖研报层、基础数据层、公告层、估值计算，7 个 action。

## Prerequisites

**Python 版本要求：** Python 3.9+

```bash
pip install requests pandas
```

| 依赖 | 版本 | 用途 |
|------|------|------|
| requests | any | 所有 HTTP API 直连 |
| pandas | any | HTML 表格解析（仅 eps_forecast / full_valuation，其余 action 不需要） |

> 不含第三方数据封装依赖（akshare 等），全部直连源站 HTTP API。

**依赖缺失检查：** 脚本启动时自动检测，缺少时会打印 JSON 错误并退出：

- 缺少 `requests`：
  ```json
  {"error": "pip install requests first", "exit_code": 1}
  ```
- 缺少 `pandas`（仅影响 eps_forecast / full_valuation）：
  ```json
  {"error": "pip install pandas first (required for eps_forecast/full_valuation)", "exit_code": 1}
  ```

> 其余 action（reports, stock_info, financial_report, announcements, valuation）**无需 pandas**，只装 `requests` 即可使用。

## 快速开始

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/stock-research/scripts/stock-research.py '{"action":"<action>",...}'
```

## 输入约定

单个 JSON 字符串参数，必填 `action`。

### 公共规则

- 股票代码支持多种格式：`688017`、`SH688017`、`688017.SH`，内部归一化
- 东财系 action（reports, stock_info）受全局限流保护，可通过 `RESEARCH_EM_INTERVAL` 环境变量调大

---

## Actions

### 研报层

#### reports — 东财研报列表（含评级+三年EPS预测）

```json
{"action":"reports","code":"688017","pages":3}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| pages | int | 否 | 最多翻页数，默认 3（每页 100 篇） |

**返回：** `reports` 列表 + `total`。每条含：

| 字段 | 含义 |
|------|------|
| title | 研报标题 |
| date | 发布日期 |
| org | 机构简称 |
| info_code | 用于拼 PDF URL |
| eps_this_year | 今年EPS预测 |
| eps_next_year | 明年EPS预测 |
| eps_two_year | 后年EPS预测 |
| rating | 评级(买入/增持/...) |
| industry | 行业分类 |

#### eps_forecast — 同花顺机构一致预期EPS

```json
{"action":"eps_forecast","code":"688017"}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |

**返回：** `periods`(各年度: year, analyst_count, eps_mean, eps_min, eps_max), `eps_current`(今年均值), `eps_next`(明年均值), `analyst_count`

> "预测机构数" < 3 的要谨慎。无机构覆盖时 `periods` 为空。

---

### 基础数据层

#### stock_info — 东财个股基本面

```json
{"action":"stock_info","code":"688017"}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |

**返回：** `code`, `name`, `industry`, `total_shares`(总股本), `float_shares`(流通股), `mcap`(总市值, 元), `float_mcap`, `list_date`, `price`

#### financial_report — 新浪财报三表

```json
{"action":"financial_report","code":"600519","type":"lrb","periods":8}
{"action":"financial_report","code":"600519","type":"fzb","periods":4}
{"action":"financial_report","code":"600519","type":"llb","periods":4}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| type | string | 否 | `lrb`(利润表), `fzb`(资产负债表), `llb`(现金流量表)，默认 lrb |
| periods | int | 否 | 返回期数，默认 8 |

**返回：** `periods` 列表，每条为 `{period(报告期), 科目1, 科目1_yoy(同比), ...}`。科目名即新浪原始 `item_title`。

---

### 公告层

#### announcements — 巨潮公告全文检索

```json
{"action":"announcements","code":"600519","size":30}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| size | int | 否 | 返回条数，默认 30 |

**返回：** `org_id`(股票对应巨潮机构ID), `announcements` 列表(每条: title, type, date, url), `total`

内部自动通过巨潮官方映射表（`szse_stock.json`）查询真实 orgId，支持全部 6198 只 A 股。

---

### 估值计算

#### valuation — 估值公式（前向PE / PEG / PE消化）

```json
{"action":"valuation","price":100,"eps":5,"cagr":0.3}
{"action":"valuation","pe":20,"cagr":0.3}
{"action":"valuation","current_pe":60,"cagr":0.3,"target_pe":30}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| price | float | 条件 | 当前股价 |
| eps | float | 条件 | 年度EPS |
| pe | float | 条件 | 前向PE（price/eps 或直接给定） |
| current_pe | float | 条件 | 当前PE（用于消化时间计算） |
| cagr | float | 条件 | 盈利增速（小数，如 0.3 = 30%） |
| target_pe | float | 否 | 目标PE，默认 30 |

**返回：** `forward_pe`(前向PE), `peg`(PEG), `digest_years`(PE消化到目标需要多少年)

**估值框架：** PEG < 1 便宜，1~1.5 合理，> 1.5 贵。PE消化 < 2年合理，> 4年太贵。

#### full_valuation — 单票完整估值

```json
{"action":"full_valuation","code":"688017"}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |

**返回：** `name`, `price`, `mcap_yi`(亿), `pe_ttm`, `pb`, `eps_current`, `eps_next`, `pe_fwd`(前向PE), `cagr_pct`(增速%), `peg`, `digest_years`, `analyst_count`

整合腾讯实时行情 + 同花顺一致预期 EPS，一次性输出完整估值画像。

---

## 输出约定

### 成功

```json
{"code":0, "message":"ok", "data":..., "item_count":N}
```

### 失败

```json
{"error":"<描述>", "exit_code":1}
```

常见错误：

| error | 原因 |
|-------|------|
| `action is required` | 缺少 action 字段 |
| `Unknown action: xxx` | action 名称不存在 |
| `code is required` | 缺少 code 参数 |
| `Invalid JSON payload` | JSON 格式错误或不是对象 |
| `pip install pandas first` | eps_forecast/full_valuation 需要 pandas |

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RESEARCH_EM_INTERVAL` | `1.0` | 东财请求最小间隔（秒），批量任务建议上调 |

---

## 数据源详情

| 数据源 | 协议 | Action | 鉴权 |
|--------|------|--------|------|
| 东财 reportapi `reportapi.eastmoney.com` | HTTP | reports | 无 |
| 同花顺 `basic.10jqka.com.cn` | HTTP | eps_forecast | 无(需UA) |
| 东财 push2 `push2.eastmoney.com` | HTTP | stock_info | 无 |
| 新浪财经 `quotes.sina.cn` | HTTP | financial_report | 无 |
| 巨潮 `cninfo.com.cn` | HTTP | announcements | 无 |
| 腾讯 `qt.gtimg.cn` | HTTP | full_valuation(行情部分) | 无 |

全部免费无 key。

---

## FAQ

### Q: eps_forecast 返回空？
A: 该股票无机构覆盖。小盘/次新/ST 股常见。可 fallback 到 `reports` 里的 eps_this_year 字段。

### Q: 新浪财报三表字段解读？
A: `lrb`(利润表) / `fzb`(资产负债表) / `llb`(现金流量表)。每期 dict 中的科目名即新浪原始 `item_title`，`_yoy` 后缀为同比变化。

### Q: announces 公告的 type 字段是数字？
A: 巨潮接口 `announcementTypeName` 返回的是代码串（如 `01010503\|\|010113\|\|011301`），非人工可读。需对照交易所公告分类编码表。

### Q: EPS 差别很大？
A: `reports` 返回的是**单个分析师预测值**，`eps_forecast` 返回的是**机构一致预期均值**。对估值，均值更可靠；个体值适合看分歧度。
