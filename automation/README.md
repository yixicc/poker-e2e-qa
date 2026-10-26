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

生成/更新用例 Excel（仓库脚本）：

```bash
python3 ../scripts/build_mcp_auto_cases.py
```

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

### 跑 UI（需先开管理台 + UI_ENABLED=1）

```bash
# 另开终端
python3 ../scripts/trace_config_server.py

# .env 中 UI_ENABLED=1
./scripts/run_ui.sh
```

### Allure 可视化报告（自动生成）

用 `./scripts/run_api.sh` / `run_ui.sh` 跑完后会**自动**：

1. 写出 `reports/allure-results/`（原始结果）
2. 若已安装 allure CLI → 生成 `reports/allure-report/index.html` 并尝试用浏览器打开

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

### 常驻 + 内网访问

默认监听 `0.0.0.0:8767`，同事用脚本打印的 **内网 IP** 访问（如 `http://192.168.110.220:8767/`）。

```bash
# 临时启动
./scripts/serve_reports.sh

# 安装常驻（登录后自动开）
./scripts/install_lan_portal.sh
# 卸载
./scripts/uninstall_lan_portal.sh
```

说明：仓库若在 `Downloads` 下，macOS 不允许 LaunchAgent 读该目录，安装脚本会改用**登录项**；更稳可把项目挪到 `~/Projects/` 后再装（崩溃自动拉起）。防火墙需放行 8767。

## 配置说明

| 变量 | 含义 |
|---|---|
| `MCP_BASE_URL` | MCP 入口，如 `https://xxx.ngrok-free.app/mcp` |
| `MCP_TOKEN` | Bearer token（不要提交 git） |
| `MCP_OPEN_ID` | 默认 open_id（郑秀雨） |
| `MCP_CASES_XLSX` | 命令行要跑的自动化 Excel。配了就用它，上传不会覆盖 |
| `UI_ENABLED` | `1` 才跑 UI |
| `UI_BASE_URL` | 管理台地址，默认 `http://127.0.0.1:8765` |

## 用例从哪来

- Excel：`cases` + `requests`（由 `scripts/build_mcp_auto_cases.py` 生成）
- API：每个 `enabled=Y` 的 request 行 = 1 条 pytest
- UI：先用冒烟覆盖「数据问答」页；可按 `cases.user_question` 继续扩展

## 报告里有什么

- case_id / tool / 优先级（Allure 标签）
- 请求 Body、原始 SSE/JSON 响应
- 失败时 UI 截图（Playwright 默认）
- **Excel 自动导出**（跑完即有）：
  - `reports/MCP执行结果_YYYYMMDD_HHMMSS.xlsx`
  - `reports/MCP执行结果_latest.xlsx`（始终覆盖为最新）
  - Sheet「执行明细」：原用例字段 + 自动化参数 + 返回结果
  - Sheet「汇总统计」：通过率 / 按优先级 / 按工具 / 按分组
