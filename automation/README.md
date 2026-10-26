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

未装 allure CLI 时，仍可看 `reports/report.html`（pytest-html）。不想自动弹浏览器时：`ALLURE_OPEN=0 ./scripts/run_api.sh`

## 配置说明

| 变量 | 含义 |
|---|---|
| `MCP_BASE_URL` | MCP 入口，如 `https://xxx.ngrok-free.app/mcp` |
| `MCP_TOKEN` | Bearer token（不要提交 git） |
| `MCP_OPEN_ID` | 默认 open_id（郑秀雨） |
| `MCP_CASES_XLSX` | 自动化 Excel 路径 |
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
