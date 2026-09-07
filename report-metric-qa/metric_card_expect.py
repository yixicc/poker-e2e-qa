"""每张主卡的手算期望。数字来自 sample_sessions.md，换场先改那边。"""

from __future__ import annotations

# session: 用哪一场；expect: 这场合该是几；fail: 怎样算失败
E: dict[str, dict[str, str]] = {
    "video_duration": {
        "session": "按条准备：带秒的普通片 / 0 秒片 / 超长片",
        "expect": "字段单位是秒，数值等于播放器时长（例 12 分 30 秒 = 750）。0 秒片写出 0；超长片按实际秒数写全，不能截成整小时。",
        "fail": "写成分钟整数、和播放器差 1 秒以上、用手数冒充时长、0 秒片被省略或编成默认时长、超长被截断却仍显示成功。",
    },
    "total_hands": {
        "session": "场A",
        "expect": "8。翻前弃、进翻后、摊牌都各算 1。手数列表行数=8。",
        "fail": "漏掉翻前弃牌的手；或把围观/另一场的手加进来。",
    },
    "hands_played": {
        "session": "场A",
        "expect": "6（H1 H2 H3 H4 H6 H8）。H4 因盲注亏损计入。H5 H7 不计入。",
        "fail": "只算自愿入池得到 5（漏 H4）；或把 H5 算进去得到 7。",
    },
    "folded_preflop_hands": {
        "session": "场A",
        "expect": "3（H4 H5 H7）。H1/H2/H3/H6/H8 进了翻后，不算翻前弃。",
        "fail": "把进翻后才弃牌的手当翻前弃；或漏掉 H4。",
    },
    "postflop_hands": {
        "session": "场A",
        "expect": "5（H1 H2 H3 H6 H8）。",
        "fail": "H4/H5/H7 被算进翻后；或只有残缺公牌却编进翻后。",
    },
    "showdown_hands": {
        "session": "场A + 场J（各街摊牌）",
        "expect": "场A：3（H1 H3 H8 有亮牌）。场J 另验：翻前/翻/转 all-in 亮牌各 +1，河牌亮牌 +1；H2 及各街弃牌未亮不算。",
        "fail": "只把河牌亮牌算摊牌（漏翻前/翻/转 all-in 后发完剩余街再亮牌）；或把未亮牌赢池、all-in 后对手弃牌算进去。",
    },
    "participation_rate": {
        "session": "场A",
        "expect": "6/8 = 75%。",
        "fail": "做成 5/8（按 VPIP）；或 6/6。",
    },
    "preflop_fold_rate": {
        "session": "场A",
        "expect": "3/8 = 37.5%。",
        "fail": "分母用参与手数 3/6。",
    },
    "postflop_entry_rate": {
        "session": "场A",
        "expect": "5/8 = 62.5%。",
        "fail": "分母用参与手数 5/6。",
    },
    "showdown_rate": {
        "session": "场A",
        "expect": "3/6 = 50%。分母是参与手数，不是总手数。",
        "fail": "3/8 = 37.5%（Skill 用总手数）。H2 进分子。",
    },
    "total_profit_chips": {
        "session": "场A",
        "expect": "200+100−150−50+0+80+0−300 = −120。",
        "fail": "用开场−散场未核验差值；重复 H1 把 +200 加两次。",
    },
    "total_profit_bb": {
        "session": "场A",
        "expect": "2.0+1.0−1.5−0.5+0+0.4+0−1.5 = −0.1BB。两档大盲按手换算再加总。",
        "fail": "−120÷150（场均大盲）= −0.8BB。",
    },
    "hand_profit_chips": {
        "session": "场A",
        "expect": "H1=+200，H2=+100，H3=−150，H4=−50，H5=0，H6=+80，H7=0，H8=−300。",
        "fail": "每手都填 −120；未结算手填 0 冒充。",
    },
    "hand_profit_bb": {
        "session": "场A",
        "expect": "H1=+2，H2=+1，H3=−1.5，H4=−0.5，H5=0，H6=+0.4，H7=0，H8=−1.5。H6/H8 必须 ÷200。",
        "fail": "H6 做成 +80/100=+0.8。",
    },
    "winning_hands_count": {
        "session": "场A",
        "expect": "3（H1 H2 H6）。",
        "fail": "把 H5/H7 打平算赢；或漏 H6。",
    },
    "losing_hands_count": {
        "session": "场A",
        "expect": "3（H3 H4 H8）。",
        "fail": "漏 H4（只输盲注也是亏）。",
    },
    "breakeven_hands_count": {
        "session": "场A",
        "expect": "2（H5 H7，利润恰好 0）。",
        "fail": "未结算手当 0 打平。",
    },
    "top_profit_hands": {
        "session": "场A",
        "expect": "顺序 H1(+200)、H2(+100)、H6(+80)。N=3 时就这三条，亏损手不出现。",
        "fail": "H8 出现在盈利列表；顺序按时间不按盈亏。",
    },
    "top_loss_hands": {
        "session": "场A",
        "expect": "顺序 H8(−300)、H3(−150)、H4(−50)。",
        "fail": "盈利手进列表；按时间排序。",
    },
    "profit_concentration_ratio": {
        "session": "场A",
        "expect": "绝对值最大三手 300+200+150=650；全场绝对值 200+100+150+50+80+300=880；650/880 ≈ 73.86%。打平的 0 不进分母也可，分母仍是 880。",
        "fail": "用带符号加总当分子（正负抵消）。",
    },
    "total_ev": {
        "session": "场A 且每手给 EV：H1=+1.2BB … 假设八手 EV 加总 = +2.0BB（执行时按实际 GTO 返回改数字，但加总规则不变）",
        "expect": "等于各手 per_hand_ev 之和。无 EV 的手不进总和、不当 0。",
        "fail": "用 −0.1（实际盈亏）冒充 EV；缺 EV 的手当 0 填进总和。",
    },
    "per_hand_ev": {
        "session": "场A + 场D 有返回的手",
        "expect": "有 GTO EV 的手写原值；H5/H7 若无 EV 则省略，不编。",
        "fail": "把 −0.1 摊到每一手。",
    },
    "actual_vs_ev_gap": {
        "session": "场A，设 total_ev_bb=+2.0",
        "expect": "−0.1 − 2.0 = −2.1BB（单位必须都是 BB）。",
        "fail": "一边筹码一边 BB 相减。",
    },
    "ev_relation_type": {
        "session": "场A，gap=−2.1BB",
        "expect": "按文档阈值：明显低于期望 →「低于期望」（阈值未写死则在备注写明采用的阈值，例如 |gap|≥2BB）。",
        "fail": "缺 EV 仍打「低于期望」。",
    },
    "luck_direction": {
        "session": "场A：实际 −0.1BB、EV +2.0BB，且有「打对但输」的手",
        "expect": "运气不利（实际明显低于 EV）。",
        "fail": "只看 −120 筹码就打运气，不看 EV。",
    },
    "decision_impact_direction": {
        "session": "场A + 场D：高风险 2 个点、关键亏损 H8",
        "expect": "能指出决策质量对亏损有影响（有依据）。信息不足场不得给标签。",
        "fail": "没有质量数据和关键亏牌仍给方向。",
    },
    "good_decision_bad_result_hands": {
        "session": "补一手：全程符合GTO/可接受，且本手 −80；场A 的 H8 若有高风险则不能进本列表",
        "expect": "只出现「质量可接受且亏损」的手。",
        "fail": "H8 有风险偏高却因亏损被放进来。",
    },
    "bad_process_good_result_hands": {
        "session": "补一手：任意动作风险偏高且本手 +50；H1 全程符合且赢，不进",
        "expect": "只出现「有高风险且盈利」的手。",
        "fail": "H1 进列表。",
    },
    "total_decision_points": {
        "session": "场D",
        "expect": "10。自动交盲不计数。",
        "fail": "对手动作被算进 Hero；或 8（漏信息不足点）。",
    },
    "judgeable_decision_points": {
        "session": "场D",
        "expect": "8（总 10 − 信息不足 2）。",
        "fail": "10；或三类加总 ≠ 8。",
    },
    "gto_matched_count": {
        "session": "场D",
        "expect": "4（D1 D5 D9 D10）。D4 尺度超 ±30% 不算符合。",
        "fail": "D4 算符合得到 5；D3 算符合。",
    },
    "acceptable_count": {
        "session": "场D",
        "expect": "2（D3 频率>30%；D4 尺度超 ±30%）。频率刚好 30% 必须稳定落在一类，本场用 35% 避开。",
        "fail": "D2（25%）算可接受。",
    },
    "high_risk_count": {
        "session": "场D",
        "expect": "2（D2 D8）。",
        "fail": "D3 算高风险。",
    },
    "insufficient_info_count": {
        "session": "场D",
        "expect": "2（D6 D7）。",
        "fail": "把可判断点标信息不足。",
    },
    "gto_match_rate": {
        "session": "场D",
        "expect": "4/8 = 50%（整数百分比）。分母是可判断数，不是 10。",
        "fail": "4/10=40%；分母为 0 时输出 0%。",
    },
    "acceptable_decision_rate": {
        "session": "场D",
        "expect": "(4+2)/8 = 75%。",
        "fail": "分子含高风险；分母用 10。",
    },
    "high_risk_decision_rate": {
        "session": "场D",
        "expect": "2/8 = 25%。与可接受占比四舍五入前加总 100%。",
        "fail": "2/10=20%。",
    },
    "risk_by_street": {
        "session": "场D：D2 翻前、D8 河牌",
        "expect": "preflop=1，river=1，flop/turn=0 或省略。不得把可接受算进来。",
        "fail": "没有河牌高风险却输出 0 冒充「河牌很稳」给用户。",
    },
    "risk_by_position": {
        "session": "场D + 场A 位置",
        "expect": "按本手真实位置汇总高风险点数；2 人桌不能用 UTG。",
        "fail": "写死六人桌位置名。",
    },
    "risk_by_pot_type": {
        "session": "补 1 个高风险点：决策前底池 60BB、3 人、河牌被加、投入 75% 筹码",
        "expect": "同一点同时计入：大底池、多人、河牌面对加注、接近 All-in 四个标签。",
        "fail": "只打一个标签；49BB 打上大底池。",
    },
    "actual_action": {
        "session": "场D D1",
        "expect": "raise（与录像一致）。",
        "fail": "写成 call；或把对手动作写到 Hero。",
    },
    "gto_recommended_action": {
        "session": "场D D1",
        "expect": "raise + 频率（如 2.5bb / 主推）。",
        "fail": "没有返回却填 raise；或抄 Hero 实际动作。",
    },
    "gto_action_tendency": {
        "session": "场D D1 / D5",
        "expect": "D1→加注施压；D5→更倾向弃牌。只允许清单枚举。",
        "fail": "自由发挥一句；无 GTO 仍编倾向。",
    },
    "decision_quality_label": {
        "session": "场D",
        "expect": "D1符合 / D3可接受 / D2风险偏高 / D6信息不足。一点一类。",
        "fail": "第五类；D4 标符合。",
    },
    "vpip_rate": {
        "session": "场A",
        "expect": "5/8 = 62.5%（H1 H2 H3 H6 H8）。H4 只交盲不算自愿。H5 大盲免费看牌也不算（本场 H5 是 UTG fold）。",
        "fail": "6/8（把 H4 算 VPIP）；或 5/6。",
    },
    "pfr_rate": {
        "session": "场A",
        "expect": "2/8 = 25%（H1 H6 open raise）。H2 limp、H3 call、H8 call 不算。",
        "fail": "把 limp 算 PFR 得到 3/8。",
    },
    "limp_rate": {
        "session": "场E",
        "expect": "1/4 = 25%。面对 open 再 call 不进分子也不进这个分母。",
        "fail": "call open 算 limp。",
    },
    "call_open_rate": {
        "session": "场E",
        "expect": "1/4 = 25%。3bet 和 fold 只进分母。",
        "fail": "自己 open 进分母；limp 算 call open。",
    },
    "three_bet_rate": {
        "session": "场E",
        "expect": "1/4 = 25%。",
        "fail": "自己先 open 算 3bet；4bet 算 3bet。",
    },
    "four_bet_rate": {
        "session": "场E",
        "expect": "1/3 ≈ 33.3%。",
        "fail": "3bet 进分子；分母用面对 open 次数。",
    },
    "fold_to_3bet_rate": {
        "session": "场E",
        "expect": "1/3 ≈ 33.3%。",
        "fail": "面对 open 就 fold 算进来。",
    },
    "bb_defense_rate": {
        "session": "场E",
        "expect": "2/3 ≈ 66.7%（call+raise）。fold 只进分母。",
        "fail": "SB 防守混进；无人加注的 BB check 进分母。",
    },
    "sb_defense_rate": {
        "session": "场E",
        "expect": "0/2 = 0%。这是「有分母的 0%」，允许。",
        "fail": "和「分母为 0」搞混而省略；或做成 null。本条有 2 次机会，必须是 0%。",
    },
    "cbet_flop_rate": {
        "session": "场E",
        "expect": "2/3 ≈ 66.7%。翻前只跟注再 flop bet 不算。",
        "fail": "非 aggressor 的 flop bet 进分子。",
    },
    "turn_barrel_rate": {
        "session": "场E",
        "expect": "1/2 = 50%。",
        "fail": "翻牌没 bet、转牌突然 bet 进分子。",
    },
    "river_bet_rate": {
        "session": "场E",
        "expect": "1/3 ≈ 33.3%。",
        "fail": "河牌 call 算 bet。",
    },
    "river_call_vs_raise_rate": {
        "session": "场E",
        "expect": "1/2 = 50%。面对的是 raise 不是普通 bet。",
        "fail": "河牌被 bet 后的 call 算进本指标。",
    },
    "postflop_call_rate": {
        "session": "场E",
        "expect": "2/5 = 40%。按次，不按手。",
        "fail": "按手做成 2/3；翻前 call 进分子。",
    },
    "postflop_raise_rate": {
        "session": "场E",
        "expect": "1/5 = 20%。",
        "fail": "自己先 open bet 算 raise；按手计数。",
    },
    "multiway_pot_rate": {
        "session": "场A 改两手：H1 进翻后 3 人，H6 进翻后 2 人；参与仍 6",
        "expect": "多人进翻后的参与手 / 6。若只有 H1 是多人：1/6 ≈ 16.7%。翻前 3 人、进翻后剩 2 人的手不算。",
        "fail": "单挑算多人；未参与的多人桌算进去。",
    },
    "weak_top_pair_continue_rate": {
        "session": "场H",
        "expect": "1/2 = 50%（A7 继续投入；ATs 场景不算弱顶对，不进分母）。",
        "fail": "ATs 进分母；两对算弱顶对。",
    },
    "marginal_hand_entry_rate": {
        "session": "场H：边缘牌出现 3 次，入池 2 次（54s、A2o），AA 入池不进分子分母",
        "expect": "2/3 ≈ 66.7%。",
        "fail": "AA 算边缘。",
    },
    "aggression_ratio": {
        "session": "统计场A+场E 的 bet+raise 与 call+check。例：bet+raise=6，call+check=4 → 6/4=1.5",
        "expect": "等于 (bet+raise)/(call+check)。fold 不进分母。",
        "fail": "分母含 fold；分母为 0 时输出 0 或无穷大。",
    },
    "passive_call_ratio": {
        "session": "call 3 次、check 2 次、bet 4 次、fold 5 次",
        "expect": "3/(3+2+4)=3/9=33.3%。分母含 check，不含 fold。",
        "fail": "3/(3+4)=42.9%（Skill 踢掉 check）。",
    },
    "position_name": {
        "session": "场F",
        "expect": "2 人桌不出 UTG；9 人桌 Hero=UTG+2；6 人桌场A 用 CO/BTN/BB/UTG/HJ。",
        "fail": "9 人桌写成六人桌 HJ 硬套。",
    },
    "hands_by_position": {
        "session": "场A",
        "expect": "CO=2（H1 H6），BTN=2（H2 H7），BB=2（H3 H4），UTG=1（H5），HJ=1（H8）。没坐过的位置省略，不要 0 手还拿去算 VPIP。",
        "fail": "把 0 手位置输出 0% VPIP 给用户。",
    },
    "played_by_position": {
        "session": "场A",
        "expect": "CO=2，BTN=1（仅 H2），BB=2（H3 H4），UTG=0 省略，HJ=1。",
        "fail": "BTN 把 H7 未参与算进去。",
    },
    "vpip_by_position": {
        "session": "场A",
        "expect": "每组自己算。BTN=1/2=50%（H2 自愿，H7 不自愿）；CO=2/2=100%。不要填全场 62.5%。",
        "fail": "每个位置都填 62.5%。",
    },
    "pfr_by_position": {
        "session": "场A",
        "expect": "CO=2/2=100%；BTN=0/2=0%；其余 0/该位置手数。",
        "fail": "limp 算进 BTN 的 PFR。",
    },
    "call_by_position": {
        "session": "场A：BB 可 call 2 次（H3 call，H4 被加后 fold）→ BB=1/2",
        "expect": "按位置独立。无机会的位置省略。",
        "fail": "check 当 call。",
    },
    "profit_by_position": {
        "session": "场A",
        "expect": "CO=+200+80=+280；BTN=+100+0=+100；BB=−150−50=−200；UTG=0；HJ=−300。单位是筹码。五者之和=−120。",
        "fail": "写成 BB；各组之和 ≠ −120。",
    },
    "ev_by_position": {
        "session": "场A 有 EV 的手按位置加总",
        "expect": "该位置 per_hand_ev 之和；无 EV 不填 0。",
        "fail": "用实际盈亏填 EV。",
    },
    "risk_decisions_by_position": {
        "session": "场D 高风险点挂到本手位置",
        "expect": "各位置 high_risk 点数；空位置省略。",
        "fail": "可接受算进高风险。",
    },
    "bb_defense_quality": {
        "session": "场E 的 BB 防守手 + 场D 质量",
        "expect": "只在 BB 被加后继续的手里算可接受/高风险比例。",
        "fail": "无人加注的 BB 手进分母；SB 混进。",
    },
    "sb_defense_quality": {
        "session": "场E SB 被加 2 次均 fold → 没有「继续防守」的质量样本",
        "expect": "无继续则省略或按缺失，不得编质量。",
        "fail": "用 0% 冒充「SB 防守很差/很好」。",
    },
    "opponent_id": {
        "session": "场G",
        "expect": "甲、乙各一个稳定 id，甲的 3 手同一个 id。",
        "fail": "昵称当 id 展示给用户。",
    },
    "opponent_name": {
        "session": "场G",
        "expect": "甲=「小王」；乙看不清则省略。",
        "fail": "乙编成「玩家2」。",
    },
    "opponent_position_distribution": {
        "session": "场G 甲三次：BTN、BB、CO 各 1",
        "expect": "甲：BTN1 BB1 CO1。",
        "fail": "把 Hero 位置算到甲头上。",
    },
    "hands_vs_hero": {
        "session": "场G",
        "expect": "甲=3，乙=1。同桌未共同入池的 2 手不算。",
        "fail": "甲=5（把未同入的手算上）。",
    },
    "profit_vs_opponent": {
        "session": "场G",
        "expect": "甲=+60，乙=−100。多人池不得把同一手盈亏同时记给甲和乙各一份（除非口径书面允许，本卡按「只记共同参与且不重复记账」）。",
        "fail": "未同入的手盈亏记到甲。",
    },
    "ev_vs_opponent": {
        "session": "场G 三手甲有 EV 则加总",
        "expect": "共同参与手 EV 之和。",
        "fail": "无 EV 填 0。",
    },
    "opponent_vpip": {
        "session": "甲可观察 5 手、自愿入池 3 手",
        "expect": "3/5=60%。只交盲不算。",
        "fail": "看不清的手当分母。",
    },
    "opponent_pfr": {
        "session": "甲可观察 5 手、翻前加注 1 手",
        "expect": "1/5=20%。",
        "fail": "甲 limp 算 PFR。",
    },
    "opponent_raise_rate": {
        "session": "甲可行动 8 次、raise 2 次",
        "expect": "2/8=25%。",
        "fail": "没轮到甲的手进分母。",
    },
    "opponent_call_rate": {
        "session": "甲面对下注 4 次、call 1 次",
        "expect": "1/4=25%。",
        "fail": "甲自己 bet 当 call。",
    },
    "opponent_fold_rate": {
        "session": "甲面对下注 4 次、fold 2 次",
        "expect": "2/4=50%。",
        "fail": "无人下注的弃牌虚增分母。",
    },
    "opponent_3bet_rate": {
        "session": "甲面对 open 3 次、3bet 1 次",
        "expect": "1/3≈33.3%。",
        "fail": "甲自己 open 进分母。",
    },
    "opponent_cbet_rate": {
        "session": "甲可 c-bet 2 次、flop bet 1 次",
        "expect": "1/2=50%。",
        "fail": "甲翻前只 call、flop bet 算 c-bet。",
    },
    "hero_response_vs_opponent": {
        "session": "对甲：fold1 check0 call1 raise1 all-in0；对乙：fold1",
        "expect": "按对手分开，次数和占比对得上。",
        "fail": "甲乙混成一张表。",
    },
    "hand_index": {
        "session": "场A",
        "expect": "H1=1 … H8=8，按视频从早到晚。",
        "fail": "按结算乱序；出现两个「1」当两手。",
    },
    "video_timestamp": {
        "session": "场A，H1 从 00:00:40 起，H8 在 00:11:10",
        "expect": "每手一个起始时间，越晚 index 越大。",
        "fail": "全填 00:00:00；用手数冒充时间格式。",
    },
    "hero_cards": {
        "session": "场A H1 设为 A♠K♥，H1 摊牌亮牌相同",
        "expect": "H1=A♠K♥。看不清的手省略。",
        "fail": "看不清填 AA；公牌当手牌；围观把别人的牌当 Hero。",
    },
    "hero_position": {
        "session": "场A + 场F",
        "expect": "与表一致：H1=CO，H5=UTG，2 人桌无 UTG。",
        "fail": "9 人桌输出六人桌名。",
    },
    "blinds": {
        "session": "场A",
        "expect": "H1–H5 为 50/100（或 100 大盲，按接口）；H6–H8 为 100/200。",
        "fail": "八手都写成 100/200。",
    },
    "effective_stack": {
        "session": "H1 Hero 12000、摊牌对手 8000 → 8000",
        "expect": "min(Hero, 主要对手)。",
        "fail": "填 12000；或填桌均。",
    },
    "board_flop": {
        "session": "H1 翻牌 A♠ 7♦ 2♣；H4 没有 flop",
        "expect": "H1=A♠7♦2♣；H4 省略。",
        "fail": "H4 编三张；转牌叠进翻牌。",
    },
    "board_turn": {
        "session": "H1 转牌 9♥；H2 没到转牌",
        "expect": "H1=9♥；H2 省略。",
        "fail": "H2 填转牌。",
    },
    "board_river": {
        "session": "H1 河牌 4♣；未到河牌的手省略",
        "expect": "H1=4♣。",
        "fail": "没发河牌却填。",
    },
    "pot_size_by_street": {
        "session": "H1：翻前 250、翻牌 800、转牌 800、河牌 1600（示例，以行动链累加为准）",
        "expect": "四街数字能对上行动链；后街 ≥ 前街（除非抽水另有说明）。没到的街省略。",
        "fail": "四街都填最终 1600。",
    },
    "action_sequence_preflop": {
        "session": "H1：UTG fold, HJ fold, CO(Hero) raise 2.5bb, BTN fold, SB fold, BB call",
        "expect": "按真实位置顺序，与录像一致。",
        "fail": "漏 BB call；编造没发生的 3bet。",
    },
    "action_sequence_flop": {
        "session": "H1 有 flop 行动链；H4 无",
        "expect": "H1 有链；H4 省略，不得复制翻前链。",
        "fail": "H4 出现假 flop 链。",
    },
    "action_sequence_turn": {
        "session": "仅到转牌的手有链",
        "expect": "没到转牌省略。",
        "fail": "没到转牌却编链。",
    },
    "action_sequence_river": {
        "session": "仅到河牌的手有链",
        "expect": "没到河牌省略。",
        "fail": "没到河牌却编链。",
    },
    "hero_actual_actions": {
        "session": "H1：翻前 raise，翻后按实际（例 flop bet）",
        "expect": "只含 Hero，按街列全。与 action_sequence 里 Hero 步骤一致。",
        "fail": "混进对手动作。",
    },
    "showdown_result": {
        "session": "H1 亮牌赢；H2 未亮",
        "expect": "H1 有牌力/胜负/亮牌；H2 省略（不是「Hero 赢」当摊牌结果）。",
        "fail": "H2 写摊牌牌力；亮牌与 hero_cards 矛盾。",
    },
    "is_multiway_pot": {
        "session": "H1 进翻后 3 人=true；H6 进翻后 2 人=false",
        "expect": "看进翻后人数，不是翻前人数。",
        "fail": "翻前 3 人、flop 2 人标 true。",
    },
    "is_big_pot": {
        "session": "一手最大底池 49BB、一手 50BB、一手 80BB",
        "expect": "49=false，50=true，80=true。用该手大盲换算。",
        "fail": "大盲 100 时把 50 筹码当成 50BB。",
    },
    "is_all_in_or_near_all_in": {
        "session": "全下 / 投入 70% / 投入 50% 各一手",
        "expect": "全下 true；70% true；50% false。优先看 Hero 投入。",
        "fail": "69% 标 true。",
    },
    "main_opponent": {
        "session": "一手：中途最大投入是甲，最终摊牌是乙",
        "expect": "乙（优先摊牌者）。",
        "fail": "填甲；填 Hero 自己。",
    },
    "hand_order_sequence": {
        "session": "场A",
        "expect": "[H1…H8] 与时间戳同序。",
        "fail": "乱序、漏手、重复手。",
    },
    "segment_vpip_rate": {
        "session": "场I：前4入池1、中4入池3、后4入池2",
        "expect": "前 25%、中 75%、后 50%。不要三段都填全场值。",
        "fail": "三段相同。",
    },
    "segment_pfr_rate": {
        "session": "场I：前段 0 次加注、后段 2 次 open / 4 手",
        "expect": "前 0%，后 50%。独立算。",
        "fail": "复用全场 PFR。",
    },
    "segment_call_rate": {
        "session": "中段面对下注 3 次、call 2 次",
        "expect": "中段 2/3。分母是面对下注次数。",
        "fail": "分母用手数。",
    },
    "segment_defense_rate": {
        "session": "后段盲注被加 2 次、继续 1 次",
        "expect": "后段 1/2。",
        "fail": "非盲注 call 算防守。",
    },
    "segment_high_risk_rate": {
        "session": "后段可判断 4、高风险 2",
        "expect": "后段 50%。分母不含信息不足。",
        "fail": "复用全场 25%。",
    },
    "win_streak_count": {
        "session": "场I：+++−0++−−−+−",
        "expect": "3（开头三连赢）。中间的 0 打断，后面 ++ 只有 2。",
        "fail": "打平不打断，数成更长。",
    },
    "loss_streak_count": {
        "session": "场I",
        "expect": "3（第 8–10 手）。",
        "fail": "打平接在亏损后面仍连着算。",
    },
    "marginal_entry_after_win": {
        "session": "场I 连赢 3 手后的 N=3 窗口内，边缘入池 1 次",
        "expect": "1（N 若产品不是 3，改窗口后重算）。连赢前的边缘入池不计。",
        "fail": "没有连赢也统计。",
    },
    "marginal_entry_after_loss": {
        "session": "场I 连亏 3 手后的 N=3 窗口内，边缘入池 1 次",
        "expect": "1。",
        "fail": "连亏前的边缘入池算进来。",
    },
    "weak_AK_entry_count": {
        "session": "场H：A5 入池、AT 入池、A5 fold",
        "expect": "1（仅 A5 入池）。",
        "fail": "AT 计入；A5 fold 计入。",
    },
    "low_connector_entry_count": {
        "session": "场H：54s 入池、JTs 入池、54s fold",
        "expect": "1。",
        "fail": "JTs 算边缘连张。",
    },
    "oop_marginal_entry_count": {
        "session": "场H：UTG 54s 入池、BTN 54s 入池",
        "expect": "1。",
        "fail": "BTN 那手算进来。",
    },
    "emotion_node_hand_range": {
        "session": "场I 第 8–10 手连亏，对应视频约 08:00–10:30",
        "expect": "区间写第 8～10 手，时间段与时间戳一致。",
        "fail": "没有连亏依据却画一个节点；区间与时间对不上。",
    },
}


def expect_for(code: str) -> dict[str, str]:
    return E.get(
        code,
        {
            "session": "按清单自备用户参与场 + 围观对照",
            "expect": "按统计方法手算。",
            "fail": "围观计入；或与手算不一致。",
        },
    )
