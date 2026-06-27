---
name: market-info
description: A股实时市场行情数据工具 — 覆盖行情(腾讯PE/PB/市值/换手率/涨跌停+百度K线带MA)、信号(同花顺强势股+题材归因+北向资金+东财板块归属+资金流向分钟级+龙虎榜+全市场龙虎榜+解禁日历+行业板块排名)、资金面(融资融券+大宗交易+股东户数+分红送转+资金流120日)。适用于实时行情查询、盘中资金流向、龙虎榜跟踪、板块轮动、题材归因、解禁预警、行业对比等场景。关键词：行情、K线、盘口、实时报价、PE、PB、市值、强势股、题材、热点、北向资金、资金流向、龙虎榜、解禁、融资融券、大宗交易、股东户数、分红、行业排名。
origin: custom
version: 2.0.0
---

> 📦 源项目：https://github.com/simonlin1212/a-stock-data

# A股实时市场行情工具

覆盖行情层、信号层、资金面三大数据维度，15 个 action，优先用腾讯（不封IP），东财接口内置限流防封。

## 数据源优先级

| 优先级 | 数据源 | 封 IP 风险 | 覆盖 |
|--------|--------|-----------|------|
| **1（首选）** | **腾讯财经** HTTP | **不封 IP** | 实时价、PE/PB/市值/换手率/涨跌停、指数、ETF |
| 2 | 同花顺 HTTP | 极低 | 强势股/题材归因/北向资金 |
| 3 | 百度股市通 HTTP | 极低 | K线（带 MA5/10/20） |
| **4（仅独有数据）** | **东财** HTTP | **有风控，会封 IP** | 板块归属、资金流向、龙虎榜、解禁、融资融券、大宗交易、股东户数、分红、行业排名 |

东财风控阈值：>5次/秒、并发≥10、1分钟≥200次 → 临时封 IP。脚本已内置串行限流（间隔≥1s+随机抖动）。

## Prerequisites

**Python 版本要求：** Python 3.9+

```bash
# 唯一外部依赖（腾讯行情用标准库 urllib，无需额外安装）
pip install requests
```

| 依赖 | 版本 | 用途 |
|------|------|------|
| requests | any | 所有东财/同花顺/百度 HTTP API |

> 不含第三方数据封装依赖（akshare 等），全部直连源站 HTTP API。

**依赖缺失检查：** 脚本启动时自动检测 `requests`，缺少的话会打印 JSON 错误并退出：

```json
{"error": "pip install requests first", "exit_code": 1}
```

## 首次使用（环境自检）

**第一次调用前先跑 `doctor`，一次确认 Python/依赖/网络/样本调用都正常**：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-info/scripts/market-info.py '{"action":"doctor"}'
```

返回 `code=0` 即可正常使用其它 action；否则按 `data.checks[*].hint` 修复。

> **Windows 提示：** 若 `python3` 命令不存在，改用 `python`（Windows 官方安装器只装 `python`）。输出已自动按 stdout 是否管道化做编码切换，无需手动设 `PYTHONIOENCODING`。

## 快速开始

`${CLAUDE_PLUGIN_ROOT}` 是 Claude Code 在运行时注入的变量，指向本 plugin 的安装根目录。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-info/scripts/market-info.py '{"action":"<action>",...}'
```

## 输入约定

单个 JSON 字符串参数，必填 `action`（选择端点），其余字段依 action 而定。

### 公共规则

- 股票代码支持多种格式：`688017`、`SH688017`、`688017.SH`，内部归一化为 6 位数字
- 东财系 action 受全局限流保护，连续批量调用间隔 ≥1s，可通过环境变量 `MARKET_EM_INTERVAL` 调大
- 返回金额单位：东财 push2 系列为**元**，腾讯行情市值为**亿**

---

## Actions

### 行情层

#### quote — 腾讯财经实时行情

PE/PB/市值/换手率/涨跌停/指数/ETF。

```json
{"action":"quote","codes":["600519","000858"]}
{"action":"quote","codes":["000001","399006"]}
{"action":"quote","codes":["510050"]}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| codes | string[] | 是 | 6位股票代码/指数代码/ETF代码 |

**返回字段：** `name`, `price`, `last_close`, `open`, `change_pct`, `high`, `low`, `turnover_pct`, `pe_ttm`, `pb`, `mcap_yi`(亿), `float_mcap_yi`(亿), `limit_up`, `limit_down`, `pe_static`

#### kline_baidu — 百度K线（带MA均价）

```json
{"action":"kline_baidu","code":"600519","start_time":""}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| start_time | string | 否 | 起始日期，空=全部 |

**返回：** `keys`(字段名列表，含 ma5/ma10/ma20 均价), `rows`(解析后K线数组)

> ⚠️ 百度 PAE 接口可能间歇返回 403（IP 级风控）。遇此情况返回 `error` 字段标注。

---

### 信号层

#### hot_stocks — 同花顺当日强势股+题材归因

```json
{"action":"hot_stocks"}
{"action":"hot_stocks","date":"2026-06-19"}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 否 | YYYY-MM-DD，默认今天 |

**返回：** 每只股票含 `code`, `name`, `reason`(题材归因 tags), `close`, `change_pct`, `turnover_pct`, `amount`, `dde_net`(大单净量), `market`

#### northbound — 北向资金（实时分钟+历史缓存）

```json
{"action":"northbound","mode":"realtime"}
{"action":"northbound","mode":"history","days":20}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| mode | string | 否 | `realtime`(默认) 或 `history` |
| days | int | 否 | history 模式取最近 N 天，默认 20 |

**实时返回：** 每分钟一条 `{time, hgt_yi(沪股通亿), sgt_yi(深股通亿)}`

自动缓存：每次请求实时数据后，自动把收盘累计写入本地 `~/.a-stock-market/northbound_daily.csv`。

#### concept_blocks — 个股板块/概念归属

```json
{"action":"concept_blocks","code":"600519"}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |

**返回：** `boards`(列表: name, code(BK码), change_pct, lead_stock), `concept_tags`(板块名列表), `total`

#### fund_flow_minute — 个股资金流向（分钟级）

```json
{"action":"fund_flow_minute","code":"000858"}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |

**返回：** 每分钟一条 `{time, main_net(主力净流入), small_net, mid_net, large_net, super_net}`，单位：元

#### dragon_tiger — 龙虎榜（个股上榜+席位）

```json
{"action":"dragon_tiger","code":"002475","date":"2026-06-19","look_back":30}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| date | string | 否 | 截止日期，默认今天 |
| look_back | int | 否 | 回看天数，默认 30 |

**返回：** `records`(上榜记录: date, reason, net_buy_wan, turnover_pct, close, change_pct)

#### daily_dragon_tiger — 全市场龙虎榜

```json
{"action":"daily_dragon_tiger","date":"2026-06-19"}
{"action":"daily_dragon_tiger","date":"2026-06-19","min_net_buy":5000}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 否 | YYYY-MM-DD，默认今天 |
| min_net_buy | float | 否 | 净买入下限（万元），不填=不过滤 |

**返回：** `stocks`(code, name, reason, close, change_pct, net_buy_wan, buy_wan, sell_wan, turnover_pct)

#### lockup_expiry — 限售解禁日历

```json
{"action":"lockup_expiry","code":"002475","date":"2026-06-19","forward_days":90}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| date | string | 否 | 基准日期，默认今天 |
| forward_days | int | 否 | 未来天数，默认 90 |

**返回：** `history`(历史解禁), `upcoming`(未来待解禁)，每条含 date, type, shares, ratio

#### industry_compare — 行业板块排名

```json
{"action":"industry_compare","top_n":10}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| top_n | int | 否 | 返回前N名+后N名，默认 20 |

**返回：** `top`(涨幅前 N 行业), `bottom`(跌幅后 N 行业), `total_industries`。每条含 rank, name, change_pct, code, up_count, down_count, leader, leader_change

---

### 资金面

#### margin_trading — 融资融券明细

```json
{"action":"margin_trading","code":"600519","size":30}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| size | int | 否 | 返回条数，默认 30 |

**返回：** 每天一条 `{date, rzye(融资余额), rzmre(融资买入), rzche(融资偿还), rqye(融券余额), rqmcl(融券卖出量), rqchl(融券偿还量), rzrqye(合计)}`

#### block_trade — 大宗交易记录

```json
{"action":"block_trade","code":"600519","size":20}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| size | int | 否 | 返回条数，默认 20 |

**返回：** 每笔含 date, price, close, premium_pct(溢价率%), vol, amount, buyer, seller

#### holders — 股东户数变化

```json
{"action":"holders","code":"600519","size":10}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| size | int | 否 | 返回季度数，默认 10 |

**返回：** 每季含 date, holder_num, change_num, change_ratio(环比%), avg_shares(户均持股)

#### dividend — 分红送转历史

```json
{"action":"dividend","code":"600519","size":20}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| size | int | 否 | 返回条数，默认 20 |

**返回：** 每次含 date, bonus_rmb(每股派息), transfer_ratio(每10股转增), bonus_ratio(每10股送股), plan(进度)

#### fund_flow_120d — 个股资金流（120日日级）

```json
{"action":"fund_flow_120d","code":"600519","size":120}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 6位代码 |
| size | int | 否 | 返回天数，默认 120 |

**返回：** 每天一条 `{date, main_net, small_net, mid_net, large_net, super_net}`，单位：元

---

## 输出约定

### 成功

```json
{"code":0, "message":"ok", "data":..., "item_count":N}
```

`data` 可能是数组或对象，视 action 而定。

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
| `HTTP request failed` | 网络超时或 DNS 错误 |
| `Handler error (xxx): ...` | 下游 API 异常 |

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MARKET_EM_INTERVAL` | `1.0` | 东财请求最小间隔（秒），批量任务建议上调到 1.5~2 |

---

## 数据源详情

| 数据源 | 协议 | 用途 | 鉴权 |
|--------|------|------|------|
| 腾讯财经 `qt.gtimg.cn` | HTTP GBK | quote (PE/PB/市值/指数/ETF) | 无 |
| 百度股市通 `finance.pae.baidu.com` | HTTP | kline_baidu (K线+MA) | 无 |
| 同花顺 `zx.10jqka.com.cn` | HTTP | hot_stocks (强势股+题材) | 无 |
| 同花顺 `data.hexin.cn` | HTTP | northbound (北向资金) | 无 |
| 东财 push2 `push2.eastmoney.com` | HTTP | concept_blocks, fund_flow_minute, industry_compare | 无 |
| 东财 push2his `push2his.eastmoney.com` | HTTP | fund_flow_120d | 无 |
| 东财 datacenter `datacenter-web.eastmoney.com` | HTTP | dragon_tiger, daily_dragon_tiger, lockup_expiry, margin_trading, block_trade, holders, dividend | 无 |

所有数据源均免费无 key，无需注册。

---

## FAQ

### Q: 腾讯 quote 和 mootdx K 线有什么区别？
A: 腾讯 = 估值层（PE/PB/市值/换手率/涨跌停），不封 IP。K 线数据可走 `kline_baidu`（带 MA 均价）或单独安装 mootdx。

### Q: 东财接口偶尔返回空或断连？
A: 部分大陆住宅 IP 会被东财间歇风控。对策：隔几分钟重试、换网络、调大 `MARKET_EM_INTERVAL`。

### Q: 北向资金历史数据少？
A: 本地自缓存模式。每次调 `northbound` (realtime) 自动写入本地 CSV，历史越跑越丰富。

### Q: 腾讯 API 字段 43 是 PB 吗？
A: 不是。43=振幅%，46=PB。网上很多教程写错了。

### Q: 百度 K 线 ResultCode 不稳定？
A: 已知问题——有时 int，有时 string。脚本已用 `str()` 统一比较并做容错处理。
