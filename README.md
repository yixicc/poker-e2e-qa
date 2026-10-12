# GTO 行动历史还原质量对比

对比「手工补全真值」与「旧版 / 新版系统发给 GTO 的请求报文」，输出 HTML 总览 + 逐手三方对照页。

## 输入

- `data/old.xlsx`：旧数据（含「补全后的请求」真值）
- `data/new.csv`：新数据
- `data/trace_query.json`：Trace 查询条件（环境 / OpenID / 时间窗；模拟器 userId 变了时改这里）
- `data/trace_ch.env`：ClickHouse 凭证（**勿提交**；从 `data/trace_ch.env.example` 复制）

## ClickHouse 取数（仅 UAT）

Trace 已改为直连 ClickHouse，**当前仅注册 `uat` → 库 `otel_uat`**，不查询生产库。

```bash
# 1. 安装依赖
pip3 install -r requirements.txt

# 2. 配置凭证（gitignored）
cp data/trace_ch.env.example data/trace_ch.env
# 编辑 CH_HOST / CH_PORT / CH_USER / CH_PASSWORD

# 也可 export CH_HOST=... CH_PASSWORD=...
```

以后若要加 prod：在 `scripts/trace_envs.py` 的目录里新增一项（如 `otel_prod`），并在表单下拉启用；**默认不要启用**。

## 跑一遍

```bash
python3 scripts/compare_gto_requests.py \
  --old data/old.xlsx \
  --new data/new.csv \
  --shots "/Users/xixi/Downloads/手牌重命名" \
  --outdir output \
  --trace-env uat
```

`data/trace_query.json` 存在时会自动加载（也可用 `--trace-config` / `TRACE_CONFIG` 指定）。证据页会公布本次实际用到的查询条件。

### 页面填写（推荐）

```bash
# 1. 启动本地服务（写配置；证据页「现场查 Trace」经此代理打 CH）
python3 scripts/trace_config_server.py

# 2. 浏览器打开
#    http://127.0.0.1:8766/          （管理入口）
#    或 output/trace_query.html
```

填好 **环境（UAT）** / OpenID / 开始结束时间后点「保存到项目」。证据页打开时会：

1. 读取嵌入的 `traceEnv` / OpenID / 时间窗  
2. 若未配置 cards，自动带入当前手牌 ID（如 `QC5H`）  
3. `POST` 本地 `8766/api/trace-query`（**不访问** 公网 `:7121`），再渲染跨模块表与 JSON  

请用本地服务打开证据页：

```text
http://127.0.0.1:8766/hands/HAND_001.html
```

本地服务未开时，现场查 Trace 会提示无法连接代理。

### 内网分享给同事（推荐）

本机当服务器，同事用浏览器打开你的局域网地址即可看**数据 + 牌桌截图**（截图通过 HTTP 从你本机目录读，无需打包图片）。

```bash
# 1. Trace 查询条件里填好 origShotsDir / shotsDir（本机绝对路径），保存
# 2. 绑定全网卡启动：
python3 scripts/trace_config_server.py --host 0.0.0.0
```

注意：同事机器上看「现场查 Trace」仍会打**同事本机**的 `127.0.0.1:8766`；若需要对方也能现场查，对方需本机起服务并配好 `trace_ch.env`。

截图命名需为：`手牌_usertoken_时间戳.jpg`（如 `QC5H_80edd32e1d0c3583_1783954824311.jpg`）。

## 口径摘要

- 对齐键：`hole_cards_p0`（重复时用 WePoker 时间戳最近邻）
- 真值裁剪：保留到 **P0 最后一次行动之前**；公共牌按决策街截断
- 系统侧字段：`last_step_request`（`last_step_response` 是 GTO 返回，不是请求）
- 忽略：`userId` / `handId` / `eventId` / `gtoType` / 时间戳
- **模块数据链**（`--trace-env`）：以查询结果中**最后一次 `hero_action`** 为锚点，按同索引连线对齐状态引擎 / 网关 / Chess API，各层抽取 `business.request` 写入证据页与 `*.trace.json`

## Trace 查询配置（`data/trace_query.json`）

```json
{
  "traceEnv": "uat",
  "envLabel": "UAT · otel_uat",
  "openId": "693ba6566e468032",
  "openIdMode": "config_first",
  "startTime": "2026-08-03 17:45:00",
  "endTime": "2026-08-05 19:52:00",
  "hands": {
    "QC5H": { "openId": "……", "startTime": "……", "endTime": "……" }
  }
}
```

| 字段 | 含义 |
|---|---|
| `traceEnv` / `envLabel` | ClickHouse 环境（当前仅 `uat`）；旧字段 `api` 仅兼容读取后默认落到 uat |
| `openId` | 模拟器/CRM OpenID（可与截图原 userId 不同） |
| `openIdMode` | `config_first`（默认）/ `data_first` / `config_only` |
| `startTime` / `endTime` | 固定时间窗；留空则按决策点 ±pad |
| `origShotsDir` / `shotsDir` | 本机截图目录（内网分享看图用） |
| `hands.<hole_key\|HAND_xxx>` | 单手覆盖 openId / cards / 时间 |

CLI：

| 参数 | 含义 | 默认 |
|---|---|---|
| `--trace-env` / `TRACE_ENV` | 环境 id（如 `uat`） | 配置 `traceEnv`，否则 `uat` |
| `--trace-config` / `TRACE_CONFIG` | 查询条件 JSON | `data/trace_query.json` |
| `--trace-open-id` / `TRACE_OPEN_ID` | CLI 兜底 openId | 空=用配置 |
| `--trace-start` / `--trace-end` | CLI 固定时间窗 | 空=用配置 |
| `--trace-pad-minutes` | 时间半宽（分钟） | 15 |
| `--skip-trace` | 跳过 Trace 拉取 | 关 |

`--trace-api` 已废弃（忽略）。

## 输出

| 文件 | 含义 |
|---|---|
| `output/index.html` | 总览指标 + 问题分类 + Top 失败 + 可筛选手牌表 |
| `output/hands/HAND_xxx.html` | 正确值 / 旧版 / 新版对照 + Trace 查询条件 + 模块链 |
| `output/hands/HAND_xxx.trace.json` | 各层 `business.request` 与本次查询条件 |
| `output/summary.json` | 机器可读指标与改进建议 |
| `output/diff_table.csv` | 扁平差异表 |
| `output/REPORT.md` | 文字摘要 |

### 人工录入数据（不会被版本更新清掉）

总览「全部手牌」里的 **Bug 状态 / 负责人 / 备注** 存在 `data/hand_bugs.json`：

- 与 `output/` 对比报告分离；重跑 `compare_gto_requests.py`、重生证据页/总览页都**只读不写**该文件
- 保存时与已有记录**合并**（页上没有的手牌记录会保留）
- 每次保存前自动写 `data/hand_bugs.json.bak` 备份

## 数据问答

管理台侧栏「数据问答」（`/chat`）。只读数据服务包成 stdio MCP（`scripts/data_mcp_server.py`），聊天时由模型自己决定调用跑批、正确值、Bug 备注、Trace、fusion。

```bash
cp data/chat.env.example data/chat.env
# 填写 CHAT_BASE_URL / CHAT_API_KEY / CHAT_MODEL（OpenAI 兼容）
python3 scripts/trace_config_server.py
# http://127.0.0.1:8766/chat
```

`data/chat.env` 含密钥，不要提交。Cursor 也可把同一个 MCP 进程配成 stdio 服务。

## 数字好友桌质量站

代码全部在 `e2e-quality-station/`。拷到另一台电脑时拷这个文件夹。本仓库里启动：

```bash
./e2e-quality-station/start.sh
```

页面数据写在 `output/e2e-quality/`。说明见该目录 README。

