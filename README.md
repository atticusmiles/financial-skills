# Financial Skills

A股金融数据 skill 集合 —— 代码与文档分离，一个 action 一个 JSON 入参。

[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-blue)](https://docs.claude.com/en/docs/claude-code/plugin-marketplaces)

## 在 Claude Code 中安装

本仓库是一个 Claude Code plugin marketplace。在 Claude Code 会话中执行：

```bash
# 1. 添加 marketplace（任选其一）
/plugin marketplace add atticusmiles/financial-skills          # GitHub
/plugin marketplace add /path/to/financial-skills              # 本地路径

# 2. 安装 plugin
/plugin install financial-skills@financial-skills

# 3. 安装 Python 依赖
pip install requests pandas
```

安装后三个 skill 即可被 Claude Code 自动加载：`market-info`、`stock-research`、`fetch_news`。

## Skills

### market-info — 实时市场行情

15 个 action，覆盖行情/信号/资金面。腾讯/同花顺/百度/东财多数据源，东财接口内置限流防封。

```bash
pip install requests
python3 ${CLAUDE_PLUGIN_ROOT}/skills/market-info/scripts/market-info.py '{"action":"quote","codes":["600519"]}'
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
python3 ${CLAUDE_PLUGIN_ROOT}/skills/stock-research/scripts/stock-research.py '{"action":"reports","code":"688017"}'
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
├── .claude-plugin/
│   ├── marketplace.json          # Claude Code marketplace 清单
│   └── plugin.json               # plugin 元数据
├── skills/
│   ├── market-info/
│   │   ├── SKILL.md
│   │   └── scripts/market-info.py
│   ├── stock-research/
│   │   ├── SKILL.md
│   │   └── scripts/stock-research.py
│   └── fetch_news/
│       ├── SKILL.md
│       └── scripts/fetch_news.py
├── README.md
└── .gitignore
```

## 调用模式

所有 skill 遵循统一接口（`${CLAUDE_PLUGIN_ROOT}` 由 Claude Code 运行时注入）：

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/<skill>/scripts/<skill>.py '<JSON_PAYLOAD>'
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
