---
name: poker-golden-from-video
description: >-
  Reconstructs Texas Hold'em hands from video into the 32-hand golden
  dataset JSON (gameInfo.actionSequence + result) so two agents' outputs
  are program-comparable. Use when the user asks to 从视频还原牌局, 按黄金集
  schema 输出, 32hands_gto, 修改后的请求, 正确值, or to fill
  actionSequence / total_pot from a poker recording. Do not use for
  auditing an existing JSON batch (use poker-hand-data-qa), or for a
  手数对账 Excel from WePoker video (use wepoker-hand-excel).
---

# 从视频还原黄金集牌局

输入是录像（或逐帧桌面）。输出是**一手一份**黄金集 JSON。只写牌局事实，不写视频路径、帧号、待审标记。

看不清行动或金额：该手不要当可比对正确值输出。`name` 可 `""`；看不见的 `holeCards` 必须 `null`，禁止编牌。

产出后若要做合法性扫描，用 [poker-hand-data-qa](../poker-hand-data-qa/SKILL.md)。从 WePoker 录像出手数对账表（房间/桌号/手牌/公牌），用 [wepoker-hand-excel](../wepoker-hand-excel/SKILL.md)。

## 流程

```
- [ ] 切手（BTN 移动 / Hero 手牌换 / 公牌清零 / 底池重置）
- [ ] 逐手填下面这份对象
- [ ] 类型与枚举自检（字符串金额、T 不是 10、ALL-IN）
- [ ] 看不清的手剔除，不进可比对集合
```

## 对象

```text
{
  userId: string                       // 录像用户 token；比对可忽略
  gtoType: string                      // 固定 "3"；比对可忽略
  gameInfo: {
    ante: string                       // 数字字符串，无前注写 "0"
    smallBlind: string
    bigBlind: string
    straddle: string                   // 无 straddle 必须 "0"，禁止 null / 0
    handId: string                     // {userId}.texas.{app}.{本手起始毫秒}；比对忽略
    eventId: string                    // {handId}:HeroDoingEvent:0:{本手起始毫秒}；比对忽略
    communityCards: string[]           // 只保留实际打到的街：翻前[] 翻后3 转4 河5
    players: [
      {
        seat: string                   // 桌上座位号 P0…Pn；P0 必须是 Hero（录像用户）
        position: string               // 见位置表
        holeCards: string[] | null     // Hero 必填 2 张；其余仅摊牌可见时填，否则 null
        initChips: string              // 本手开始筹码
        finalChips: string             // 本手结束筹码
        name: string                   // 看不清写 ""
      }
    ]
    actionSequence: [                  // 时间序完整一手；禁止写发盲/ante
      {
        seat: string
        street: string                 // PREFLOP | FLOP | TURN | RIVER
        actionType: string             // FOLD | CHECK | CALL | BET | RAISE | ALL-IN
        amount: string                 // 该玩家本街累计投入（不是这一口增量）
      }
    ]
  }
  result: {
    total_pot: string                  // 未跟注已退回后的终池
    winners: string[]                  // 座位号
    showdown: bool                     // 有人亮牌才 true
    showdown_players: [                // 无人摊牌必须 []
      {
        seat: string
        name: string
        cards: string[]                // 2 张
        status: string                 // show | muck
      }
    ]
    pots: [
      {
        type: string                   // main | side
        amount: string                 // 该层池额，禁止写净赢
        players: string[]              // 该层还有资格赢的人（未弃且投入覆盖该层），禁止写全桌
        winners: string[]              // ⊆ players
      }
    ]
  }
}
```

## 填写规则

**类型**  
盲注、筹码、`amount`、`total_pot`、`pots.amount` 一律数字字符串。牌面 `A/K/Q/J/T/9…2` + `S/H/D/C`，十点必须 `T`，禁止 `10C`。

**座位与位置**  
`P0` = Hero，不是物理 0 号。位置按人数从这张满员表**从前砍**：

`UTG, UTG1, UTG2, LJ, HJ, CO, BTN, SB, BB`

| 人数 | positions |
|---|---|
| 9 | 全用 |
| 8 | 去掉 `UTG2` |
| 6 | `UTG, HJ, CO, BTN, SB, BB` |
| 4 | `CO, BTN, SB, BB` |
| 3 | `BTN, SB, BB` |

BTN 左手是 SB，再左手是 BB，再左手是该人数下的第一个位置（UTG 或 CO）。

**行动**

- 不写 POST_BLIND / ANTE / STRADDLE。
- `amount` = 当街累计。跟注到 220 写 `"220"`，不要写这一口新加的。
- `FOLD` / `CHECK`：本街还没投入过写 `"0"`；SB 翻前弃牌写已投小盲（如 `"10"`）；BB 翻前弃牌写已投大盲（如 `"20"`）。
- 没人下注时的主动投入是 `BET`；有人下注后抬高水位是 `RAISE`；没抬高是 `CALL`。禁止把 call 写成 raise。
- 筹码归零记 `ALL-IN`（连字符，不要 `ALL_IN`），`amount` 仍是当街累计。
- 翻前从 UTG（有 straddle 则从其左手）开始；翻后从 SB 起，已弃过的跳过。
- 街未闭合不得进下一街。`communityCards` 不得带下一手的牌。OCR 底池常含未跟注下注，禁止用屏幕最大值当 `total_pot`。

**结算**

每人投入 = ante + 各街该玩家最大累计 `amount`（fold 常记 0，取本街最大不要取最后一条）+ 序列里没有的盲注/straddle。

最后一街：最高累计 − 第二高 = 未跟注，**退回后再算** `total_pot`。多路 all-in 按投入从小到大分档：

```
第 i 档金额 = (vi − v(i-1)) × (投入 ≥ vi 的人数)
pots[i].players = 投入 ≥ vi 且未弃牌的人
最高档若只有 1 人达到 → 未跟注，不进 pots
```

- `sum(pots.amount) == total_pot`
- 收池无人摊牌：`showdown=false`，`showdown_players=[]`，`pots.players` 只写赢家
- 边池 `type=side`，`players` 只写参与该档的人
- 全桌 `Σ(finalChips − initChips) == 0`（含 ante）

## 程序比对

**忽略：** `userId` `gtoType` `handId` `eventId` `players[].name`

**要比：** 盲注/straddle、`communityCards`、`players` 的 seat/position/holeCards/initChips/finalChips、整段 `actionSequence`、整个 `result`

**先归一再 diff：** `"20"` == `"20.0"`；`ALL_IN` 当成 `ALL-IN`；`10C` 当成 `TC`。  
`actionSequence` 按顺序逐条比 `seat + street + actionType + amount`，区分缺 / 多 / 改写，不要只比长度。
