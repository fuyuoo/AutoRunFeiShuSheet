# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

自动同步金融数据到飞书多维表格的Python脚本。从Tushare获取股票、ETF、板块的日线数据，本地聚合周线并计算技术指标，通过字段映射写入飞书多维表格。

## 技术栈

- Python 3.9+
- Tushare Pro API (金融数据)
- 飞书开放平台 API (多维表格)
- pandas / numpy (数据处理)

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行主程序
python main.py

# 运行测试
pytest tests/ -v

# 运行单个测试
pytest tests/test_indicators.py -v
```

## 项目结构

```
AutoRunFeiShuSheet/
├── config/
│   └── config.yaml        # 主配置文件
├── data/
│   └── cache/             # 数据缓存目录
├── src/
│   ├── feishu/            # 飞书API客户端
│   │   ├── client.py      # API认证和请求
│   │   └── bitable.py     # 多维表格操作
│   ├── tushare_api/       # Tushare数据获取
│   │   └── fetcher.py     # 支持 股票/ETF/板块 不同接口
│   ├── indicators/        # 技术指标计算
│   │   └── calculator.py  # KDJ/CCI/BOLL 本地计算
│   ├── utils/             # 工具模块
│   │   └── weekly_aggregator.py  # 日线→周线聚合
│   └── sync/              # 数据同步逻辑
│       └── sync_data.py   # 主同步流程
├── tests/                 # 测试目录
├── main.py                # 入口文件
└── requirements.txt
```

## 核心数据流程

```
飞书多维表格 ──读取──> 证券代码+类型
                         │
                         ▼
Tushare API ──获取──> 日线数据(前复权)
                         │
                         ▼
              日线聚合 ──> 周线数据
                         │
                         ▼
              本地计算 ──> 技术指标(KDJ/CCI/BOLL)
                         │
                         ▼
              字段映射 ──> 飞书字段
                         │
                         ▼
              批量写入 ──> 飞书多维表格
                         │
                         ▼
              输出报告 ──> 成功/失败/警告
```

## 配置说明

### config/config.yaml 结构

```yaml
tushare:
  token: "your_tushare_token"

feishu:
  app_id: "xxx"
  app_secret: "xxx"
  bitable:
    app_token: "xxx"
    table_id: "xxx"
    code_column: "证券代码"   # 代码列名
    type_column: "类型"       # 类型列名

# 字段映射: 飞书列名 -> 程序指标名称
field_mapping:
  "日线KDJ_K": "daily_kdj_k"
  "周线BOLL上轨": "weekly_boll_upper"
  # ...更多映射

sync:
  history_days: 120  # 获取历史天数

cache:
  enabled: true
  dir: "data/cache"
```

## 证券类型与接口

| 类型 | Tushare接口 | 备注 |
|------|------------|------|
| 股票 | `pro_bar(adj='qfq')` | 前复权数据 |
| ETF | `fund_daily` | 场内基金 |
| 板块/指数 | `index_daily` | 行业/概念板块 |

## 技术指标

**日线 & 周线：**
- KDJ (9,3,3)
- CCI (14)
- BOLL (20,2)

**周线聚合规则：**
- 开盘价 = 周首日开盘
- 最高价 = 周内最高
- 最低价 = 周内最低
- 收盘价 = 周末收盘
- 成交量 = 周内累加

## 飞书多维表格配置

1. 创建飞书应用：https://open.feishu.cn/app
2. 开通权限：`bitable:record:read`, `bitable:record:write`
3. 获取凭证：App ID, App Secret
4. 多维表格URL格式：`https://xxx.feishu.cn/base/{app_token}?table={table_id}`

## 本地缓存

- 日线数据缓存到 `data/cache/{code}_daily.csv`
- 避免重复请求Tushare
- 可在配置中禁用
