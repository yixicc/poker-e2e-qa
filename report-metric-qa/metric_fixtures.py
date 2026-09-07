"""每个指标的可执行素材：有效（必须计入）/ 无效（必须排除）。

测试员按这里准备录像或事实层，不要只看公式。
只写测员能录、能传、能对照的素材。切片重复、缺 hand_id、结算打架这类系统脏数据不要写进步骤。
"""

from __future__ import annotations

# 几乎所有场次级指标都要先过这一关
SESSION_EXCLUDE = [
    "用户只围观、自己没有入座的牌局录像",
    "与德州无关的视频（大厅闲聊、其他游戏、空白/黑屏）",
]


def F(
    include: list[str],
    exclude: list[str] | None = None,
    mix: str = "",
    opportunity: list[str] | None = None,
    zero_denom: str = "",
    missing: str = "",
    unit: str = "",
    consistency: str = "",
    conflict: str = "",
    half: list[str] | None = None,
) -> dict:
    ex = list(exclude or [])
    if not any("围观" in x for x in ex):
        for item in SESSION_EXCLUDE:
            if item not in ex:
                ex.append(item)
    return {
        "include": include,
        "exclude": ex,
        "mix": mix
        or "同一场（或同一账号连续两场对照）必须同时有有效素材和无效素材，证明系统会区分，而不是碰巧全算对。",
        "opportunity": opportunity or [],
        "zero_denom": zero_denom,
        "missing": missing,
        "unit": unit,
        "consistency": consistency,
        "conflict": conflict,
        "half": half or [],
    }


# ---------------------------------------------------------------------------
# 123 指标素材。include/exclude 写「准备什么」，不写「按公式算」。
# ---------------------------------------------------------------------------

FIXTURES: dict[str, dict] = {
    "video_duration": F(
        include=[
            "任意能上传成功的录像即可，不区分围观/入座；用播放器记下精确到秒的时长（例：12 分 30 秒 = 750 秒，不要用整分钟）",
        ],
        exclude=[
            "时长正好为 0 秒的视频（本指标不按「无效素材」排除，0 是单独一条边界）",
        ],
        mix="视频时长不测有效/无效计入，只测：上传 0、超长、单位到秒。",
        missing="文件能上传但读不到时长（元数据损坏/没有 duration），不要和「时长=0」混成一条。",
        unit="字段单位是秒。播放器 12:30 必须写成 750 或 12:30，不能四舍五入成 12 分钟。",
        consistency="只对播放器/文件属性里的时长，不要用手牌数或行动链反推。",
    ),
    "total_hands": F(
        include=[
            "本场录像里每一手完整牌：Hero 入座、有发牌；翻前弃、进翻后、摊牌都各算 1",
        ],
        exclude=[
            "用户只围观、自己没入座的牌",
            "另一场牌局里的手（另录一场对照，不能算进本场）",
            "从一手中间开始录或中途停录、看不全完整一手",
        ],
        mix="一场若干完整手；另用围观或另一场做对照。",
        consistency="手数列表行数必须等于总手数。",
    ),
    "hands_played": F(
        include=[
            "主动 limp；主动 open；翻前跟 open 被 3bet 弃（没进翻后）；翻前加注对手全弃（没进翻后）",
            "大盲被加后跟/再加；大盲无人加注过牌看翻牌；翻前 all-in 有人跟仍发翻牌",
            "只交盲即弃亏盲；大盲其他人全弃收盲",
            "同一手同时 limp+进翻后+有盈亏，参与只 +1",
        ],
        exclude=[
            "Hero 只自动交盲、翻前直接 fold、没有防守、没进翻后——且产品确认本手不产生「参与」时不算（若有盲注亏损，按清单「产生盈亏即计入」，要算进；两边不一致先记口径待确认）",
            "托管前位系统代弃且盈亏=0（与手动前位弃牌同口径，不算参与）",
            "围观、Hero 未入座",
        ],
        opportunity=[
            "ClubGG托管大盲无人加注系统代过牌看翻牌（算参与，不算 VPIP）",
            "WePoker托管大盲小盲平跟系统代弃亏大盲（算参与，不算 VPIP，算翻前弃牌）",
            "托管小盲系统代弃亏盲（两款通用，算参与，不算 VPIP）",
            "托管被加注系统代弃且有盈亏（两款通用，算参与）",
        ],
        mix="同一场同时放：自愿入池手、盲注防守手、只交盲即弃手。另用围观做对照。",
        consistency="参与手数 ≤ 总手数；每手是否计入必须能在 hands[] 上勾出来。",
        conflict="Skill 更接近自愿入池；需求含盲注防守/进翻后/有盈亏。本条只认需求清单。",
    ),
    "folded_preflop_hands": F(
        include=[
            "Hero 翻前 fold，公牌没有 flop，翻后无 Hero 行动（例：UTG 弃牌、BB 被加后弃牌）",
        ],
        exclude=[
            "Hero 翻前 call/raise 后进翻后，即使后面弃了也不算「翻前弃牌手数」",
            "Hero 翻前 check（大盲无人加注）看到翻牌",
            "围观或未识别 Hero 翻前动作的手",
        ],
        mix="同一场：翻前弃牌手 + 翻前入池后进翻后手 + 大盲无人加注过牌看翻牌。",
    ),
    "postflop_hands": F(
        include=[
            "有翻牌三张公牌的手（Hero 看到 flop）",
            "没有清晰公牌图、但有 Hero 翻后 check/bet/call 等行动记录的手",
        ],
        exclude=[
            "翻前所有人弃牌、没有 flop 也没有翻后行动",
            "围观桌的翻后画面",
        ],
        mix="同一场：进翻后手 + 翻前结束手。",
    ),
    "showdown_hands": F(
        include=[
            "任意街摊牌都算：该街 all-in 且至少一人跟注，双方在该街亮手牌，再发完剩余公牌（翻前→翻/转/河，翻牌→转/河，转牌→河）；河牌有人跟则在河牌亮牌",
            "有 showdown_result、双方（或多方）亮牌、或明确 showdown 标记即计入；按手 +1，不按亮牌人数加倍",
        ],
        exclude=[
            "任意街有人弃牌结束、没有亮牌（未摊牌赢池），包括河牌弃牌收池",
            "翻前 all-in 后无人跟：不发翻/转/河，翻前直接收池——不能因为 all-in 就记摊牌",
            "只有胜负筹码变化、没有任何亮牌/摊牌标记",
            "围观他人摊牌、Hero 未参与",
        ],
        mix="同一场必须覆盖四条街的摊牌正例，以及四条街的弃牌未亮反例。",
    ),
    "participation_rate": F(
        include=["用上面「参与手数」的有效手做分子，用「总手数」的有效手做分母"],
        exclude=["分子混进只交盲即弃（若清单不算参与）或围观手；分母用错成只统计入池手"],
        mix="一场里参与手与未参与手都有，便于手算 hands_played / total_hands。",
        unit="比率；过程用小数，展示按目录。",
        conflict="随 hands_played 分叉：Skill 语义接近 VPIP，需求跟参与手数。只认需求。",
        opportunity=["前位翻前弃牌，盈亏=0。总手数含这一手，参与手数不含这一手"],
    ),
    "preflop_fold_rate": F(
        include=["分子=翻前弃牌手数的有效手；分母=本场总手数"],
        exclude=["把进翻后才弃牌的手算进分子；分母只用参与手数"],
        mix="翻前弃牌手与进翻后手同场。",
        unit="folded_preflop_hands / total_hands",
        opportunity=["翻前跟注或加注后进了翻后。总手数含这一手，翻前弃牌手数不含这一手"],
    ),
    "postflop_entry_rate": F(
        include=["分子=进入翻后的有效手；分母=总手数"],
        exclude=["翻前结束的手进分子；分母改成参与手数"],
        mix="进翻后与翻前结束同场。",
        opportunity=["用户翻前弃牌，不发翻/转/河。总手数含这一手，进入翻后手数不含这一手"],
    ),
    "showdown_rate": F(
        include=["分子=有摊牌/亮牌的手；分母=参与手数（hands_played），不是总手数"],
        exclude=[
            "未参与手出现在分母（按需求分母是 hands_played）",
            "未亮牌赢池算进分子",
        ],
        mix="参与且摊牌、参与未摊牌、未参与 三类同场。",
        conflict="需求/基准分母=hands_played；Skill 分母=total_hands。只认需求。",
    ),
    "total_profit_chips": F(
        include=[
            "本场每手已结算的 Hero 筹码净变化，有赢有亏有打平，最后加总（例：+1200、-800、0）",
        ],
        exclude=[
            "围观桌的输赢",
        ],
        mix="已结算的赢/亏/平同场。",
        unit="筹码整数或约定小数；不要写成 BB。",
        consistency="sum(hands.hand_profit_chips) 必须等于本字段。",
        missing="没有每手结算、也没有可信整场盈亏。",
    ),
    "total_profit_bb": F(
        include=[
            "每手 chips ÷ 该手大盲，再加总（例：手1 大盲 100 赢 200 = +2BB；手2 大盲 200 赢 200 = +1BB；整场 +3BB，不是用场均大盲去除）",
        ],
        exclude=["用整场筹码 ÷ 场均/最后一手大盲", "未准入结算的手"],
        mix="每场一种盲注。换盲注后分别在两个session里按该场大盲换算。",
        unit="BB；内部≥4 位，展示约 2 位。",
        consistency="sum(hand_profit_bb) == total_profit_bb。",
        missing="有手数但没有任何大盲或结算。",
    ),
    "hand_profit_chips": F(
        include=["每一手结束后 Hero 本手筹码净变化，来自结算字段或核验过的 stack 差"],
        exclude=["围观手", "把整场盈亏复用到每一手"],
        mix="赢/亏/平各至少一手，外加一手结算不可用。",
        missing="该手没有结算。",
    ),
    "hand_profit_bb": F(
        include=["该手 chips ÷ 该手 bigBlind"],
        exclude=["用邻手或场均大盲去除", "chips 未准入却算出 BB"],
        mix="两大盲档各一手。",
        unit="BB，按手换算。",
    ),
    "winning_hands_count": F(
        include=["per_hand_profit > 0 的已结算手，哪怕只赢 1 筹码"],
        exclude=["profit = 0 的打平手", "profit < 0", "未结算手"],
        mix="赢、亏、平、未结算 同场。",
    ),
    "losing_hands_count": F(
        include=["per_hand_profit < 0 的已结算手，含只输盲注"],
        exclude=["打平", "盈利", "未结算"],
        mix="赢、亏、平同场。",
    ),
    "breakeven_hands_count": F(
        include=["per_hand_profit 恰好 = 0 的已结算手"],
        exclude=["+1 或 -1 的手", "未结算当 0"],
        mix="打平 + 微赢 + 微亏 + 未结算。",
    ),
    "top_profit_hands": F(
        include=["按单手盈利从高到低取 Top N（例：+150BB、+80BB、+40BB 必须排在前面且带每手盈亏）"],
        exclude=["亏损手", "未结算的手"],
        mix="至少 5 手不同盈利 + 亏损手 + 未结算手；N 不足则有几条出几条。",
        consistency="列表顺序严格按盈亏降序；并列规则稳定。",
        missing="全场没有一手盈利。",
    ),
    "top_loss_hands": F(
        include=["按单手盈亏从低到高取 Top N（亏最多的在前，带每手盈亏）"],
        exclude=["盈利手", "未结算手"],
        mix="多手不同亏损 + 盈利手。",
        missing="全场没有一手亏损。",
    ),
    "profit_concentration_ratio": F(
        include=["算出 Top 3 单手盈亏绝对值之和 / 全场每手盈亏绝对值之和（例：三手大赢大亏拉开整场）"],
        exclude=["用 Top 3 带符号盈亏相加（正负抵消）当分子", "分母漏掉打平以外的手"],
        mix="少数极大盈亏手 + 许多小盈亏手。",
        unit="0~1 或百分比，按目录。",
    ),
    "total_ev": F(
        include=["每手 GTO 返回的 EV 加总（有正有负）"],
        exclude=["没有 EV 返回的手当 0 填进总和", "用实际盈亏冒充 EV"],
        mix="有 EV 的手 + 无 GTO/无 EV 的手。",
        missing="整场没有任何 per_hand_ev。",
    ),
    "per_hand_ev": F(
        include=["该手 GTO 返回的 EV 原值"],
        exclude=["没有 GTO 结果的手", "把整场 total_ev 摊到每一手"],
        missing="该手无 GTO EV。",
    ),
    "actual_vs_ev_gap": F(
        include=["total_profit_bb − total_ev_bb（或筹码口径成对相减），用同一单位"],
        exclude=["一边用 BB、一边用筹码相减", "缺 EV 时用 0 冒充差值"],
        mix="实际盈亏与 EV 明显不一致的一场。",
        missing="缺实际盈亏或缺 EV。",
    ),
    "ev_relation_type": F(
        include=[
            "差值超过「高于期望」阈值的一场（标签：高于期望）",
            "落在接近带内的一场（接近期望）",
            "低于阈值的一场（低于期望）",
        ],
        exclude=["缺 EV 仍打出高于/低于", "阈值边界样本被随机归类"],
        mix="三场对照，或一场内用文档阈值手算应落哪一类。",
    ),
    "luck_direction": F(
        include=["实际明显低于 EV → 运气不利；明显高于 EV → 结果较顺"],
        exclude=["只看输赢不看 EV 就打运气标签", "信息不足仍打「运气不利」"],
        mix="「打得对但输」与「打得差但赢」各有一手支撑。",
    ),
    "decision_impact_direction": F(
        include=["结合 GTO 质量、关键亏损牌、EV 关系后给出的决策影响方向（有依据）"],
        exclude=["没有关键亏损牌也没有质量数据仍给标签"],
        missing="GTO 与盈亏都不足以判断。",
    ),
    "good_decision_bad_result_hands": F(
        include=[
            "该手每一次可判断行动都是「符合GTO」或「基本可接受」，且本手 per_hand_profit < 0",
        ],
        exclude=[
            "任意一次行动是「风险偏高」却因结果亏损被放进列表",
            "决策好但本手盈利",
            "信息不足的手",
        ],
        mix="打对但输、打对但赢、打差且输 三类同场。",
        missing="没有同时满足「质量可接受 + 亏损」的手。",
    ),
    "bad_process_good_result_hands": F(
        include=["该手任意一次行动是「风险偏高」，且 per_hand_profit > 0"],
        exclude=["全程符合 GTO 的盈利手", "风险偏高但本手亏损", "信息不足"],
        mix="过程差但赢、过程差且输、过程好且赢 同场。",
        missing="没有「风险偏高 + 盈利」的手。",
    ),
    "total_decision_points": F(
        include=[
            "Hero 在各街每一次 fold/call/check/bet/raise/all-in，一手多街要分开计（例：翻前 raise + 翻牌 c-bet + 转牌 check = 3 个点）",
        ],
        exclude=[
            "对手的行动",
            "系统自动交盲（不是 Hero 决策）",
            "ClubGG/WePoker 托管代打的 check 或 fold（录屏有托管标识，视同非用户决策，不计入 GTO 决策点）",
            "识别不出动作的空白街",
        ],
        mix="一手多决策 + 一手只自动交盲 + 对手行动很多的手。",
        consistency="决策点列表条数 = 本计数。",
    ),
    "judgeable_decision_points": F(
        include=["已打上 符合GTO / 基本可接受 / 风险偏高 的决策点"],
        exclude=["信息不足的点", "没有实际动作或没有 GTO 返回的点"],
        mix="四类标签各出现至少 1 个点。",
        consistency="三类可判断数之和 = 本字段；+ 信息不足 = 总决策次数。",
    ),
    "gto_matched_count": F(
        include=[
            "实际动作 = GTO 主推荐动作",
            "实际是加注，尺度落在推荐额 ±30% 以内（含刚好 30%）",
        ],
        exclude=[
            "动作相同但加注额超出 ±30%",
            "动作不同但频率 >30%（应算基本可接受，不算符合）",
            "信息不足",
        ],
        mix="首选一致、尺度刚好卡在 ±30% 内外、频率>30% 的非首选 同场。",
    ),
    "acceptable_count": F(
        include=[
            "动作不是 GTO 首选，但该动作频率 >30%",
            "是加注但尺度超出推荐额 ±30%，且仍按口径归到「基本可接受」的样本（按清单：超出 ±30% 走可接受）",
        ],
        exclude=["首选一致的点", "频率 <30% 的偏离", "信息不足"],
        mix="频率刚好 30% 上下各一点（边界必须稳定落在一类）。",
    ),
    "high_risk_count": F(
        include=["不是 GTO 首选，且该动作频率 <30%"],
        exclude=["频率 >30% 的非首选", "首选一致", "信息不足"],
        mix="频率刚好低于/高于 30% 的偏离点。",
    ),
    "insufficient_info_count": F(
        include=[
            "缺实际动作",
            "缺 GTO 返回",
            "行动链或公牌不完整，无法判断",
        ],
        exclude=["四类信息齐全却标成信息不足", "把可判断点算进本计数"],
        mix="信息不足点 + 可判断点同场。",
    ),
    "gto_match_rate": F(
        include=["gto_matched_count / judgeable_decision_points，输出整数百分比"],
        exclude=["分母用总决策次数（含信息不足）", "分母为 0 时输出 0%"],
        mix="可判断点与信息不足点同场。",
        zero_denom="整场没有任何可判断决策点。",
        unit="整数百分比，舍入规则与目录一致。",
    ),
    "acceptable_decision_rate": F(
        include=["(gto_matched + acceptable) / judgeable"],
        exclude=["把风险偏高算进分子", "分母含信息不足"],
        zero_denom="无可判断点。",
    ),
    "high_risk_decision_rate": F(
        include=["high_risk_count / judgeable"],
        exclude=["分母用总决策点"],
        zero_denom="无可判断点。",
        consistency="可接受占比 + 高风险占比，四舍五入前为 100%（展示允许 1 个百分点误差）。",
    ),
    "risk_by_street": F(
        include=["高风险点按 preflop/flop/turn/river 分开计数（例：河牌 3 个、翻前 1 个）"],
        exclude=["把基本可接受算进高风险分布", "没有该街决策却输出 0 冒充「该街很稳」"],
        mix="四条街都有决策，但高风险只集中在河牌。",
    ),
    "risk_by_position": F(
        include=["高风险点按本手 Hero 真实位置汇总（BTN/CO/SB/BB/UTG/MP 等，跟人数映射表）"],
        exclude=["写死六人桌位置名", "空位置输出 0% 冒充没风险"],
        mix="2 人和 6 人桌都有高风险点。",
    ),
    "risk_by_pot_type": F(
        include=[
            "每个高风险点可打多个场景标签，按清单 7 维分别汇总：大底池(决策前底池≥50BB)、多人(≥3人)、盲注防守/前位入池、面对3bet/4bet、面对cbet/check-raise、河牌各节点、All-in或投入≥70%有效筹码",
        ],
        exclude=["一个点只允许一个标签（漏多标签）", "未达 50BB 打上「大底池」", "2 人底池打上「多人」"],
        mix="一手同时满足「大底池 + 河牌被加 + 接近 all-in」的高风险点，必须三个标签都计数。",
    ),
    "actual_action": F(
        include=["该决策点 Hero 真实动作：fold/check/call/bet/raise/all-in 之一，与录像一致"],
        exclude=["对手动作写到 Hero", "看不清时填一个默认 call", "自动交盲写成 call"],
        missing="该点看不清动作。",
        consistency="必须能对上该街 action_sequence 里 Hero 那一步。",
    ),
    "gto_recommended_action": F(
        include=["GTO 返回的主推荐动作及频率（例：raise 70%）"],
        exclude=["没有 GTO 结果的决策点"],
        missing="该点无 GTO 结果。",
    ),
    "gto_action_tendency": F(
        include=[
            "有依据的自然语言倾向：更倾向弃牌 / 过牌控池 / 跟注 / 价值下注 / 加注施压 / All-in 施压 / All-in 跟注",
        ],
        exclude=["枚举外的自由发挥", "无 GTO 仍编一句倾向"],
        missing="无 GTO。",
    ),
    "decision_quality_label": F(
        include=["四个枚举各准备至少 1 个点：符合GTO标准 / 基本可接受 / 风险偏高 / 信息不足"],
        exclude=["自造第五类", "边界样本（频率刚好 30%、尺度刚好 ±30%）归类不稳定"],
        mix="四种标签同场；含刚好卡在 30% 与 ±30% 的点。",
        consistency="同一点只能一个标签；与三类计数对得上。",
    ),
    "vpip_rate": F(
        include=[
            "分子：Hero 自愿 limp / 自愿 call / 自愿 raise 的手",
            "分母：本场总手数",
        ],
        exclude=[
            "只自动交大小盲、没有自愿加码——不能算 VPIP",
            "大盲前面没人加注、用户过牌看翻牌——不是自愿入池",
            "围观手",
        ],
        mix="自愿平跟、自愿加注、只交盲即弃、大盲无人加注过牌看翻牌 同场。",
        opportunity=["分母是总手数，不是「有机会自愿入池的手」"],
        zero_denom="本场识别手数为 0。",
        unit="自愿入池手数 / 总手数。",
    ),
    "pfr_rate": F(
        include=["分子：翻前 open raise、3-bet、4-bet（主动加注）；分母：总手数"],
        exclude=["limp 后别人加注再 call（不是 PFR）", "只跟注 open", "盲注防守的 call"],
        mix="open、3bet、limp、call open 同场。",
        zero_denom="总手数为 0。",
    ),
    "limp_rate": F(
        include=["分子：Hero 翻前 limp（call 盲注、前面无人加注）；分母：可行动手数（Hero 翻前轮到自己、且面前还没有 raise）"],
        exclude=["面对 open 再 call（那是 call_open，不是 limp）", "自己 open raise", "没轮到 Hero 的手进分母"],
        opportunity=["前面无人加注轮到Hero：Hero加注或弃牌。这手分母加1，分子不加"],
        zero_denom="整场 Hero 从未遇到「可 limp」的局面（例如全是面对加注）。",
    ),
    "call_open_rate": F(
        include=["分子：面对他人 open raise，Hero 选择 call；分母：面对 open raise 的次数"],
        exclude=["自己 open", "面对 3-bet 的 call", "limp（无人加注时 call 盲）"],
        opportunity=["面对加注，Hero弃牌或再加注。这手分母加1，分子不加"],
        zero_denom="整场没有人 open 到 Hero。",
    ),
    "three_bet_rate": F(
        include=["分子：面对 open 后 Hero 3-bet；分母：面对 open 的机会次数"],
        exclude=["自己先 open 不算 3-bet", "面对 3-bet 再 4-bet 不算 3-bet 分子", "cold call"],
        opportunity=["面对加注，Hero跟注或弃牌。这手分母加1，分子不加"],
        zero_denom="整场没有人 open 到用户。",
    ),
    "four_bet_rate": F(
        include=["分子：面对 3-bet 后 Hero 4-bet；分母：面对 3-bet 的机会次数"],
        exclude=["Hero 自己 3-bet 后对手再加，那是 Hero 面对 4-bet，不是 4-bet 分子", "面对 open 的 3-bet"],
        opportunity=["面对再加注，Hero弃牌或跟注。这手分母加1，分子不加"],
        zero_denom="整场用户没有面对 3bet。",
    ),
    "fold_to_3bet_rate": F(
        include=["分子：面对 3-bet 选择 fold；分母：面对 3-bet 次数"],
        exclude=["面对 open 就 fold", "自己 3-bet 成功让对手弃牌"],
        opportunity=["面对再加注，Hero跟注或再加注。这手分母加1，分子不加"],
        zero_denom="没有面对 3-bet。",
    ),
    "bb_defense_rate": F(
        include=["Hero 坐 BB，面对他人加注后 call 或 raise；分母=BB 面对加注次数"],
        exclude=["Hero 不在 BB", "BB 无人加注时 check", "SB 防守"],
        opportunity=["Hero坐大盲被加注后弃牌。这手分母加1，分子不加"],
        zero_denom="Hero 本场没有在 BB 被加注。",
    ),
    "sb_defense_rate": F(
        include=["Hero 坐 SB，面对加注后继续（call/raise）；分母=SB 面对加注次数"],
        exclude=["Hero 不在 SB", "SB 完成补盲后无人加注", "BB 防守"],
        opportunity=["Hero坐小盲被加注后弃牌。这手分母加1，分子不加"],
        zero_denom="没有在 SB 被加注。",
    ),
    "cbet_flop_rate": F(
        include=["Hero 是翻前最后一个加注者（aggressor），翻牌下注；分母=可 c-bet 次数（翻前主动且看到 flop、无人先下注）"],
        exclude=["翻前只跟注、翻牌再 bet（不是 c-bet）", "翻牌面对别人先 bet 再 raise", "没进翻后"],
        opportunity=["Hero翻前加注后进翻牌，翻牌过牌。这手分母加1，分子不加"],
        zero_denom="Hero 本场从未作为翻前主动者看到 flop。",
    ),
    "turn_barrel_rate": F(
        include=["翻牌已下注，转牌继续下注；分母=翻牌下注后转牌仍可下注的次数"],
        exclude=["翻牌没 bet、转牌突然 bet", "转牌面对别人下注再 raise"],
        opportunity=["Hero翻牌下注后转牌过牌。这手分母加1，分子不加"],
        zero_denom="没有「翻牌已 bet 且看到转牌」的手。",
    ),
    "river_bet_rate": F(
        include=["河牌 Hero 主动下注；分母=河牌 Hero 可行动次数（轮到 Hero、面前未关闭）"],
        exclude=["河牌只 call", "没到河牌"],
        opportunity=["到河牌，Hero过牌或弃牌。这手分母加1，分子不加"],
        zero_denom="没有河牌可行动。",
    ),
    "river_call_vs_raise_rate": F(
        include=["河牌 Hero 被加注后选择 call；分母=河牌被加注次数"],
        exclude=["河牌被 bet（不是 raise）后的 call——按口径这是面对下注，不是面对加注", "翻牌被加"],
        opportunity=["河牌被再加注，Hero弃牌。这手分母加1，分子不加"],
        zero_denom="河牌从未被加注。",
    ),
    "postflop_call_rate": F(
        include=["翻后任意街，Hero 面对下注选择 call 的次数；分母=翻后面对下注的次数（按次，不按手）"],
        exclude=["翻前 call", "翻后自己先 bet", "check（没人下注）"],
        opportunity=["翻后面对下注，Hero弃牌或加注。这次分母加1，分子不加"],
        zero_denom="翻后从未面对下注。",
        conflict="需求=翻后面对下注次数；Skill 未写清按手还是按次。只认「次数」。",
    ),
    "postflop_raise_rate": F(
        include=["翻后面对下注后 raise；分母=翻后面对下注次数"],
        exclude=["翻后自己先 open bet", "翻前 3-bet"],
        opportunity=["翻后面对下注，Hero跟注或弃牌。这次分母加1，分子不加"],
        zero_denom="翻后从未面对下注。",
        conflict="同分母：按次，不按手。",
    ),
    "multiway_pot_rate": F(
        include=["分子：Hero 参与且进入翻后人数 ≥3 的手；分母：参与手数"],
        exclude=["单挑底池（2 人）", "Hero 未参与的多人桌", "翻前多人但 Hero 已弃、未进该底池"],
        mix="3 人底池、单挑、Hero 未参与的多人手 同场。",
        zero_denom="参与手数为 0。",
    ),
    "weak_top_pair_continue_rate": F(
        include=[
            "弱顶对（见 06：A 面 A2-A9，K 面 K2-KT，Q 面 Q2-Q9，J 面 J2-J8，T 面 T2-T7）且 Hero 在转牌或河牌继续投入（call/bet/raise）",
            "分母=弱顶对场景数（该手形成弱顶对的次数/手数，按口径）",
        ],
        exclude=[
            "ATs 在 A 高面——踢脚 T 不在 A2-A9，不算弱顶对",
            "两对/三条看起来像顶对",
            "弱顶对但转河都 check 过牌（分子不计）",
        ],
        half=["只有弱顶对、转河没有继续投入", "继续投入但牌力不是弱顶对"],
        opportunity=["拿到弱顶对，转牌和河牌都过牌或弃牌。弱顶对手数含这一手，持续投入次数不含"],
        missing="公牌或手牌识别不出，无法判断是否弱顶对。",
        zero_denom="没有弱顶对场景。",
    ),
    "marginal_hand_entry_rate": F(
        include=[
            "分子：边缘起手牌（投机型去掉边缘连张 + 垃圾牌里被主动/跟注入池的）且 Hero 入池",
            "分母：本场发到边缘起手牌的次数",
        ],
        exclude=["AA/AKs 等顶端或强范围入池", "边缘牌发到了但 Hero fold（只进分母）"],
        opportunity=["拿到边缘牌，Hero弃牌。这手分母加1，分子不加"],
        half=["入池但牌是强范围", "边缘牌但没入池"],
        zero_denom="没发过边缘起手牌。",
        missing="手牌花色点数识别不出。",
    ),
    "aggression_ratio": F(
        include=["分子=bet+raise 次数；分母=call+check 次数"],
        exclude=["fold 进分母", "all-in 未按实际是 bet/raise 归类"],
        zero_denom="整场没有 call 也没有 check（分母 0，不得输出 0 或无穷大充数）。",
    ),
    "passive_call_ratio": F(
        include=["分子=call 次数；分母=所有非弃牌动作（按需求含 check）"],
        exclude=["fold 进分母", "按 Skill 把 check 踢出分母"],
        mix="同一场既有 call 也有 check、bet。",
        conflict="需求/基准分母含 check；Skill 不含 check。只认需求（含 check）。",
        zero_denom="没有任何非弃牌动作。",
    ),
    "position_name": F(
        include=[
            "2 人桌：只能出现 BTN/SB/BB 这套映射里的名字",
            "6 人桌：BTN/SB/BB/UTG/HJ/CO",
            "9 人桌：BTN/SB/BB/UTG/UTG+1/UTG+2/LJ/HJ/CO",
        ],
        exclude=["9 人桌却按六人桌写位置", "围观桌（没有自己的位置）"],
        mix="至少准备 2 人、6 人、9 人各一场（或同账号三场）。",
        missing="看不清座次/人数。",
        consistency="必须与 06 人数位置表一致，并与 hero_position 相同口径。",
    ),
    "hands_by_position": F(
        include=["按本手 Hero 真实位置分组计数，2～9 人用对的名字"],
        exclude=["Hero 没坐过的位置输出 0 手并拿去算 VPIP", "围观手按画面座位计数"],
        mix="BTN 多手、UTG 少手、某位置 0 手。",
    ),
    "played_by_position": F(
        include=["各位置上「参与手数」口径的手，分组计数"],
        exclude=["该位置只交盲即弃却算入池（与 hands_played 同一口径）", "把总手数当参与手数"],
        mix="同一位置：入池手 + 未入池手。",
    ),
    "vpip_by_position": F(
        include=["每个位置单独：该位置自愿入池手 / 该位置手数，不要套用全场 VPIP"],
        exclude=["把全场 VPIP 填到每个位置", "空位置填 0%"],
        mix="BTN VPIP 高、UTG VPIP 低的一场。",
        unit="每组独立比率。",
        zero_denom="某位置手数为 0：该组省略或 null。",
    ),
    "pfr_by_position": F(
        include=["该位置翻前主动加注次数 / 该位置手数"],
        exclude=["用全场 PFR 复用", "limp 算进该位置 PFR"],
        zero_denom="该位置 0 手。",
    ),
    "call_by_position": F(
        include=["该位置 call 次数 / 该位置可 call 次数"],
        exclude=["check 当 call", "无机会的位置填 0%"],
        zero_denom="该位置没有面对下注可跟的手。",
    ),
    "profit_by_position": F(
        include=["该位置所有已结算单手筹码盈亏加总"],
        exclude=["写成 BB 却标成筹码（Skill 用 BB，需求是筹码净赢）", "未结算手"],
        mix="BTN 大赢、BB 大亏，加总等于整场筹码盈亏。",
        unit="筹码（需求），不是 BB。",
        conflict="需求=筹码净赢；Skill=BB。只认筹码。",
        consistency="各位置 chips 之和 = total_profit_chips。",
    ),
    "ev_by_position": F(
        include=["该位置 per_hand_ev 加总"],
        exclude=["无 EV 的手当 0", "用实际盈亏填 EV"],
        missing="该位置没有 EV。",
    ),
    "risk_decisions_by_position": F(
        include=["该位置 high_risk 决策点数"],
        exclude=["把可接受算进高风险", "空位置填 0 冒充很稳"],
    ),
    "bb_defense_quality": F(
        include=["只统计 Hero 在 BB 面对加注后继续的那些手，其中可接受 vs 高风险决策比例"],
        exclude=["非 BB 的防守", "BB 无人加注的手", "信息不足当可接受"],
        zero_denom="没有 BB 防守决策。",
    ),
    "sb_defense_quality": F(
        include=["只统计 SB 面对加注后继续的手的质量比例"],
        exclude=["BB 防守混进来", "SB 主动 open 的手"],
        zero_denom="没有 SB 防守决策。",
    ),
    "opponent_id": F(
        include=["技术侧稳定玩家 ID，同一人多手同一个 id"],
        exclude=["把昵称当 id 写进用户可见处", "围观群众每人一个却与 Hero 无交手仍进对手表"],
        missing="识别不出对手。",
    ),
    "opponent_name": F(
        include=["视频或结构化数据里的真实昵称，用户可见"],
        exclude=["编一个「玩家1」", "把 Hero 自己的昵称当对手"],
        missing="昵称看不清：可省略，不得编造。",
    ),
    "opponent_position_distribution": F(
        include=["该对手出现在 BTN/BB 等位置的次数，按手计数"],
        exclude=["Hero 的位置算到对手头上", "对手已离开的手还计数"],
    ),
    "hands_vs_hero": F(
        include=["Hero 与该对手同时入池的手（两人一起进底池）"],
        exclude=["同桌但对手已 fold、只有 Hero 在池里", "Hero 已弃、对手在打", "多人池里把没入池的旁观者算交手"],
        mix="单挑交手、多人池两人同入、同桌但未同入 三类。",
    ),
    "profit_vs_opponent": F(
        include=["仅「两人共同参与」的那些手，把 Hero 盈亏加总记到该对手"],
        exclude=["同桌但未共同入池的手的盈亏", "多人池把整手盈亏同时记给每一个对手（重复记账）——按口径只记共同参与，多人时归属规则必须写清且稳定"],
        mix="对 A 单挑赢、对 B 单挑输、与 A+B 多人一池。",
    ),
    "ev_vs_opponent": F(
        include=["共同参与手的 EV 加总"],
        exclude=["无 EV 填 0", "未共同参与的手"],
        missing="这些手没有 EV。",
    ),
    "opponent_vpip": F(
        include=["该对手自愿入池次数 / 可观察手数（能看到他是否入池的手）"],
        exclude=["看不清对手是否入池的手当分母", "对手只交盲当 VPIP"],
        zero_denom="没有可观察手。",
    ),
    "opponent_pfr": F(
        include=["该对手翻前加注次数 / 可观察手数"],
        exclude=["对手 limp 当 PFR"],
        zero_denom="无可观察手。",
    ),
    "opponent_raise_rate": F(
        include=["对手 raise 次数 / 对手可行动次数"],
        exclude=["没轮到对手的手进分母"],
        opportunity=["对手轮到可加注时选择跟或弃。这次分母加1，分子不加"],
        zero_denom="对手没有可行动次。",
    ),
    "opponent_call_rate": F(
        include=["对手 call 次数 / 对手面对下注次数"],
        exclude=["对手自己 bet 当 call"],
        opportunity=["对手面对下注选择弃或加。这次分母加1，分子不加"],
        zero_denom="对手从未面对下注。",
    ),
    "opponent_fold_rate": F(
        include=["对手 fold 次数 / 对手面对下注次数"],
        exclude=["无人下注时对手弃牌（极少，且不应虚增）"],
        opportunity=["对手面对下注选择跟或加。这次分母加1，分子不加"],
        zero_denom="对手从未面对下注。",
    ),
    "opponent_3bet_rate": F(
        include=["对手 3-bet 次数 / 对手面对 open 次数"],
        exclude=["对手自己 open"],
        opportunity=["对手面对加注选择弃或跟。这次分母加1，分子不加"],
        zero_denom="对手从未面对 open。",
    ),
    "opponent_cbet_rate": F(
        include=["对手作为翻前主动者，翻牌下注次数 / 其可 c-bet 次数"],
        exclude=["对手翻前只 call、翻牌 bet"],
        opportunity=["对手翻前加注后进翻牌，翻牌过牌。这次分母加1，分子不加"],
        zero_denom="对手从未可 c-bet。",
    ),
    "hero_response_vs_opponent": F(
        include=["面对该对手时 Hero 的 fold/check/call/raise/all-in 次数和占比，按对手分开"],
        exclude=["把对所有对手的动作混在一个对手下面", "包含未共同入池的手"],
        mix="对松手多 raise、对紧手多 fold 的两个对手。",
    ),
    "hand_index": F(
        include=["按视频时间从早到晚：第 1 手、第 2 手… 连续编号"],
        exclude=["另一场或围观的手插进本场编号", "后打的手排在先打的手前面"],
        consistency="hand_index 递增必须与 video_timestamp 早晚一致。",
    ),
    "video_timestamp": F(
        include=["该手在视频中的起始时间（例：00:12:03），来自解析"],
        exclude=["播放器对不上的手（用第几手冒充时间）"],
        missing="解析不到时间：报告用「第几手」替代，本字段省略或 null。",
        consistency="时间越大，hand_index 越大。",
    ),
    "hero_cards": F(
        include=["识别出的两张 Hero 手牌，标准格式（例：A♠K♥）"],
        exclude=["手牌没亮或被遮挡的手", "围观时别人的牌"],
        missing="手牌被遮挡/没亮。",
        consistency="摊牌亮牌时必须与 showdown 亮牌一致。",
    ),
    "hero_position": F(
        include=["本手人数对应的真实位置名（2 人不要出现 UTG）"],
        exclude=["人数 9 却输出六人桌位置", "看错庄标"],
        missing="庄标/人数看不清。",
        consistency="与 position_name、06 映射表一致。",
    ),
    "blinds": F(
        include=["该手大小盲（例：50/100），来自牌局数据或台面盲注"],
        exclude=["另一盲注级别那场的手写进本场"],
        missing="盲注识别不到。",
        mix="换盲注会切成不同 session。本场只应出现一种盲注。",
    ),
    "effective_stack": F(
        include=["min(Hero 筹码, 主要对手筹码)，单位与牌桌一致"],
        exclude=["用 Hero 自己的筹码冒充有效筹码", "用桌均筹码", "多人池随便抓一个旁观者"],
        missing="筹码数字看不清。",
    ),
    "board_flop": F(
        include=["翻牌三张，标准牌面（例：A♠ 7♦ 2♣）"],
        exclude=["翻前结束、没发 flop 的手"],
        missing="没进翻后或翻牌看不清。",
    ),
    "board_turn": F(
        include=["第四张公牌，且前面已有合法 flop"],
        exclude=["没打到转牌的手"],
        missing="没到转牌。",
    ),
    "board_river": F(
        include=["第五张公牌"],
        exclude=["没打到河牌的手"],
        missing="没到河牌。",
    ),
    "pot_size_by_street": F(
        include=["翻前/翻/转/河四个底池数字，随下注累加或来自结构化字段，能对上行动链"],
        exclude=["四条街填同一个最终底池", "没到的街填 0 却展示给用户当「该街底池是 0」"],
        missing="行动金额看不清。",
        consistency="后一街底池 ≥ 前一街（除非抽水口径另有说明）。",
    ),
    "action_sequence_preflop": F(
        include=["翻前按真实位置顺序的行动链（例：UTG fold, CO raise 2.5bb, BTN call, BB fold）"],
        exclude=["围观桌的翻前行动"],
        missing="翻前行动看不清。",
        consistency="其中 Hero 一步 = actual_action / hero_actual_actions 翻前。",
    ),
    "action_sequence_flop": F(
        include=["翻牌圈完整行动链，位置名正确"],
        exclude=["翻前就结束、没进翻后的手"],
        missing="没到翻牌或看不清。",
    ),
    "action_sequence_turn": F(
        include=["转牌圈行动链"],
        exclude=["没打到转牌的手"],
        missing="没到转牌。",
    ),
    "action_sequence_river": F(
        include=["河牌圈行动链"],
        exclude=["没打到河牌的手"],
        missing="没到河牌。",
    ),
    "hero_actual_actions": F(
        include=["按街列出 Hero 自己的动作集合（翻前 raise，翻牌 bet，转牌 check…）"],
        exclude=["混进对手动作", "漏街"],
        missing="Hero 动作看不清。",
        consistency="与各街 action_sequence 中 Hero 步骤一致。",
    ),
    "showdown_result": F(
        include=[
            "任意街形成摊牌后的牌力、胜负、各家亮牌（翻前all-in发完翻转河、翻牌all-in再发转河、转牌all-in再发河、河牌常规亮牌都要有结果）",
        ],
        exclude=["没摊牌却写「Hero 赢」当摊牌结果", "亮牌与 hero_cards 矛盾"],
        missing="未摊牌：本字段省略，不是编一个牌力。",
    ),
    "is_multiway_pot": F(
        include=["进入翻后人数 ≥3 → true"],
        exclude=["翻前 3 人、进翻后只剩 2 人 → 不能标多人（口径：进入翻后人数）", "2 人底池标 true"],
        mix="3 人进 flop、单挑进 flop 各一手。",
    ),
    "is_big_pot": F(
        include=["该手最大底池 ≥ 50BB → true（用该手大盲换算）"],
        exclude=["49BB 标大底池", "用筹码绝对值 50 当 50BB（大盲不是 1）"],
        mix="49BB 与 50BB、80BB 各一手。",
    ),
    "is_all_in_or_near_all_in": F(
        include=["存在 all-in，或单次/累计投入 ≥ 有效筹码 70% → true"],
        exclude=["投入 69% 标 true", "别人 all-in、Hero 只跟注小额却标 Hero 侧接近 all-in（按口径核对是「本手是否存在」还是「Hero 是否」——执行时按清单「是否投入全部或大部分有效筹码」，优先看 Hero 投入）"],
        mix="全下、投入刚好 70%、投入 50% 三手。",
    ),
    "main_opponent": F(
        include=["优先：最终摊牌的对手；否则本手投入最大的对手"],
        exclude=["已经弃牌的松手当主要对手（除非他投入最大且无人摊牌）", "填 Hero 自己"],
        missing="单人底池/无法识别对手。",
        mix="摊牌对手与中途最大投入者不是同一人时，必须落在「摊牌者」。",
    ),
    "hand_order_sequence": F(
        include=["整场按 hand_index 或 video_timestamp 排好的序列"],
        exclude=["另一场或围观的手插进本场顺序"],
        consistency="与 hand_index、时间戳同序。",
    ),
    "segment_vpip_rate": F(
        include=["把一场按手数切成前/中/后三段，每段单独算 VPIP（例：前 1/3 很紧、后 1/3 很松）"],
        exclude=["三段填同一个全场 VPIP", "手数很少仍硬切三段并输出假对比"],
        mix="至少 12 手以上，前段少入池、后段多入池。",
        zero_denom="某段手数为 0。",
    ),
    "segment_pfr_rate": F(
        include=["分段独立算 PFR"],
        exclude=["复用全场 PFR"],
        mix="前段不加注、后段频繁 open。",
    ),
    "segment_call_rate": F(
        include=["分段 call 次数 / 分段面对下注次数"],
        exclude=["用全场 call 率", "分母用手数而不是面对下注次数"],
        zero_denom="该段没有面对下注。",
    ),
    "segment_defense_rate": F(
        include=["分段盲注位防守次数 / 分段盲注位面对加注次数"],
        exclude=["把非盲注 call 算进防守", "复用全场"],
        zero_denom="该段盲注位没被加。",
    ),
    "segment_high_risk_rate": F(
        include=["分段 high_risk / 分段 judgeable"],
        exclude=["分母用该段总决策（含信息不足）", "复用全场高风险占比"],
        zero_denom="该段无可判断点。",
    ),
    "win_streak_count": F(
        include=["按时间序，连续 per_hand_profit > 0 的最长长度（例：赢赢赢亏赢赢 → 3）"],
        exclude=["中间夹一手当 0 仍算连续", "打平手打断后仍连着算", "按绝对值或按 BB 重排后再数"],
        mix="两段连赢，中间夹一手亏或平，最长段必须是较长那一段。",
    ),
    "loss_streak_count": F(
        include=["连续亏损最长长度"],
        exclude=["打平不打断亏损（按口径：只有 <0 才算连亏，打平应打断）", "乱序数"],
        mix="两段连亏，中间夹赢或平。",
    ),
    "marginal_entry_after_win": F(
        include=["出现连赢后的窗口（N 手，N 按产品约定，未写则在用例里写明采用的 N），窗口内边缘牌入池的次数"],
        exclude=["连赢之前的边缘入池", "连赢后用 AA 入池", "没有连赢却统计"],
        half=["连赢后窗口内发了边缘牌但 fold", "没有连赢但边缘入池很多"],
        missing="没有时间序或手牌识别不出。",
    ),
    "marginal_entry_after_loss": F(
        include=["连亏后 N 手窗口内，边缘牌入池次数"],
        exclude=["连亏前的边缘入池", "连亏后强牌入池"],
        half=["连亏后边缘牌 fold", "未连亏的边缘入池"],
        missing="无时间序或无手牌。",
    ),
    "weak_AK_entry_count": F(
        include=["A2–A9、K2–K9（弱踢脚）且 Hero 入池的手，计数"],
        exclude=["AT/AJ/AQ/AK 入池", "A2 发到了但 fold", "KTs"],
        half=["弱 A/K 但没入池"],
        missing="手牌识别不出。",
    ),
    "low_connector_entry_count": F(
        include=["边缘连张名单内且入池：32s～T9s、32o～T9o（06 名单）"],
        exclude=["JTs（强范围同花连张，不在边缘连张表）", "54s 发到但 fold", "隔张 64s 按名单不算边缘连张"],
        half=["名单内连张但没入池"],
        missing="花色点数不清。",
    ),
    "oop_marginal_entry_count": F(
        include=["不利位置（UTG / MP / SB / BB，按该手人数映射）拿到边缘牌并入池"],
        exclude=["BTN/CO 边缘入池", "UTG 边缘牌 fold", "UTG 用 AA 入池"],
        half=["不利位置边缘牌但 fold", "有利位置边缘入池"],
        missing="位置或手牌不清。",
    ),
    "emotion_node_hand_range": F(
        include=["情绪节点对应的手牌区间 + 视频时间段（例：第 12～18 手，08:00–12:30，连亏后入池变松）"],
        exclude=["没有连续盈亏/入池变化依据却画一个节点", "区间与时间戳对不上"],
        missing="没有时间顺序或没有波动依据：模块 omit，不得编区间。",
    ),
}


MODULE_FIXTURES = {
    "smart_summary_status": {
        "normal": "一场同时有 Session 基础（总手数、参与）、整场盈亏、GTO 质量（可判断决策点）。",
        "degraded": "有总手数和盈亏，但 GTO 只有部分点能判断（缺一半推荐）。",
        "omit": "围观/无关视频，或完全切不出手数且没有任何 GTO。",
    },
    "emotion_module_status": {
        "normal": "手数足够、有时间序、能看出连赢/连亏和入池变化，并能指出代表手。",
        "degraded": "只有轻微波动（例如只连赢 2 手），证据不全。",
        "omit": "3 手以内或没有时间顺序。",
    },
    "key_hand_module_status": {
        "normal": "至少 4 手同时有行动链、GTO 参考、结算结果。",
        "degraded": "只有 1～3 手完整，或缺非关键字段。",
        "omit": "没有任何一手同时具备行动链和 GTO。",
    },
    "opponent_position_module_status": {
        "normal": "能识别至少 1 个对手的交手，且各位置手数充分。",
        "degraded": "只有对手或只有位置一类（例：位置齐但对手全是「未知」）。",
        "omit": "对手认不出、位置也认不出。",
    },
    "pnl_ev_module_status": {
        "normal": "有实际每手盈亏、EV、关键牌盈亏、决策质量。",
        "degraded": "有实际盈亏，EV 大面积缺失。",
        "omit": "没有任何可信盈亏（结算全打架）。",
    },
    "hand_type_warning_status": {
        "normal": "能从本场抽出 3～5 个有依据的风险场景（弱顶对继续、连亏后边缘入池等）。",
        "degraded": "只能抽出 1～2 个。",
        "omit": "没有可归纳的牌局类型（手数太少或全是信息不足）。",
    },
    "improvement_suggestion_status": {
        "normal": "有稳定优点、主要问题、可执行建议，且都能在本场数据上指到具体手/指标。",
        "degraded": "只有部分问题依据，仍能给一条建议。",
        "omit": "数据不足以形成任何有依据建议。",
    },
}


JSON_OBJECT_FIXTURES = {
    "session_summary": "用户参与的完整一场：有视频或等价事实层，切出多手。对照：围观/无关视频不应产出完整 session_summary 当作用户战绩。",
    "profit_ev_summary": "含已结算盈亏的一场。对照：结算全缺失时本对象按规则省略或空，不得全 0 充数。",
    "gto_decision_points": "至少若干 Hero 决策点有实际动作和 GTO 返回。对照：无 GTO 时列表空或不出现。",
    "style_profile_stats": "有足够翻前/翻后行动可算 VPIP/PFR 等。对照：只有围观则不应有用户画像。",
    "position_stats": "2～9 人中至少两种人数。对照：座次全看不清则省略。",
    "opponent_stats": "至少一名可识别对手、且与 Hero 有共同入池。对照：认不出对手。",
    "hands": "一手一行，含 hand_index。对照：围观/另一场的手不能出现在本场列表。",
    "timeline_stats": "有时间序和分段。对照：无时间戳且无法用手序分段时省略。",
}


# 反例标题用：说清楚「什么不计入」，不要写「无效素材」
NEG_LABEL = {
    "total_hands": "围观、另一场或半手",
    "hands_played": "前位弃牌且无盈亏",
    "folded_preflop_hands": "翻前入池、all-in有人跟、大盲过牌看翻牌",
    "postflop_hands": "翻前弃光未发flop",
    "showdown_hands": "弃牌未亮牌",
    "participation_rate": "未参与手当参与",
    "preflop_fold_rate": "进翻后弃牌算翻前弃",
    "postflop_entry_rate": "翻前结束手当进翻后",
    "showdown_rate": "未参与手进分母",
    "total_profit_chips": "围观桌输赢",
    "total_profit_bb": "用场均大盲换算",
    "hand_profit_chips": "整场盈亏摊到每一手",
    "hand_profit_bb": "用邻手或场均大盲",
    "winning_hands_count": "打平手当赢",
    "losing_hands_count": "打平手当亏",
    "breakeven_hands_count": "微赢微亏当打平",
    "top_profit_hands": "亏损手进盈利榜",
    "top_loss_hands": "盈利手进亏损榜",
    "profit_concentration_ratio": "Top3正负抵消",
    "total_ev": "无EV填0进总和",
    "per_hand_ev": "无GTO却有EV",
    "actual_vs_ev_gap": "BB和筹码混减",
    "ev_relation_type": "缺EV仍打标签",
    "luck_direction": "只看输赢打运气",
    "decision_impact_direction": "无依据仍打标签",
    "good_decision_bad_result_hands": "高风险亏损手当好决策",
    "bad_process_good_result_hands": "符合GTO的盈利手",
    "total_decision_points": "对手行动或自动交盲",
    "judgeable_decision_points": "信息不足点",
    "gto_matched_count": "尺度超出±30%",
    "acceptable_count": "首选一致点",
    "high_risk_count": "频率高于30%的偏离",
    "insufficient_info_count": "信息齐全却标不足",
    "gto_match_rate": "分母含信息不足",
    "acceptable_decision_rate": "高风险进分子",
    "high_risk_decision_rate": "分母用总决策点",
    "risk_by_street": "可接受算进高风险",
    "risk_by_position": "写死六人桌位置",
    "risk_by_pot_type": "漏多标签",
    "actual_action": "写成对手动作",
    "gto_recommended_action": "无GTO却填推荐",
    "gto_action_tendency": "枚举外自由发挥",
    "decision_quality_label": "自造第五类标签",
    "vpip_rate": "只交盲或大盲无人加注过牌看翻牌",
    "pfr_rate": "limp后再跟注",
    "limp_rate": "面对open再跟注",
    "call_open_rate": "自己open",
    "three_bet_rate": "自己先open",
    "four_bet_rate": "自己3bet后被再加",
    "fold_to_3bet_rate": "面对open就弃",
    "bb_defense_rate": "人不在BB",
    "sb_defense_rate": "人不在SB",
    "cbet_flop_rate": "翻前只跟翻牌再bet",
    "turn_barrel_rate": "翻牌没bet转牌才bet",
    "river_bet_rate": "河牌只跟注",
    "river_call_vs_raise_rate": "河牌面对下注后跟注",
    "postflop_call_rate": "翻前跟注",
    "postflop_raise_rate": "自己先开注",
    "multiway_pot_rate": "单挑底池",
    "weak_top_pair_continue_rate": "ATs不当弱顶对",
    "marginal_hand_entry_rate": "AA等强牌当边缘",
    "aggression_ratio": "fold进分母",
    "passive_call_ratio": "fold进分母",
    "position_name": "9人桌套六人桌位置",
    "hands_by_position": "没坐过的位置填0手",
    "played_by_position": "该位只交盲即弃",
    "vpip_by_position": "全场VPIP填到每个位置",
    "pfr_by_position": "复用全场PFR",
    "call_by_position": "check当call",
    "profit_by_position": "BB写成筹码",
    "ev_by_position": "无EV填0",
    "risk_decisions_by_position": "可接受算高风险",
    "bb_defense_quality": "非BB的防守",
    "sb_defense_quality": "BB防守混进来",
    "opponent_id": "昵称当id",
    "opponent_name": "编「玩家1」",
    "opponent_position_distribution": "Hero位置算到对手",
    "hands_vs_hero": "同桌未同入池",
    "profit_vs_opponent": "未同入池记账",
    "ev_vs_opponent": "无EV填0",
    "opponent_vpip": "看不清仍进分母",
    "opponent_pfr": "对手limp当PFR",
    "opponent_raise_rate": "没轮到对手进分母",
    "opponent_call_rate": "对手自己bet当call",
    "opponent_fold_rate": "无人下注的弃牌",
    "opponent_3bet_rate": "对手自己open",
    "opponent_cbet_rate": "对手翻前只跟翻牌bet",
    "hero_response_vs_opponent": "多对手动作混在一人",
    "hand_index": "后打的手排在前面",
    "video_timestamp": "用第几手冒充时间",
    "hero_cards": "手牌没亮或被遮挡",
    "hero_position": "9人桌套六人桌位置",
    "blinds": "把另一盲注场写进本场",
    "effective_stack": "用自己筹码冒充有效筹码",
    "board_flop": "没发flop的手",
    "board_turn": "没打到转牌的手",
    "board_river": "没打到河牌的手",
    "pot_size_by_street": "四街填同一个最终底池",
    "action_sequence_preflop": "围观桌行动",
    "action_sequence_flop": "没进翻后的手",
    "action_sequence_turn": "没打到转牌的手",
    "action_sequence_river": "没打到河牌的手",
    "hero_actual_actions": "混进对手动作",
    "showdown_result": "没摊牌却写Hero赢",
    "is_multiway_pot": "翻前3人flop只剩2人",
    "is_big_pot": "49BB或50筹码",
    "is_all_in_or_near_all_in": "投入69%且无全下",
    "main_opponent": "已弃牌的松手",
    "hand_order_sequence": "另一场或围观插入",
    "segment_vpip_rate": "三段填同一个全场VPIP",
    "segment_pfr_rate": "复用全场PFR",
    "segment_call_rate": "复用全场call率",
    "segment_defense_rate": "非盲注call算防守",
    "segment_high_risk_rate": "分母含信息不足",
    "win_streak_count": "中间夹0仍算连赢",
    "loss_streak_count": "打平不打断连亏",
    "marginal_entry_after_win": "连赢前的边缘入池",
    "marginal_entry_after_loss": "连亏前的边缘入池",
    "weak_AK_entry_count": "AT入池或A5弃牌",
    "low_connector_entry_count": "JTs或未入池的54s",
    "oop_marginal_entry_count": "BTN/CO边缘入池",
    "emotion_node_hand_range": "无依据却画节点",
}


def fixture_for(code: str) -> dict:
    return FIXTURES.get(code) or F(
        include=[f"按需求清单准备能算出「{code}」的用户参与牌局"],
        exclude=list(SESSION_EXCLUDE),
    )
