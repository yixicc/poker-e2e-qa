---
name: wepoker-hand-excel
description: >-
  Reconstructs a WePoker recording into the 手数对账 Excel (房间/桌号/分段/手牌/公牌/Hero筹码/切局/识别).
  Use when the user asks to 从视频生成excel, 完整合成, 手数表, 手数对账, 手牌公牌,
  漏识别, 桌号, session 对账, or to continue a handed-off WePoker video job.
  Do not use for golden-set JSON (poker-golden-from-video) or auditing existing
  HandV2/auto_json (poker-hand-data-qa).
---

# WePoker 录像 → 手数对账表

从录像还原**每一手 Hero 底牌 + 公牌 + 桌号 + 筹码**，写成一张 Excel。先看画面，再对 pipeline。禁止编牌。

未完成场次先读 [handoff.md](handoff.md)。画面几何、拆手规则、Excel 列见 [reference.md](reference.md)。识牌函数见 [scripts/wepoker_cards.py](scripts/wepoker_cards.py)。

```
- [ ] 0 确认这是哪一场（片头桌号 ≠ 上一场就当新场）
- [ ] 1 抽帧：段首没有底牌/公牌就 +10s，直到读到或片尾
- [ ] 2 识 Hero 两张底牌、公牌 0/3/4/5、桌号、Hero 筹码
- [ ] 3 按牌面切手；一段里两局要拆成两行
- [ ] 4 写 Excel；output/ 与 xlsx 不进 git
```

## 0. 先定性

输入可能是：

| 输入 | 做法 |
|---|---|
| 一条 `完整合成.mp4` | 本地抽帧，按时间切手 |
| UAT `sessionID` + 分段 mp4 | 每段单独抽，再用 `segmentId` 填「分段」 |
| 已有 `frames/` | 不要重下；接着 OCR / 拆手 |

**抽 1 帧看桌号。** 六位数在桌心水印（如 `145588`），不是昵称「日月××」。桌号和上一场不同就是另一场，不要复用上一场的 Excel / `session_meta`。

WePoker **四色牌**：S 黑、H 红、D 蓝、C 绿。点数 `T` 不要写成 `10`。

## 1. 抽帧

- 分辨率常见 `512×1088`。ffmpeg 用 `imageio_ffmpeg.get_ffmpeg_exe()`。
- 整场片：`fps=0.1`（每 10 秒一帧）。分段片：段首一帧；没有底牌/公牌则 `-ss` 再 +10s，直到读到或该段结束。
- 分段片的 `_b.jpg` 是**片尾**（`dur-1.4s`），不是 0.4 秒。按真实时间排序。
- 微信聊天、补码弹窗、等待下一手：这一帧不当成牌面。

## 2. 识牌（不要发明新检测器）

用 [scripts/wepoker_cards.py](scripts/wepoker_cards.py) + [scripts/ocr_vision.swift](scripts/ocr_vision.swift)（macOS Vision）。

**禁止** `白像素>205` 当牌面：红心 JPEG 发灰，会整场漏牌。用「亮度>90 且非绿绒」。

- Hero 底牌：画面底部头像下两张。
- 公牌：桌心横排 3/4/5 张。
- 花色看牌面内部油墨，绿边当桌布丢掉。
- OCR 点数：彩色 rank 图 + 二值化 `_rb` + 整张牌，三者谁读到用谁。
- 桌号 / 倒计时：桌心水印 OCR。Hero 筹码：底部「高牌/对子」下方数字。

段首没有就往后延 10 秒再截，底牌和公牌都这样。

## 3. 切手

新手开始：底牌换成另一对（不是花色抖），或公牌清掉后发出**对不上前缀**的新翻牌。

仍是同一手：翻牌 3 张变成转 4 / 河 5（后帧包含前帧前缀）。

不要拆：`C↔S`、`6↔9` 的 OCR 抖动；中间一帧被聊天挡住。合并时保留更长的公牌、先读到的底牌。

**一段视频里打了两局**：Excel 拆成两行，同一 `segmentId`（或同一时间片），「切局是否正常」= 否，异常原因写「同一切片第 N 局」。

不算手：纯等待、补码弹窗、换桌动画。入座带入和中途补码要分开，不要把两次 2000 加成 4000。

## 4. Excel

两张表：**汇总** + **手数对账**。对账列必须是：

`房间, 桌号, 段号, 分段, 手牌, 公牌, hero初始筹码, hero结束筹码, 切局是否正常, 是否识别到, 异常原因`

- 房间：按桌号切换记 桌1 / 桌2（不要用桌名）。
- 分段：有 traces 就写 `segmentId` UUID；只有整场片就写 `mm:ss–mm:ss`。
- 手牌：`4S 7D` 这种两张。没有就空，不要写 `H001`。
- 公牌：打到哪条街写到哪；翻前空。
- 是否识别到：有 pipeline 时用数据处理 SUCCESS；纯录像真值表则「读到两张底牌」= 是。

汇总（有 pipeline 时）：

```
真值手数 G = 录像里实际德州手数（扣等待/补码/换桌；一段两局算 2）
识别到 S = 入库唯一手
漏 = G − 命中
多 = S − 命中
```

Hero 盈亏：`离桌筹码 − 入座带入 − 中途补码`。

写到 `~/Downloads/<场次名>_手数表.xlsx`。不要提交 `output/` 和 xlsx。

## 和别的 skill 的边界

- 要 `actionSequence` / `result.total_pot` 黄金 JSON → [poker-golden-from-video](../poker-golden-from-video/SKILL.md)
- 已有 JSON 查规则/底池 → [poker-hand-data-qa](../poker-hand-data-qa/SKILL.md)
