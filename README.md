# Financial Skills

A股金融数据 skill 集合 —— 代码与文档分离，一个 action 一个 JSON 入参。

## Skills

### market-info — 实时市场行情

15 个 action，覆盖行情/信号/资金面。腾讯/同花顺/百度/东财多数据源，东财接口内置限流防封。

```bash
pip install requests
python3 market-info/scripts/market-info.py '{"action":"quote","codes":["600519"]}'
```

| 类别 | Action |
|------|--------|
| 行情 | `quote` `kline_baidu` |
| 信号 | `hot_stocks` `northbound` `concept_blocks` `fund_flow_minute` `dragon_tiger` `daily_dragon_tiger` `lockup_expiry` `industry_compare` |
| 资金面 | `margin_trading` `block_trade` `holders` `dividend` `fund_flow_120d` |

### stock-research — 股票信息与研报

7 个 action，覆盖研报/基本面/公告/估值。

```bash
pip install requests pandas
python3 stock-research/scripts/stock-research.py '{"action":"reports","code":"688017"}'
```

| 类别 | Action |
|------|--------|
| 研报 | `reports` `eps_forecast` |
| 基本面 | `stock_info` `financial_report` |
| 公告 | `announcements` |
| 估值 | `valuation` `full_valuation` |

## 目录结构

```
financial-skills/
├── market-info/
│   ├── SKILL.md
│   └── scripts/
│       └── market-info.py
├── stock-research/
│   ├── SKILL.md
│   └── scripts/
│       └── stock-research.py
└── README.md
```

## 调用模式

所有 skill 遵循统一接口：

```
python3 {baseDir}/scripts/<skill>.py '<JSON_PAYLOAD>'
```

成功输出：
```json
{"code": 0, "message": "ok", "data": {...}, "item_count": N}
```

失败输出：
```json
{"error": "...", "exit_code": 1}
```

## 数据源

| 数据源 | 鉴权 | 用途 |
|--------|------|------|
| 腾讯财经 `qt.gtimg.cn` | 无 | 实时行情 PE/PB/市值 |
| 同花顺 `zx.10jqka.com.cn` | 无 | 强势股/题材归因/北向资金/一致预期 |
| 百度股市通 `finance.pae.baidu.com` | 无 | K线带MA均价 |
| 东财 push2/datacenter/push2his/reportapi | 无 | 板块/资金流/龙虎榜/研报等 |
| 新浪财经 `quotes.sina.cn` | 无 | 财报三表 |
| 巨潮 `cninfo.com.cn` | 无 | 公告全文 |

全部免费，无需注册。

## License

Apache License 2.0
