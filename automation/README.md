# Poker MCP / UI 自动化测试

API（直连 MCP Streamable HTTP）+ UI（Playwright）+ Allure/HTML 报告。

## 目录

```
automation/
├── config/           # 环境配置
├── common/           # McpClient、Excel 加载、断言、报告附件
├── api/              # API 用例（Excel 驱动）
├── ui/               # UI 用例（Page Object）
├── scripts/          # 一键跑脚本
├── reports/          # 报告输出（gitignore）
├── .env.example
├── pytest.ini
└── requirements.txt
```

## 快速开始

```bash
cd automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # 仅 UI 需要

cp .env.example .env
# 编辑 .env：填 MCP_TOKEN；确认 MCP_BASE_URL / MCP_CASES_XLSX
```

生成/更新用例 Excel（仓库脚本，默认读 10 月 26 原始专项表）：

```bash
python3 ../scripts/build_mcp_auto_cases.py \
  --source "/Users/xixi/Downloads/MCP专项测试用例_10月26.xlsx" \
  --out "/Users/xixi/Downloads/MCP自动化步骤用例_10月26.xlsx"
```

原始表不再有「正确结果(预期)」；断言描述从「预期结果」里的【核心】【数据基准】抽出。状态含「阻塞」的用例会标 skip。

### 只跑 API 冒烟

```bash
./scripts/run_api.sh smoke
# 或
pytest -m "api and smoke" --html=reports/report.html --self-contained-html
```

### 跑 Excel 全量 API（enabled=Y）

```bash
./scripts/run_api.sh
```

### 只跑 UI 冒烟

和 API 共用同一张 cases 表，只问前 3 条。地址写在 `automation/.env`（`UI_ENABLED=1`、`UI_BASE_URL`、`UI_CHAT_PATH`），不要把这些行贴进终端。

```bash
./scripts/run_ui.sh smoke
```

要看着浏览器操作，加上 `headed`：

```bash
./scripts/run_ui.sh smoke headed
```

### 跑 UI 全量

同一张表，按顺序全部提问。模型回答原文写进结果表右侧「响应答复」，并按预期结果描述核对数据。不核对调用了哪个工具。单轮原文和关键步骤截图（已输入问题、已发送、回答已展示）落在 `reports/ui_chat_turns/`，截图同时挂在 Allure 对应步骤上。

```bash
./scripts/run_ui.sh
./scripts/run_ui.sh headed
```

`headed` 会弹出浏览器窗口。不加则是无头模式。`smoke` 和 `headed` 可以一起写，顺序不限。也可以在 `.env` 写 `UI_HEADED=1`，之后每次都有界面。

### Allure 可视化报告（自动生成）

用 `./scripts/run_api.sh` / `run_ui.sh` 跑完后会**自动**：

1. 清空后重写 `reports/allure-results/`，这份 Allure 只含本次 API 或本次 UI，不会把上一次的结果叠进来
2. 若已安装 allure CLI → 生成 `reports/allure-report/index.html`，并复制到该次历史记录的 Allure 链接

首次需安装 Allure 命令行（只需一次）：

```bash
brew install allure
```

也可以手动再生成 / 预览：

```bash
./scripts/gen_allure.sh
allure serve reports/allure-results
```

未装 allure CLI 时，门户页里 Allure 会显示「未生成」，仍可下载 Excel、打开 pytest-html。

跑完会启动 HTTP 门户（默认绑 `0.0.0.0:8767`，本机 + 内网可访问）。  
**不要用 file:// 直接打开 Allure**，浏览器会报 Failed to fetch。

```bash
./scripts/run_api.sh smoke
# 或只重新托管已有报告：
./scripts/serve_reports.sh
```

### 门户：命令行跑测 vs 上传

首页为**执行历史列表**（每次 `run_api` 一行，可回溯 Excel/HTML/Allure）。

- **看记录** `./scripts/serve_reports.sh`：只打开结果页，不跑测，不会新增一行
- **跑测** `./scripts/run_api.sh`：直接用 `.env` 的 `MCP_CASES_XLSX`（已指定目录下的那份），不必先上传。跑完才会在历史里多一行，归档在 `reports/runs/{时间}/`
- **右上角「上传测试用例集」**：可选。只把一份新的原始 xlsx 转成自动化表并另存，不替换命令行正在用的文件

不想自动弹浏览器：`REPORT_OPEN=0 ./scripts/run_api.sh`  
换端口：`REPORT_PORT=8770 ./scripts/run_api.sh`  
仅本机：`REPORT_HOST=127.0.0.1 ./scripts/serve_reports.sh`

### 展示服务 vs 跑测（分开）

| | 展示服务 `:8767` | `run_api` / `run_ui` |
|---|---|---|
| 职责 | 只看历史结果、Allure、上传转换 | 只跑 pytest、写 `reports/runs/` |
| 何时开 | **开机后开一次，一直挂着** | 需要时再跑 |
| 互相 | 跑测会刷新门户 HTML，**默认不杀、不重启**展示进程 | 不依赖你是否刚开浏览器 |

```bash
# 第一次 / 发现打不开时：启动展示服务（已在跑则复用）
./scripts/serve_reports.sh

# 登录后自动开（推荐）
./scripts/install_lan_portal.sh

# 停止展示服务
./scripts/stop_portal.sh
# 强制重启展示服务
REPORT_FORCE_RESTART=1 ./scripts/serve_reports.sh
```

默认监听 `0.0.0.0:8767`。仓库若在 `Downloads`，macOS LaunchAgent 可能读不了，安装脚本会改用登录项；更稳可挪到 `~/Projects/`。防火墙需放行 8767。

## 配置说明

| 变量 | 含义 |
|---|---|
| `MCP_BASE_URL` | MCP 入口，如 `https://xxx.ngrok-free.app/mcp` |
| `MCP_TOKEN` | Bearer token（不要提交 git） |
| `MCP_OPEN_ID` | 默认 open_id（郑秀雨） |
| `MCP_CASES_XLSX` | 命令行要跑的自动化 Excel。配了就用它，上传不会覆盖 |
| `UI_ENABLED` | `1` 才跑 UI |
| `UI_HEADED` | `1` 时弹出浏览器窗口，默认无头 |
| `UI_BASE_URL` | 聊天页地址，默认 `http://192.168.110.147:3100` |

## 用例从哪来

- Excel：`cases` + `requests`（由 `scripts/build_mcp_auto_cases.py` 生成）
- API：每个 `enabled=Y` 的 request 行 = 1 条 pytest
- UI：和 API 同一张 cases 表。`./scripts/run_ui.sh smoke` 只问前 3 条，`./scripts/run_ui.sh` 按顺序全部提问

## 报告里有什么

- case_id / tool / 优先级（Allure 标签）
- 请求 Body、原始 SSE/JSON 响应
- 失败时 UI 截图（Playwright 默认）
- **Excel 自动导出**（跑完即有）：
  - `reports/MCP执行结果_YYYYMMDD_HHMMSS.xlsx`
  - `reports/MCP执行结果_latest.xlsx`（始终覆盖为最新）
  - Sheet「执行明细」：左侧原用例列（cases/requests），右侧追加执行列（请求报文 / 响应答复 / 执行时间ms / 执行结果 / 结果分析）
  - Sheet「汇总统计」：通过率 / 按优先级 / 按工具 / 按分组
