# MCP 自动化测试步骤

从「专项原始用例」到「API / UI 自动化跑通、看报告」的固定流程。  
原始用例以仓库内 `testdata/mcp/source/MCP专项测试用例_10月26.xlsx` 为准（10 月 26 格式）。

---

## 0. 文档与文件分别是什么

| 文件 | 作用 |
|------|------|
| `testdata/mcp/source/MCP专项测试用例_10月26.xlsx` | 人写的专项原始用例（含操作步骤、预期结果） |
| `scripts/build_mcp_auto_cases.py` | 原始表 → 自动化 steps / requests 表 |
| `MCP自动化步骤用例_10月26.xlsx`（Downloads 或本地生成） | pytest 实际读取的自动化用例 |
| `automation/.env` 里 `MCP_CASES_XLSX` | 指向上述自动化表 |

本专项测的是 **MCP 工具返回对不对**，不是先测 Agent 口语。UI 自动化另跑，只核最终回答里的数据。

---

## 1. 写 / 改原始用例（MCP 专项）

Sheet：`MCP专项`（表头在第 2 行）。

### 必填列

编号、分组、标题、所属模块、优先级、状态、前置条件、操作步骤、预期结果、备注。

人工执行记录列（异常截图、mcp返回原文等）转换时忽略。

### 预期结果怎么写（重要）

1. **按真实 MCP 顶层字段写**，不要写产品别名里对不上的键。常见对应：

   | 工具 | 应用核对的字段 |
   |------|----------------|
   | `tool_get_user_overview` | `session_count` / `hands` / `profit_bb` / `recent_sessions` |
   | `tool_list_user_sessions` | `session_count` / `sessions[]`（含 `profit_bb`） |
   | `tool_find_hands` | `matched_count` / `hands[]` |
   | `tool_get_hand_detail` | `hand` |
   | `opponent_profile` | `vpip` / `pfr` / `hands_vs_hero` 等扁平字段 |
   | `tool_query_user_metrics` / `query_metrics` | `data` |

2. **多工具分步写【核心】**，例如：

   ```text
   ● 必须调用：
   1）tool_list_user_sessions …
   2）tool_find_hands …

   【核心·场次清单】… sessions …
   【核心·找牌】… hands …（不要把 sessions 字段套到找牌返回上）
   【数据基准】…
   ```

3. **【数据基准】和前置、步骤一致**（有没有输场、验场级负号还是验手牌负号，要写清）。

4. 状态含「阻塞」的用例，转换后会标 `skip`，默认不跑 API。

---

## 2. 转成自动化用例表

在仓库根目录：

```bash
python3 scripts/build_mcp_auto_cases.py \
  --source testdata/mcp/source/MCP专项测试用例_10月26.xlsx \
  --out "$HOME/Downloads/MCP自动化步骤用例_10月26.xlsx"
```

脚本会同时写入：

- `testdata/mcp/MCP自动化步骤用例_10月26.xlsx`（本地生成，gitignore）
- `automation/data/MCP自动化步骤用例_latest.xlsx`（同上）

产出 sheet：`readme` / `config` / `cases` / `steps` / `requests` / `metrics`。  
pytest API 主要用 `requests`（`enabled=Y`）；UI 用 `cases` 里有问题的行。

断言表达式按工具生成：场次 → `sessions`，找牌 → `hands`，避免跨工具套字段。

---

## 3. 配置环境

```bash
cd automation
cp .env.example .env
# 填写 MCP_TOKEN、MCP_BASE_URL
# MCP_CASES_XLSX 指向刚生成的自动化表，例如：
# MCP_CASES_XLSX=/Users/你/Downloads/MCP自动化步骤用例_10月26.xlsx
# MCP_OPEN_ID / UI_OPEN_ID 与用例前置条件一致
```

---

## 4. 跑 API 自动化

```bash
cd automation
source .venv/bin/activate   # 若尚未建环境见 README

./scripts/run_api.sh smoke   # 冒烟
./scripts/run_api.sh         # 全量 enabled=Y
```

---

## 5. 跑 UI 自动化（可选）

与 API 同一张 cases 表；只核模型最终回答数据，不核工具名。

```bash
./scripts/run_ui.sh smoke          # 前 3 条
./scripts/run_ui.sh smoke headed   # 看得见浏览器
./scripts/run_ui.sh                # 全量
```

关键步骤截图在 `reports/ui_chat_turns/`，并挂 Allure 步骤。

---

## 6. 看结果

```bash
./scripts/serve_reports.sh
```

打开门户 → 执行历史 → Excel 网页 / Allure。  
每次 Allure 只含当次运行（跑前会清 `allure-results`）。

判失败时：

- API：看该步 `tool_name` 与 `assert_expr` 是否匹配真实返回键  
- UI：看「响应答复 / 模型回答」是否覆盖【核心】【数据基准】里的数据点  

---

## 7. 推荐检查清单（每改一版原始表）

1. 改完 `testdata/mcp/source/…xlsx` 的预期结果  
2. 重新执行第 2 步转换  
3. 确认 `.env` 的 `MCP_CASES_XLSX` 指向新自动化表  
4. `./scripts/run_api.sh smoke` 过关键路径  
5. 需要时再全量 / UI  

---

## 相关入口

- 总说明：`automation/README.md`  
- 转换脚本：`scripts/build_mcp_auto_cases.py`  
- 上传门户转换：仍走同一套 `convert_workbook`（与 CLI 同一逻辑）
