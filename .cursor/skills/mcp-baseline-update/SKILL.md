---
name: mcp-baseline-update
description: >-
  Updates MCP 专项 Excel 「数据基准」 by querying ClickHouse (uat/prod)
  for an openID, without opening the web UI. Use when the user asks to
  更新数据基准, 重算基准, 刷基准, 跑数据基准更新工具, refresh baseline,
  or regenerate 数据基准 for MCP专项测试用例.xlsx.
---

# MCP 数据基准更新

用本机「数据基准更新工具」按 openID 直连 ClickHouse 重算，回填「数据基准」列。  
**不要**再让用户双击网页；Agent 直接跑下面的 CLI。

## 工具根目录

```
/Users/xixi/Downloads/常用工具/数据基准更新工具
```

Python：优先 `…/数据基准更新工具/.venv/bin/python`。没有就先：

```bash
cd "/Users/xixi/Downloads/常用工具/数据基准更新工具"
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## 标准流程

1. **确认入参**（缺就问一句或用默认）
   - `--xlsx`：专项用例表（须含 sheet `MCP专项` + `指标`）。默认常为  
     `~/Downloads/MCP专项测试用例_10月26.xlsx` 或仓库  
     `testdata/mcp/source/MCP专项测试用例_10月26.xlsx`
   - `--oid`：openID。未给则读 `automation/.env` 的 `MCP_OPEN_ID`，再退回工具 `config.json` 的 `accounts.A`
   - `--date`：基准日 `YYYY-MM-DD`，默认今天（「今天/昨天」按这天推）
   - `--env`：可选 `uat` / `prod`；不传则自动探测有数据的环境

2. **执行**（一条命令）：

```bash
TOOL="/Users/xixi/Downloads/常用工具/数据基准更新工具"
"$TOOL/.venv/bin/python" "$TOOL/cli_update.py" \
  --xlsx "<专项xlsx>" \
  --oid "<openID>" \
  --date "$(date +%F)"
```

可选：`--env uat`、`--only M3-01`（只跑一条）、`--copy-to ~/Downloads/`（把结果再拷一份到目录）。

3. **回报用户**（精简）
   - 环境 + 覆盖率摘要（一致 / 有变化 / 需人工 / 不涉及）
   - 结果 xlsx 路径（在工具 `runs/<时间戳>/`）
   - 若有「有变化」「需人工」，列前几条 case_id + 旧→新 或 note；完整差异见同目录 `report.json`

4. **不要做的事**
   - 不要改 `config.json` 里的库密码并提交
   - 不要对库做写操作（工具本身已拦截非 SELECT）
   - 不要默认覆盖用户正在编辑的源表；产物是新文件，用户确认后再替换源表
   - 不要为此去起 `start.command` / Flask，除非用户明确要网页

## 状态含义

| 状态 | 含义 |
|------|------|
| match / 一致 | 与原基准相同（忽略排版） |
| drift / 有变化 | 数字变了（数据涨了或原基准有误） |
| manual / 需人工 | 无匹配口径，保留原值 |
| skip / 不涉及 | 协议/传输类，无数据基准 |

## 排障

- openID 两环境都是 0 手 → 先核对 oid / 环境，不要硬跑整表
- 代理导致连不上库 → `unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY`
- 详细口径与已知坑见工具目录 `README.md`
