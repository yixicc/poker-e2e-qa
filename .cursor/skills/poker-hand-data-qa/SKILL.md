---
name: poker-hand-data-qa
description: >-
  Audits poker hand test data and GTO/HandV2 payloads for Texas Hold'em
  legality, pot accounting, and field consistency. Use when
  checking 好友桌用例 CSV, auto_json, HandV2, gameInfo, actionSequence,
  result.total_pot, pots.players, 底池不闭合, 最小加注, 32hands_gto,
  or when the user asks to 排查/核对/验收 a new batch of hand JSON or Excel.
  Do not use to reconstruct a 手数对账 Excel from WePoker video
  (use wepoker-hand-excel).
---

# 牌局数据排查

新来一批牌局 / 用例数据时按本流程做。先定口径，再分层扫，**先出清单再改**。改完必须重扫校验合法。

从视频**新造**黄金集形状的正确值，用 [poker-golden-from-video](../poker-golden-from-video/SKILL.md)。从 WePoker 录像出手数对账表，用 [wepoker-hand-excel](../wepoker-hand-excel/SKILL.md)。本 skill 只核已有 JSON / Excel。

## 0. 定口径（必做）

先看样本里 `amount` 和有没有 `result`：

| 形态 | 识别 | `amount` 含义 |
|---|---|---|
| 好友桌 CSV `auto_json` | 有 `actions` / `net_won_chips`，常无 `result.pots` | **这一口新推进去的筹码** |
| HandV2 / GTO | 有 `gameInfo.actionSequence` + `result` | **当前街累计投入** |

认错口径后面全是误报。盲注/前注/Straddle 若不在动作序列里，投入要另加。Excel 把 `1/2`、`5/10` 显示成日期不当成牌局错误。

OCR/视频辅助时：OCR 底池常显示「底池 + 未跟注下注」，**不要用 OCR 最大值直接当 `total_pot`**；OCR 板面要按 Hero 手牌过滤，否则易混入邻手帧；翻前结束但末帧有公共牌，常是下一手污染。

详细字段与问题清单见 [reference.md](reference.md)。

## 1. 排查顺序（不要跳层）

复制进度：

```
- [ ] 0 口径（增量 vs 累计；有无 result）
- [ ] 1 德州规则
- [ ] 2 底池与结算（有 total_pot 才做）
- [ ] 3 牌面与筹码字段
- [ ] 4 仅在用户要求修改时才改；改完重跑 1–3
```

**第 1 层 · 德州规则**  
按街还原水位、最小加注、谁还能动。查：fold/all-in 后不再动；面对下注不能 check；raise 必须抬高水位；无人下注应为 bet 不是 raise；轮次结束才能进下一街；有 Straddle 时从 Straddle 左手开始。加注疑似写错但实为 call（raise 未抬高水位）也在此层。

**第 2 层 · 底池**  
每人投入 = 前注 + 各街最后累计。多路 all-in 时按 reference.md 的边池拆分算法逐档算，最后一条街若有未跟注，**扣掉再比** `result.total_pot`。  
查：缺 `result`（缺 showdown/winners/total_pot/pots）；已 fold 却进 `showdown_players`；`pots.players` 不得写成全桌（见下）；`sum(pots.amount) ≠ total_pot`；把赢家**净赢**写成 `total_pot`/`pots[].amount`（净赢 = 底池 − 本人投入，不是池额）。

**第 3 层 · 静态字段**  
已知手牌 + 板面不重复；P0 手牌与摊牌牌一致；`finalChips` 齐（缺失即报）且全桌 `Σ(finalChips − initChips) = 0`（**含 ante**，≠0 报；多手相邻同名玩家 init ≠ 上手 final 多为买入/离桌/重坐，不算错）；点数统一（`TC` 不要混 `10C`）。

## 2. `pots.players` 应写成什么

**这一层池里还有资格赢的人**（未弃、且投入覆盖这一层）。`winners` ⊆ `players`。

- 收池无人摊牌：只写赢家，如 `["P7"]`
- 两人摊牌一个主池：写还在池里的两人，如 `["P0","P4"]`
- 边池：只写参与那一层的人，不要写全桌

不是「坐过这桌的人」，也不是「扔过死钱的人」。

## 3. 修改原则（仅用户要求改时）

- 不改用例名。
- 合法且满足描述要求：跟注拉锯要用 call 收尾，不要互推全下；夹击要 3 人且 Hero 5-Bet；CR 要有 check-raise；弃牌局 Hero 先 bet 再 fold。
- 不要用「Hero 最后一步」回写 `行动标识`（会把跟注/加注/下注改成全下）。
- 源文件默认不动，输出到新文件，除非用户明确要改源。

## 4. 怎么汇报

先结论（有无问题、几类、几手），再举例落到**字段路径**。用户要表格时列：手牌、错误原因、报文（出错字段标出）、能确定则写改后值。

抽 1 手人工对口径后再批量扫。

## 5. 验收

- 规则扫描 0
- 有 `total_pot`：按底池拆分算法，返还未跟注后的投入 = `total_pot`；`sum(pots.amount) = total_pot`；无「净赢当池额」
- `pots.players` 不含已弃牌；无人既 fold 又摊牌
- 有 `finalChips` 则全桌 `Σ(finalChips − initChips) = 0`（含 ante；相邻手 init 链不算错）
