(() => {
  'use strict';

  const failures = {
    ALL: [
      ['MODEL_TIMEOUT', 141],
      ['MODEL_OUTPUT_TRUNCATED', 61],
      ['MODEL_STRUCTURED_OUTPUT_INVALID', 37],
      ['MODEL_UNAVAILABLE', 21],
      ['MODEL_RATE_LIMITED', 4],
    ],
    PREPARE: [
      ['INPUT_SCOPE_INVALID', 18],
      ['DATA_PLATFORM_NOT_READY', 11],
    ],
    AUTHOR: [
      ['MODEL_TIMEOUT', 86],
      ['MODEL_OUTPUT_TRUNCATED', 49],
      ['MODEL_STRUCTURED_OUTPUT_INVALID', 31],
    ],
    REVIEW: [
      ['MODEL_TIMEOUT', 55],
      ['MODEL_UNAVAILABLE', 14],
      ['MODEL_OUTPUT_TRUNCATED', 12],
    ],
  };

  const evalRows = [
    { model: 'gemini-3.7-flash', stage: 'REVIEW', stageName: '结果评审', n: 2721, bind: '—', harm: '—', leak: '—', score: '不打质量分', pass: '判过 18%', reco: 'keep', recoText: '保留主审', effective: '¥0.19' },
    { model: 'gpt-5.6-luna', stage: 'REVIEW', stageName: '结果评审', n: 27, bind: '—', harm: '—', leak: '—', score: '不打质量分', pass: '判过 22%', reco: 'thin', recoText: '样本不足', effective: '¥0.31' },
    { model: 'deepseek-v4-flash', stage: 'AUTHOR', stageName: '报告生成', n: 707, bind: '61%', harm: '3.1%', leak: '42%', score: '3.1', pass: '18%', reco: 'keep', recoText: '保留基线', effective: '¥0.13' },
    { model: 'doubao-seed-2-1-pro-260628', stage: 'AUTHOR', stageName: '报告生成', n: 37, bind: '48%', harm: '8.1%', leak: '27%', score: '2.9', pass: '14%', reco: 'wait', recoText: '停混跑，待对照', effective: '¥0.37' },
    { model: 'gemini-3.7-flash', stage: 'AUTHOR', stageName: '报告生成', n: 323, bind: '55%', harm: '5.6%', leak: '33%', score: '2.6', pass: '11%', reco: 'stop', recoText: '停用生成', effective: '¥0.41' },
    { model: 'gemini-3.7-flash', stage: 'FALLBACK', stageName: '兜底', n: 105, bind: '70%', harm: '2.0%', leak: '51%', score: '3.4', pass: '—', reco: 'stop', recoText: '测试期关闭', effective: '¥0.33' },
    { model: 'gpt-5.6-luna', stage: 'AUTHOR', stageName: '报告生成', n: 16, bind: '—', harm: '—', leak: '—', score: '—', pass: '—', reco: 'thin', recoText: '样本不足', effective: '—' },
    { model: '—', stage: 'PREPARE', stageName: '数据准备', n: 29, bind: '不进', harm: '不进', leak: '不进', score: '不进质量分', pass: '—', reco: 'thin', recoText: '非模型问题', effective: '¥0.00' },
  ];

  const reportKpis = {
    ALL: [
      ['证据绑定率', '61%', '四种报告加权', '程序 · 达标线 80%'],
      ['伤害性错误率', '4.8%', '盈亏、位置、摊牌写反或引用不存在的手', '程序 + 评审 · 出现即否决'],
      ['主泄漏抓对率', '38%', 'rank 1 改进打在本场最大问题上', '评审 · 抓错即否决'],
      ['建议可执行率', '54%', '改进含「下次遇到 X 就 Y」', '程序粗判 · 暂不否决'],
      ['终态成功率', '99.6%', '最终出了报告；含修订和兜底', '不等于写得对'],
      ['首轮通过率', '18%', '按新通过线重算，低于旧的 26%', '准确过线才算'],
    ],
    SESSION: [
      ['证据绑定率', '64%', '场次报告 · 手牌多更好挂', '程序 · 达标线 80%'],
      ['伤害性错误率', '3.6%', '场次里写反盈亏相对少', '程序 + 评审 · 出现即否决'],
      ['主泄漏抓对率', '44%', '单场主泄漏比跨场好抓', '评审 · 抓错即否决'],
      ['建议可执行率', '58%', '场次改进更容易写成硬规则', '程序粗判 · 暂不否决'],
      ['终态成功率', '99.5%', '场次最终大多能出报告', '不等于写得对'],
      ['首轮通过率', '21%', '四种里相对最好', '准确过线才算'],
    ],
    POSITION: [
      ['证据绑定率', '58%', '位置报告 · 要挂跨手证据', '程序 · 达标线 80%'],
      ['伤害性错误率', '4.1%', '位置写反仍会出现', '程序 + 评审 · 出现即否决'],
      ['主泄漏抓对率', '40%', '长期泄漏有时被单手戏剧带偏', '评审 · 抓错即否决'],
      ['建议可执行率', '51%', '位置建议容易写成套话', '程序粗判 · 暂不否决'],
      ['终态成功率', '99.3%', '位置最终大多能出报告', '不等于写得对'],
      ['首轮通过率', '16%', '低于场次，高于对手', '准确过线才算'],
    ],
    OPPONENT: [
      ['证据绑定率', '51%', '对手报告 · 引用对手手常对不上', '程序 · 达标线 80%'],
      ['伤害性错误率', '6.9%', '风格判断写反最多', '程序 + 评审 · 出现即否决'],
      ['主泄漏抓对率', '29%', '常抓最戏剧的一手，不是最大的钱', '评审 · 抓错即否决'],
      ['建议可执行率', '41%', '「打得紧一点」类套话多', '程序粗判 · 暂不否决'],
      ['终态成功率', '98.0%', '准备失败也最多（范围对不上）', '不等于写得对'],
      ['首轮通过率', '12%', '四种里最差', '准确过线才算'],
    ],
    HOME: [
      ['证据绑定率', '68%', '首页总结 · 样本少，数字波动大', '程序 · 达标线 80%'],
      ['伤害性错误率', '2.2%', '汇总较少点名单手', '程序 + 评审 · 出现即否决'],
      ['主泄漏抓对率', '47%', '主线相对好抓', '评审 · 抓错即否决'],
      ['建议可执行率', '61%', '总结更容易写成一条规则', '程序粗判 · 暂不否决'],
      ['终态成功率', '100%', '首页几乎都能出', '不等于写得对'],
      ['首轮通过率', '23%', '最好看，但 n 小', '准确过线才算'],
    ],
  };

  const reportStats = [
    { model: 'deepseek-v4-flash', duty: 'AUTHOR', dutyName: '生成', report: 'SESSION', reportName: '场次报告', n: 412, callOk: '98.5%', termOk: '99.5%', fail: 2, failWhy: '超时 2', first: '21%', bind: '64%', harm: '2.4%', leak: '46%', score: '3.2' },
    { model: 'deepseek-v4-flash', duty: 'AUTHOR', dutyName: '生成', report: 'POSITION', reportName: '位置报告', n: 148, callOk: '99.0%', termOk: '99.3%', fail: 1, failWhy: '截断 1', first: '16%', bind: '58%', harm: '3.0%', leak: '41%', score: '3.0' },
    { model: 'deepseek-v4-flash', duty: 'AUTHOR', dutyName: '生成', report: 'OPPONENT', reportName: '对手报告', n: 102, callOk: '97.2%', termOk: '98.0%', fail: 2, failWhy: '超时 1 · 结构非法 1', first: '12%', bind: '52%', harm: '4.8%', leak: '31%', score: '2.8' },
    { model: 'deepseek-v4-flash', duty: 'AUTHOR', dutyName: '生成', report: 'HOME', reportName: '首页总结', n: 45, callOk: '99.1%', termOk: '100%', fail: 0, failWhy: '—', first: '24%', bind: '70%', harm: '1.8%', leak: '48%', score: '3.3' },
    { model: 'gemini-3.7-flash', duty: 'AUTHOR', dutyName: '生成', report: 'SESSION', reportName: '场次报告', n: 180, callOk: '88.3%', termOk: '96.1%', fail: 7, failWhy: '超时 5 · 截断 2', first: '13%', bind: '58%', harm: '5.1%', leak: '35%', score: '2.7' },
    { model: 'gemini-3.7-flash', duty: 'AUTHOR', dutyName: '生成', report: 'POSITION', reportName: '位置报告', n: 68, callOk: '86.8%', termOk: '95.6%', fail: 3, failWhy: '超时 3', first: '10%', bind: '54%', harm: '5.9%', leak: '32%', score: '2.6' },
    { model: 'gemini-3.7-flash', duty: 'AUTHOR', dutyName: '生成', report: 'OPPONENT', reportName: '对手报告', n: 55, callOk: '84.0%', termOk: '92.7%', fail: 4, failWhy: '超时 3 · 不可用 1', first: '8%', bind: '49%', harm: '7.2%', leak: '24%', score: '2.4' },
    { model: 'gemini-3.7-flash', duty: 'AUTHOR', dutyName: '生成', report: 'HOME', reportName: '首页总结', n: 20, callOk: '90.0%', termOk: '100%', fail: 0, failWhy: '—', first: '15%', bind: '61%', harm: '3.8%', leak: '38%', score: '2.8' },
    { model: 'doubao-seed-2-1-pro', duty: 'AUTHOR', dutyName: '生成', report: 'SESSION', reportName: '场次报告', n: 22, callOk: '95.5%', termOk: '100%', fail: 0, failWhy: '—', first: '16%', bind: '50%', harm: '7.4%', leak: '29%', score: '2.9' },
    { model: 'doubao-seed-2-1-pro', duty: 'AUTHOR', dutyName: '生成', report: 'POSITION', reportName: '位置报告', n: 6, callOk: '100%', termOk: '100%', fail: 0, failWhy: '—', first: '12%', bind: '47%', harm: '8.0%', leak: '25%', score: '2.8' },
    { model: 'doubao-seed-2-1-pro', duty: 'AUTHOR', dutyName: '生成', report: 'OPPONENT', reportName: '对手报告', n: 7, callOk: '85.7%', termOk: '85.7%', fail: 1, failWhy: '结构非法 1', first: '9%', bind: '41%', harm: '11%', leak: '18%', score: '2.5' },
    { model: 'doubao-seed-2-1-pro', duty: 'AUTHOR', dutyName: '生成', report: 'HOME', reportName: '首页总结', n: 2, callOk: '100%', termOk: '100%', fail: 0, failWhy: '—', first: '—', bind: '—', harm: '—', leak: '—', score: '—' },
    { model: 'gemini-3.7-flash', duty: 'REVIEW', dutyName: '评审', report: 'SESSION', reportName: '场次报告', n: 1480, callOk: '95.4%', termOk: '—', fail: 68, failWhy: '超时 48 · 截断 12', first: '判过 19%', bind: '—', harm: '—', leak: '—', score: '不打质量分' },
    { model: 'gemini-3.7-flash', duty: 'REVIEW', dutyName: '评审', report: 'POSITION', reportName: '位置报告', n: 520, callOk: '95.0%', termOk: '—', fail: 26, failWhy: '超时 18', first: '判过 17%', bind: '—', harm: '—', leak: '—', score: '不打质量分' },
    { model: 'gemini-3.7-flash', duty: 'REVIEW', dutyName: '评审', report: 'OPPONENT', reportName: '对手报告', n: 510, callOk: '94.1%', termOk: '—', fail: 30, failWhy: '超时 21 · 不可用 6', first: '判过 14%', bind: '—', harm: '—', leak: '—', score: '不打质量分' },
    { model: 'gemini-3.7-flash', duty: 'REVIEW', dutyName: '评审', report: 'HOME', reportName: '首页总结', n: 211, callOk: '96.2%', termOk: '—', fail: 8, failWhy: '超时 6', first: '判过 22%', bind: '—', harm: '—', leak: '—', score: '不打质量分' },
    { model: 'gpt-5.6-luna', duty: 'REVIEW', dutyName: '评审', report: 'SESSION', reportName: '场次报告', n: 14, callOk: '100%', termOk: '—', fail: 0, failWhy: '—', first: '判过 21%', bind: '—', harm: '—', leak: '—', score: '不打质量分' },
    { model: 'gpt-5.6-luna', duty: 'REVIEW', dutyName: '评审', report: 'POSITION', reportName: '位置报告', n: 5, callOk: '100%', termOk: '—', fail: 0, failWhy: '—', first: '—', bind: '—', harm: '—', leak: '—', score: '不打质量分' },
    { model: 'gpt-5.6-luna', duty: 'REVIEW', dutyName: '评审', report: 'OPPONENT', reportName: '对手报告', n: 6, callOk: '100%', termOk: '—', fail: 0, failWhy: '—', first: '判过 17%', bind: '—', harm: '—', leak: '—', score: '不打质量分' },
    { model: 'gpt-5.6-luna', duty: 'REVIEW', dutyName: '评审', report: 'HOME', reportName: '首页总结', n: 2, callOk: '100%', termOk: '—', fail: 0, failWhy: '—', first: '—', bind: '—', harm: '—', leak: '—', score: '不打质量分' },
    { model: '—（程序）', duty: 'PREPARE', dutyName: '准备', report: 'SESSION', reportName: '场次报告', n: 6, callOk: '—', termOk: '0%', fail: 6, failWhy: '范围无效 4 · 事实未就绪 2', first: '不进', bind: '不进', harm: '不进', leak: '不进', score: '不进质量分' },
    { model: '—（程序）', duty: 'PREPARE', dutyName: '准备', report: 'POSITION', reportName: '位置报告', n: 4, callOk: '—', termOk: '0%', fail: 4, failWhy: '范围无效 3 · 事实未就绪 1', first: '不进', bind: '不进', harm: '不进', leak: '不进', score: '不进质量分' },
    { model: '—（程序）', duty: 'PREPARE', dutyName: '准备', report: 'OPPONENT', reportName: '对手报告', n: 16, callOk: '—', termOk: '0%', fail: 16, failWhy: '范围无效 11 · 事实未就绪 5', first: '不进', bind: '不进', harm: '不进', leak: '不进', score: '不进质量分' },
    { model: '—（程序）', duty: 'PREPARE', dutyName: '准备', report: 'HOME', reportName: '首页总结', n: 3, callOk: '—', termOk: '0%', fail: 3, failWhy: '事实未就绪 3', first: '不进', bind: '不进', harm: '不进', leak: '不进', score: '不进质量分' },
  ];

  const heatModels = [
    { model: 'deepseek-v4-flash', SESSION: '21%', POSITION: '16%', OPPONENT: '12%', HOME: '24%' },
    { model: 'gemini-3.7-flash · 写稿', SESSION: '13%', POSITION: '10%', OPPONENT: '8%', HOME: '15%' },
    { model: 'doubao-seed-2-1-pro', SESSION: '16%', POSITION: '12%', OPPONENT: '9%', HOME: '—' },
  ];

  let evalDuty = 'ALL';

  const callSlots = [
    {
      key: 'SESSION',
      name: '场次报告',
      job: '这场怎么打、主泄漏在哪',
      prepare: '进入 418，程序失败 6（范围无效 4 · 事实未就绪 2）。准备失败不调模型、不重试，不进质量账。',
      generate: {
        pinned: 'deepseek-v4-flash',
        mix: '钉死 deepseek。混跑残留：Gemini 写了 14%，豆包 5%。对照样本来自旧混跑，不是钉死后的 A/B。',
        did: '写了 412 份场次稿，按审核意见改了 326 份。不给自己打分，也不当审核。',
        call: [['样本', '412'], ['调用成功', '98.5%'], ['超时', '2'], ['截断', '0'], ['P95', '10.9秒'], ['token', '56k / 1.1k'], ['单份', '¥0.13'], ['本窗口', '¥53']],
        quality: [['绑定', '64%'], ['伤害', '2.4%'], ['主泄漏', '46%'], ['可执行', '58%'], ['综合分', '3.2'], ['首轮过', '21%'], ['修订变好', '43%']],
        effective: '¥0.62',
        reco: 'keep',
        recoText: '留用生成基线',
        recoWhy: '四种里场次最好写。有效成本低于两个挑战者，先钉死再加对照。',
        fails: [['MODEL_TIMEOUT', 2, '写稿超时，报告未写出']],
        retry: { n: 6, avg: '1.2', max: 2, recovered: 5 },
        outcome: { first: 405, retry1: 4, retry2: 1, fail: 2 },
        challengers: [
          { model: 'doubao-seed-2-1-pro', n: '22', call: '95.5%', first: '16%', cost: '¥0.37', effective: '¥2.31', reco: 'wait', recoText: '不换 · 样本少且更贵' },
          { model: 'gemini-3.7-flash', n: '180', call: '88.3%', first: '13%', cost: '¥0.41', effective: '¥3.15', reco: 'stop', recoText: '停用生成 · 又慢又贵' },
        ],
      },
      review: {
        pinned: 'gemini-3.7-flash',
        mix: '钉死 Gemini 主审。混跑残留：Gemini 自己写过 14% 的场次稿，那部分不能当评审对照。',
        did: '评了 412 份，判过 86 份（21%）。只打分、抓主泄漏，不改正文。程序先算绑定和伤害。',
        call: [['样本', '412'], ['调用成功', '95.4%'], ['超时', '13'], ['截断', '4'], ['不可用', '2'], ['P95', '25秒'], ['token', '61k / 0.8k'], ['单份', '¥0.19'], ['本窗口', '¥78']],
        quality: [['判过', '21%'], ['业务不过', '79%'], ['调用失败', '19'], ['事实均分', '3.6'], ['主泄漏抓错', '110']],
        effective: '¥0.20',
        reco: 'keep',
        recoText: '留用主审',
        recoWhy: '调用失败和业务不通过要分开。判过低主要是稿差。GPT 样本不够，不能换。',
        fails: [['MODEL_TIMEOUT', 13, '审核超时，没打出分'], ['MODEL_OUTPUT_TRUNCATED', 4, '审核输出被截断'], ['MODEL_UNAVAILABLE', 2, '审核不可用']],
        retry: { n: 24, avg: '1.3', max: 2, recovered: 12 },
        outcome: { first: 381, retry1: 9, retry2: 3, fail: 19 },
        challengers: [
          { model: 'gpt-5.6-luna', n: '14', call: '92.9%', first: '21%', cost: '¥0.31', effective: '¥0.33', reco: 'thin', recoText: '样本不足 · 暂不换' },
        ],
      },
    },
    {
      key: 'POSITION',
      name: '位置报告',
      job: '这个位置长期泄漏',
      prepare: '进入 152，程序失败 4（该位置无匹配手 3 · 事实未就绪 1）。不进生成。',
      generate: {
        pinned: 'deepseek-v4-flash',
        mix: '钉死 deepseek。混跑残留：Gemini 写了 12%。',
        did: '写了 148 份位置稿，改了 124 份。跨手证据比场次更难挂。',
        call: [['样本', '148'], ['调用成功', '99.0%'], ['超时', '0'], ['截断', '1'], ['P95', '11.4秒'], ['token', '58k / 1.2k'], ['单份', '¥0.14'], ['本窗口', '¥21']],
        quality: [['绑定', '58%'], ['伤害', '3.0%'], ['主泄漏', '41%'], ['可执行', '51%'], ['综合分', '3.0'], ['首轮过', '16%'], ['修订变好', '39%']],
        effective: '¥0.88',
        reco: 'keep',
        recoText: '留用，质量弱于场次',
        recoWhy: '套话比例高，但挑战者更差。先钉死，再单独开位置对照。',
        fails: [['MODEL_OUTPUT_TRUNCATED', 1, '写稿被截断']],
        retry: { n: 2, avg: '1.0', max: 2, recovered: 2 },
        outcome: { first: 145, retry1: 2, retry2: 0, fail: 1 },
        challengers: [
          { model: 'gemini-3.7-flash', n: '22', call: '86.4%', first: '9%', cost: '¥0.43', effective: '¥4.78', reco: 'stop', recoText: '停用生成' },
        ],
      },
      review: {
        pinned: 'gemini-3.7-flash',
        mix: '钉死 Gemini 主审。长期泄漏有时被单手戏剧带偏。',
        did: '评了 148 份，判过 24 份（16%）。不改正文。',
        call: [['样本', '148'], ['调用成功', '95.0%'], ['超时', '5'], ['截断', '2'], ['P95', '28秒'], ['token', '63k / 0.9k'], ['单份', '¥0.20'], ['本窗口', '¥30']],
        quality: [['判过', '16%'], ['业务不过', '84%'], ['调用失败', '7'], ['事实均分', '3.4'], ['主泄漏抓错', '48']],
        effective: '¥0.21',
        reco: 'keep',
        recoText: '留用主审',
        recoWhy: '超时略高于场次。判过低仍是稿差。',
        fails: [['MODEL_TIMEOUT', 5, '审核超时'], ['MODEL_OUTPUT_TRUNCATED', 2, '审核截断']],
        retry: { n: 11, avg: '1.2', max: 2, recovered: 7 },
        outcome: { first: 134, retry1: 5, retry2: 2, fail: 7 },
        challengers: [
          { model: 'gpt-5.6-luna', n: '8', call: '87.5%', first: '13%', cost: '¥0.34', effective: '¥0.39', reco: 'thin', recoText: '样本不足' },
        ],
      },
    },
    {
      key: 'OPPONENT',
      name: '对手报告',
      job: '对面风格和应对',
      prepare: '进入 118，程序失败 16（13.6%，四种最高：对手范围无匹配手 11 · 统计未就绪 5）。这是数据问题，不是模型质量。',
      generate: {
        pinned: 'deepseek-v4-flash',
        mix: '钉死 deepseek。混跑残留：Gemini 写了 16%，豆包 5%。',
        did: '写了 102 份对手稿，改了 90 份。风格判断最容易写反，修订也最不值钱。',
        call: [['样本', '102'], ['调用成功', '97.2%'], ['超时', '1'], ['非法输出', '1'], ['P95', '12.6秒'], ['token', '62k / 1.3k'], ['单份', '¥0.16'], ['本窗口', '¥16']],
        quality: [['绑定', '52%'], ['伤害', '4.8%'], ['主泄漏', '31%'], ['可执行', '41%'], ['综合分', '2.8'], ['首轮过', '12%'], ['修订变好', '33%']],
        effective: '¥1.33',
        reco: 'wait',
        recoText: '留用但优先换生成',
        recoWhy: '质量最差、有效成本最高。挑战者更差，所以现在不换，但这里是下一次选模的第一优先级。',
        fails: [['MODEL_TIMEOUT', 1, '写稿超时'], ['MODEL_STRUCTURED_OUTPUT_INVALID', 1, '结构化输出非法']],
        retry: { n: 5, avg: '1.7', max: 2, recovered: 3 },
        outcome: { first: 97, retry1: 2, retry2: 1, fail: 2 },
        challengers: [
          { model: 'doubao-seed-2-1-pro', n: '9', call: '88.9%', first: '11%', cost: '¥0.41', effective: '¥3.73', reco: 'thin', recoText: '样本不足' },
          { model: 'gemini-3.7-flash', n: '18', call: '83.3%', first: '6%', cost: '¥0.48', effective: '¥8.00', reco: 'stop', recoText: '停用生成' },
        ],
      },
      review: {
        pinned: 'gemini-3.7-flash',
        mix: '钉死 Gemini 主审。判过最低，主要是稿差，不是审核更严。',
        did: '评了 102 份，判过 12 份（12%）。不改正文。',
        call: [['样本', '102'], ['调用成功', '94.1%'], ['超时', '4'], ['不可用', '2'], ['P95', '31秒'], ['token', '66k / 1.0k'], ['单份', '¥0.22'], ['本窗口', '¥22']],
        quality: [['判过', '12%'], ['业务不过', '88%'], ['调用失败', '6'], ['事实均分', '3.1'], ['主泄漏抓错', '41']],
        effective: '¥0.23',
        reco: 'keep',
        recoText: '留用主审',
        recoWhy: '不要因为判过低就换审核。先把生成岗换好。',
        fails: [['MODEL_TIMEOUT', 4, '审核超时'], ['MODEL_UNAVAILABLE', 2, '审核不可用']],
        retry: { n: 10, avg: '1.3', max: 2, recovered: 6 },
        outcome: { first: 90, retry1: 4, retry2: 2, fail: 6 },
        challengers: [
          { model: 'gpt-5.6-luna', n: '6', call: '83.3%', first: '17%', cost: '¥0.36', effective: '¥0.43', reco: 'thin', recoText: '样本不足' },
        ],
      },
    },
    {
      key: 'HOME',
      name: '首页总结',
      job: '多场汇总给用户看',
      prepare: '进入 48，程序失败 3（多场汇总事实未就绪）。',
      generate: {
        pinned: 'deepseek-v4-flash',
        mix: '钉死 deepseek。混跑残留：Gemini 写了 10%。',
        did: '写了 45 份首页总结，改了 34 份。较少点名单手，伤害低。',
        call: [['样本', '45'], ['调用成功', '99.1%'], ['超时', '0'], ['截断', '0'], ['P95', '9.8秒'], ['token', '48k / 0.9k'], ['单份', '¥0.11'], ['本窗口', '¥5']],
        quality: [['绑定', '70%'], ['伤害', '1.8%'], ['主泄漏', '48%'], ['可执行', '61%'], ['综合分', '3.3'], ['首轮过', '24%'], ['修订变好', '48%']],
        effective: '¥0.46',
        reco: 'thin',
        recoText: '留用 · 样本偏少',
        recoWhy: '四种里最好看，但 n=45，数字会跳。不要据此换别的岗。',
        fails: [],
        retry: { n: 0, avg: '0', max: 2, recovered: 0 },
        outcome: { first: 45, retry1: 0, retry2: 0, fail: 0 },
        challengers: [
          { model: 'gemini-3.7-flash', n: '5', call: '80.0%', first: '20%', cost: '¥0.38', effective: '¥1.90', reco: 'thin', recoText: '样本不足' },
        ],
      },
      review: {
        pinned: 'gemini-3.7-flash',
        mix: '钉死 Gemini 主审。四种里最好看，同样受样本限制。',
        did: '评了 45 份，判过 11 份（24%）。不改正文。',
        call: [['样本', '45'], ['调用成功', '96.2%'], ['超时', '2'], ['P95', '22秒'], ['token', '52k / 0.7k'], ['单份', '¥0.18'], ['本窗口', '¥8']],
        quality: [['判过', '24%'], ['业务不过', '76%'], ['调用失败', '2'], ['事实均分', '3.8'], ['主泄漏抓错', '12']],
        effective: '¥0.19',
        reco: 'thin',
        recoText: '留用 · 样本偏少',
        recoWhy: '不能用首页总结的分数去证明 Gemini 适合写稿。',
        fails: [['MODEL_TIMEOUT', 2, '审核超时']],
        retry: { n: 3, avg: '1.5', max: 2, recovered: 2 },
        outcome: { first: 41, retry1: 2, retry2: 0, fail: 2 },
        challengers: [
          { model: 'gpt-5.6-luna', n: '4', call: '100%', first: '25%', cost: '¥0.29', effective: '¥0.29', reco: 'thin', recoText: '样本不足' },
        ],
      },
    },
  ];

  const spendShare = [
    { model: 'gemini-3.7-flash', work: '评审 ¥214 · 写稿 ¥88', calls: 3044, yen: 302, pct: 59, unit: '¥0.10', color: '#1677d2' },
    { model: 'deepseek-v4-flash', work: '钉死生成', calls: 4081, yen: 126, pct: 25, unit: '¥0.03', color: '#176f59' },
    { model: 'doubao-seed-2-1-pro', work: '历史混跑写稿', calls: 223, yen: 41, pct: 8, unit: '¥0.18', color: '#7147d9' },
    { model: 'gpt-5.6-luna', work: '评审 ¥16 · 写稿 ¥9', calls: 43, yen: 25, pct: 5, unit: '¥0.58', color: '#e86f16' },
    { model: 'deepseek-flash', work: '旧生成线路', calls: 285, yen: 18, pct: 3, unit: '¥0.06', color: '#c4b078' },
  ];

  const modelView = [
    {
      model: 'deepseek-v4-flash',
      work: '钉死生成',
      p50: '6.8秒',
      p95: '11.2秒',
      biz: {
        SESSION: { jobs: 2370, fail: 46, p50: '6.4秒', p95: '10.9秒' },
        POSITION: { jobs: 854, fail: 20, p50: '7.1秒', p95: '11.4秒' },
        OPPONENT: { jobs: 587, fail: 22, p50: '7.6秒', p95: '12.6秒' },
        HOME: { jobs: 270, fail: 0, p50: '5.9秒', p95: '9.8秒' },
      },
    },
    {
      model: 'gemini-3.7-flash',
      work: '钉死审核 · 旧混跑写稿',
      p50: '14.2秒',
      p95: '25.8秒',
      biz: {
        SESSION: { jobs: 1660, fail: 72, author: 180, review: 1480, p50: '13.6秒', p95: '25.0秒' },
        POSITION: { jobs: 588, fail: 36, author: 68, review: 520, p50: '15.1秒', p95: '28.0秒' },
        OPPONENT: { jobs: 565, fail: 44, author: 55, review: 510, p50: '16.4秒', p95: '31.0秒' },
        HOME: { jobs: 231, fail: 20, author: 20, review: 211, p50: '12.8秒', p95: '22.0秒' },
      },
    },
    {
      model: 'doubao-seed-2-1-pro',
      work: '历史混跑写稿',
      p50: '8.4秒',
      p95: '14.6秒',
      biz: {
        SESSION: { jobs: 132, fail: 2, p50: '8.1秒', p95: '13.8秒' },
        POSITION: { jobs: 36, fail: 0, p50: '8.6秒', p95: '14.2秒' },
        OPPONENT: { jobs: 42, fail: 2, p50: '9.4秒', p95: '16.1秒' },
        HOME: { jobs: 13, fail: 0, p50: '7.2秒', p95: '11.5秒' },
      },
    },
    {
      model: 'gpt-5.6-luna',
      work: '审核对照 · 少量写稿',
      p50: '11.0秒',
      p95: '18.4秒',
      biz: {
        SESSION: { jobs: 22, fail: 0, p50: '10.6秒', p95: '17.2秒' },
        POSITION: { jobs: 8, fail: 0, p50: '11.4秒', p95: '18.8秒' },
        OPPONENT: { jobs: 10, fail: 0, p50: '12.1秒', p95: '19.6秒' },
        HOME: { jobs: 3, fail: 0, p50: '9.8秒', p95: '15.4秒' },
      },
    },
    {
      model: 'deepseek-flash',
      work: '旧生成线路',
      p50: '5.1秒',
      p95: '8.4秒',
      biz: {
        SESSION: { jobs: 166, fail: 0, p50: '4.9秒', p95: '8.1秒' },
        POSITION: { jobs: 60, fail: 0, p50: '5.3秒', p95: '8.6秒' },
        OPPONENT: { jobs: 41, fail: 0, p50: '5.8秒', p95: '9.2秒' },
        HOME: { jobs: 18, fail: 0, p50: '4.6秒', p95: '7.4秒' },
      },
    },
  ];

  const overallCallStats = {
    jobs: 7676,
    ok: 7412,
    fail: 264,
    first: 7018,
    retry1: 318,
    retry2: 76,
    author: { jobs: 4928, ok: 4796, fail: 132, first: 4580, retry1: 172, retry2: 44 },
    review: { jobs: 2748, ok: 2616, fail: 132, first: 2438, retry1: 146, retry2: 32 },
  };

  const failReasonMeta = {
    MODEL_TIMEOUT: { name: '超时', detail: '调用超时，未返回完整结果', color: '#a0392d' },
    MODEL_OUTPUT_TRUNCATED: { name: '截断', detail: '输出长度超限被截断', color: '#e86f16' },
    MODEL_STRUCTURED_OUTPUT_INVALID: { name: '结构非法', detail: '结构化输出未通过校验', color: '#856522' },
    MODEL_UNAVAILABLE: { name: '不可用', detail: '模型服务不可用', color: '#637570' },
    MODEL_RATE_LIMITED: { name: '限流', detail: '触发限流，请求被拒绝', color: '#c4b078' },
  };

  const failDist = [
    { report: 'SESSION', reportName: '场次报告', duty: 'AUTHOR', dutyName: '生成', model: 'deepseek-v4-flash', code: 'MODEL_TIMEOUT', n: 26 },
    { report: 'SESSION', reportName: '场次报告', duty: 'AUTHOR', dutyName: '生成', model: 'deepseek-v4-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 14 },
    { report: 'SESSION', reportName: '场次报告', duty: 'AUTHOR', dutyName: '生成', model: 'deepseek-v4-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 6 },
    { report: 'SESSION', reportName: '场次报告', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_TIMEOUT', n: 5 },
    { report: 'SESSION', reportName: '场次报告', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 3 },
    { report: 'SESSION', reportName: '场次报告', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 2 },
    { report: 'SESSION', reportName: '场次报告', duty: 'AUTHOR', dutyName: '生成', model: 'doubao-seed-2-1-pro', code: 'MODEL_TIMEOUT', n: 1 },
    { report: 'SESSION', reportName: '场次报告', duty: 'AUTHOR', dutyName: '生成', model: 'doubao-seed-2-1-pro', code: 'MODEL_OUTPUT_TRUNCATED', n: 1 },
    { report: 'POSITION', reportName: '位置报告', duty: 'AUTHOR', dutyName: '生成', model: 'deepseek-v4-flash', code: 'MODEL_TIMEOUT', n: 10 },
    { report: 'POSITION', reportName: '位置报告', duty: 'AUTHOR', dutyName: '生成', model: 'deepseek-v4-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 7 },
    { report: 'POSITION', reportName: '位置报告', duty: 'AUTHOR', dutyName: '生成', model: 'deepseek-v4-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 3 },
    { report: 'POSITION', reportName: '位置报告', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_TIMEOUT', n: 4 },
    { report: 'POSITION', reportName: '位置报告', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 2 },
    { report: 'POSITION', reportName: '位置报告', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 2 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'AUTHOR', dutyName: '生成', model: 'deepseek-v4-flash', code: 'MODEL_TIMEOUT', n: 12 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'AUTHOR', dutyName: '生成', model: 'deepseek-v4-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 6 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'AUTHOR', dutyName: '生成', model: 'deepseek-v4-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 4 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_TIMEOUT', n: 5 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 4 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 3 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'AUTHOR', dutyName: '生成', model: 'doubao-seed-2-1-pro', code: 'MODEL_TIMEOUT', n: 1 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'AUTHOR', dutyName: '生成', model: 'doubao-seed-2-1-pro', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 1 },
    { report: 'HOME', reportName: '首页总结', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_TIMEOUT', n: 4 },
    { report: 'HOME', reportName: '首页总结', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 2 },
    { report: 'HOME', reportName: '首页总结', duty: 'AUTHOR', dutyName: '生成', model: 'gemini-3.7-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 4 },
    { report: 'SESSION', reportName: '场次报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_TIMEOUT', n: 36 },
    { report: 'SESSION', reportName: '场次报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 10 },
    { report: 'SESSION', reportName: '场次报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 4 },
    { report: 'SESSION', reportName: '场次报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_UNAVAILABLE', n: 9 },
    { report: 'SESSION', reportName: '场次报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_RATE_LIMITED', n: 3 },
    { report: 'POSITION', reportName: '位置报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_TIMEOUT', n: 16 },
    { report: 'POSITION', reportName: '位置报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 5 },
    { report: 'POSITION', reportName: '位置报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 3 },
    { report: 'POSITION', reportName: '位置报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_UNAVAILABLE', n: 4 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_TIMEOUT', n: 16 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 5 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 4 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_UNAVAILABLE', n: 6 },
    { report: 'OPPONENT', reportName: '对手报告', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_RATE_LIMITED', n: 1 },
    { report: 'HOME', reportName: '首页总结', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_TIMEOUT', n: 5 },
    { report: 'HOME', reportName: '首页总结', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_OUTPUT_TRUNCATED', n: 2 },
    { report: 'HOME', reportName: '首页总结', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_STRUCTURED_OUTPUT_INVALID', n: 1 },
    { report: 'HOME', reportName: '首页总结', duty: 'REVIEW', dutyName: '审核', model: 'gemini-3.7-flash', code: 'MODEL_UNAVAILABLE', n: 2 },
  ];

  const failCodes = ['MODEL_TIMEOUT', 'MODEL_OUTPUT_TRUNCATED', 'MODEL_STRUCTURED_OUTPUT_INVALID', 'MODEL_UNAVAILABLE', 'MODEL_RATE_LIMITED'];
  const reportColors = { SESSION: '#176f59', POSITION: '#1677d2', OPPONENT: '#e86f16', HOME: '#7147d9' };
  const modelColors = { 'deepseek-v4-flash': '#176f59', 'gemini-3.7-flash': '#1677d2', 'doubao-seed-2-1-pro': '#7147d9', 'gpt-5.6-luna': '#e86f16', 'deepseek-flash': '#c4b078' };
  const modelShort = { 'deepseek-v4-flash': 'deepseek-v4', 'gemini-3.7-flash': 'gemini', 'doubao-seed-2-1-pro': 'doubao', 'gpt-5.6-luna': 'gpt', 'deepseek-flash': 'ds-flash' };
  const reportKeys = ['SESSION', 'POSITION', 'OPPONENT', 'HOME'];
  const reportShort = { SESSION: '场次', POSITION: '位置', OPPONENT: '对手', HOME: '首页' };

  const details = {
    7122: {
      title: '场次报告 #7122',
      state: '混跑样本。生成是豆包，评审是 Gemini。第 1 轮绑定不够且主泄漏抓错，第 2 轮出现伤害性错误，第 3 轮换模重写后才过。',
      meta: [
        ['生成模型', 'doubao-seed-2-1-pro · 只写稿'],
        ['评审模型', 'gemini-3.7-flash · 只打分'],
        ['通过线', '无伤害错误，绑定 ≥ 80%，主泄漏抓对，事实 ≥ 4，综合 ≥ 4.0'],
        ['本份终局', '第 3 轮才过；前两轮被硬指标卡住'],
        ['首轮通过', '否'],
        ['调用次数', '7'],
        ['生成耗时', '4 分 49.1 秒'],
        ['估算成本', '¥1.86（示意）'],
      ],
      path: [
        { who: '程序', label: '准备', state: 'done' },
        { who: '豆包', label: '写稿', state: 'done' },
        { who: 'Gemini', label: '不过', state: 'fail' },
        { who: '豆包', label: '修订', state: 'done' },
        { who: 'Gemini', label: '否决', state: 'fail' },
        { who: 'Gemini', label: '兜底写', state: 'warn' },
        { who: 'Gemini', label: '通过', state: 'pass' },
      ],
      attempts: [
        { seq: '1', duty: '生成写稿', round: '1', model: 'doubao-seed-2-1-pro', duration: '1 分 0.8 秒', tokens: '82.1k / 1.2k', cost: '¥0.22', result: '稿件已写出', note: '调用成功 ≠ 报告通过，等评审', kind: 'write', quality: { bind: '45%', bindOk: false, action: '套话' } },
        { seq: '2', duty: '生成写稿', round: '1', model: 'doubao-seed-2-1-pro', duration: '31.2 秒', tokens: '83.4k / 1.2k', cost: '¥0.22', result: '稿件已写出', note: '结构化输出重试', kind: 'write', quality: { bind: '48%', bindOk: false, action: '套话' } },
        { seq: '3', duty: '评审打分', round: '1', model: 'gemini-3.7-flash', duration: '25.0 秒', tokens: '81.8k / 0.5k', cost: '¥0.31', result: '不通过', note: '绑定 48% < 80%，主泄漏抓错', kind: 'fail', score: { total: '3.0', fact: 3, logic: 2, structure: 4, scope: 4 }, quality: { bind: '48%', bindOk: false, harm: '无', leak: '抓错', action: '套话' } },
        { seq: '4', duty: '生成修订', round: '2', model: 'doubao-seed-2-1-pro', duration: '39.4 秒', tokens: '84.0k / 1.2k', cost: '¥0.23', result: '按评审意见改写', note: '绑定略升，但写出了不存在的手', kind: 'write', quality: { bind: '52%', bindOk: false, harm: '有', action: '半条规则' } },
        { seq: '5', duty: '评审打分', round: '2', model: 'gemini-3.7-flash', duration: '1 分 19.1 秒', tokens: '81.9k / 0.6k', cost: '¥0.34', result: '一票否决', note: '伤害性错误：引用不存在的手；事实 2 分', kind: 'fail', score: { total: '2.9', fact: 2, logic: 3, structure: 4, scope: 4 }, quality: { bind: '52%', bindOk: false, harm: '有', leak: '抓错', action: '半条规则' } },
        { seq: '6', duty: '兜底重写', round: '3', model: 'gemini-3.7-flash', duration: '36.8 秒', tokens: '81.6k / 0.9k', cost: '¥0.33', result: '稿件已写出', note: '测试期应关闭；此条是旧混跑', kind: 'write', quality: { bind: '84%', bindOk: true, action: '可执行' } },
        { seq: '7', duty: '评审打分', round: '3', model: 'gemini-3.7-flash', duration: '16.7 秒', tokens: '82.0k / 0.4k', cost: '¥0.21', result: '通过 4.2', note: '硬指标全过，综合 4.2，事实 4', kind: 'pass', score: { total: '4.2', fact: 4, logic: 4, structure: 5, scope: 4 }, quality: { bind: '84%', bindOk: true, harm: '无', leak: '抓对', action: '可执行' } },
      ],
    },
    6074: {
      title: '场次报告 #6074',
      state: '钉死策略下的合格路径：生成只写一次。旧口径综合 4.2 就算过；新口径还要看绑定、伤害、主泄漏，这份刚好都过。',
      meta: [
        ['生成模型', 'deepseek-v4-flash · 只写稿'],
        ['评审模型', 'gemini-3.7-flash · 只打分'],
        ['通过线', '无伤害错误，绑定 ≥ 80%，主泄漏抓对，事实 ≥ 4，综合 ≥ 4.0'],
        ['本份终局', '第 1 轮评审通过'],
        ['首轮通过', '是'],
        ['调用次数', '2'],
        ['生成耗时', '1 分 16.7 秒'],
        ['估算成本', '¥0.29（示意）'],
      ],
      path: [
        { who: '程序', label: '准备', state: 'done' },
        { who: 'deepseek', label: '写稿', state: 'done' },
        { who: 'Gemini', label: '通过', state: 'pass' },
      ],
      attempts: [
        { seq: '1', duty: '生成写稿', round: '1', model: 'deepseek-v4-flash', duration: '53.1 秒', tokens: '56.4k / 1.1k', cost: '¥0.08', result: '稿件已写出', note: '等待评审', kind: 'write', quality: { bind: '84%', bindOk: true, action: '可执行' } },
        { seq: '2', duty: '评审打分', round: '1', model: 'gemini-3.7-flash', duration: '23.5 秒', tokens: '57.1k / 0.5k', cost: '¥0.21', result: '通过 4.2', note: '绑定 84%，无伤害错误，主泄漏抓对', kind: 'pass', score: { total: '4.2', fact: 4, logic: 4, structure: 4, scope: 5 }, quality: { bind: '84%', bindOk: true, harm: '无', leak: '抓对', action: '可执行' } },
      ],
    },
    5960: {
      title: '对手报告 #5960',
      state: '数据准备失败，评审规则还没开始。',
      meta: [
        ['生成模型', '未调用'],
        ['评审模型', '未调用'],
        ['失败节点', '数据准备'],
        ['失败代码', 'DATA_PLATFORM_NOT_READY'],
        ['调用次数', '0'],
        ['估算成本', '¥0.00'],
      ],
      path: [
        { who: '程序', label: '准备失败', state: 'fail' },
        { who: '未调用', label: '写稿', state: 'skip' },
        { who: '未调用', label: '评审', state: 'skip' },
      ],
      attempts: [],
      message: '事实数据未就绪。准备失败走系统规则，不打 1–5 分，也不计入生成/评审质量。',
    },
  };

  function showTab(name) {
    const map = { health: 'health-tab-panel', eval: 'eval-tab-panel', query: 'query-tab-panel' };
    Object.entries(map).forEach(([key, id]) => {
      document.getElementById(id).hidden = key !== name;
      document.getElementById(key + '-tab').setAttribute('aria-selected', String(key === name));
    });
  }

  function renderFailures(stage) {
    const list = document.getElementById('failure-reasons');
    list.replaceChildren();
    for (const [code, count] of failures[stage] || failures.ALL) {
      const li = document.createElement('li');
      li.textContent = `${code}：${count} 次`;
      list.append(li);
    }
  }

  function renderEval(stage) {
    const body = document.getElementById('eval-rows');
    body.replaceChildren();
    const rows = evalRows.filter((row) => stage === 'ALL' || row.stage === stage);
    for (const row of rows) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${row.model}</td><td>${row.stageName}<span class="detail">n=${row.n}</span></td><td>${row.bind}</td><td>${row.harm}</td><td>${row.leak}</td><td class="score">${row.score}</td><td>${row.pass}</td><td>${row.effective}</td>`;
      body.append(tr);
    }
  }

  function renderKpis(report) {
    const grid = document.getElementById('quality-kpis');
    grid.replaceChildren();
    for (const [label, value, detail, src] of reportKpis[report] || reportKpis.ALL) {
      const article = document.createElement('article');
      article.innerHTML = `<span>${label}</span><strong>${value}</strong><span class="detail">${detail}</span><span class="metric-src">${src}</span>`;
      grid.append(article);
    }
  }

  function heatClass(pct) {
    if (!pct || pct === '—') return 'empty';
    const n = Number(String(pct).replace('%', ''));
    if (n >= 20) return 'high';
    if (n >= 14) return 'mid';
    return 'low';
  }

  function renderHeat() {
    const box = document.getElementById('report-heat');
    box.replaceChildren();
    ['', '场次报告', '位置报告', '对手报告', '首页总结'].forEach((text) => {
      const span = document.createElement('span');
      span.className = 'heat-head';
      span.textContent = text;
      box.append(span);
    });
    heatModels.forEach((row) => {
      const label = document.createElement('span');
      label.className = 'heat-label';
      label.textContent = row.model;
      box.append(label);
      ['SESSION', 'POSITION', 'OPPONENT', 'HOME'].forEach((key) => {
        const cell = document.createElement('b');
        cell.className = heatClass(row[key]);
        cell.textContent = row[key];
        box.append(cell);
      });
    });
  }

  function postOf(row) {
    if (row.duty === 'PREPARE') return '不调模型';
    if (row.model === 'deepseek-v4-flash' && row.duty === 'AUTHOR') return '钉死生成';
    if (row.model === 'gemini-3.7-flash' && row.duty === 'REVIEW') return '钉死审核';
    if (row.model === 'gemini-3.7-flash' && row.duty === 'AUTHOR') return '旧混跑写稿';
    if (String(row.model).startsWith('doubao')) return '旧混跑写稿';
    if (String(row.model).startsWith('gpt')) return '审核对照';
    return '—';
  }

  function mixOf(row) {
    if (row.duty === 'PREPARE') return '准备失败，不重试';
    if (row.duty === 'AUTHOR' && row.model === 'deepseek-v4-flash') return '写稿 86% · 修订 14%';
    if (row.duty === 'AUTHOR') return '写稿 100%';
    if (row.duty === 'REVIEW') return '评审 100%';
    return '—';
  }

  function retryOf(row) {
    if (row.duty === 'PREPARE' || !row.fail) return 0;
    return Math.round(row.fail * 1.3);
  }

  function effectiveOf(row) {
    const map = {
      'deepseek-v4-flash|AUTHOR|SESSION': '¥0.62',
      'deepseek-v4-flash|AUTHOR|POSITION': '¥0.88',
      'deepseek-v4-flash|AUTHOR|OPPONENT': '¥1.33',
      'deepseek-v4-flash|AUTHOR|HOME': '¥0.46',
      'gemini-3.7-flash|AUTHOR|SESSION': '¥3.15',
      'gemini-3.7-flash|AUTHOR|POSITION': '¥4.78',
      'gemini-3.7-flash|AUTHOR|OPPONENT': '¥8.00',
      'gemini-3.7-flash|AUTHOR|HOME': '¥1.90',
      'doubao-seed-2-1-pro|AUTHOR|SESSION': '¥2.31',
      'doubao-seed-2-1-pro|AUTHOR|POSITION': '—',
      'doubao-seed-2-1-pro|AUTHOR|OPPONENT': '¥3.73',
      'doubao-seed-2-1-pro|AUTHOR|HOME': '—',
      'gemini-3.7-flash|REVIEW|SESSION': '¥0.20',
      'gemini-3.7-flash|REVIEW|POSITION': '¥0.21',
      'gemini-3.7-flash|REVIEW|OPPONENT': '¥0.23',
      'gemini-3.7-flash|REVIEW|HOME': '¥0.19',
      'gpt-5.6-luna|REVIEW|SESSION': '¥0.33',
      'gpt-5.6-luna|REVIEW|POSITION': '¥0.39',
      'gpt-5.6-luna|REVIEW|OPPONENT': '¥0.43',
      'gpt-5.6-luna|REVIEW|HOME': '¥0.29',
    };
    return map[`${row.model}|${row.duty}|${row.report}`] || '¥0';
  }

  function renderReportStats(report, duty) {
    const body = document.getElementById('report-stats-rows');
    body.replaceChildren();
    const rows = reportStats.filter((row) => (report === 'ALL' || row.report === report) && (duty === 'ALL' || row.duty === duty));
    for (const row of rows) {
      const tr = document.createElement('tr');
      const fail = row.fail ? `<span class="fail-n">${row.fail}</span>` : '0';
      const retry = retryOf(row);
      tr.innerHTML = `<td>${row.model}</td><td>${postOf(row)}</td><td>${mixOf(row)}</td><td>${row.reportName}</td><td><span class="stage stage-${row.duty.toLowerCase()}">${row.dutyName}</span></td><td>${row.n}</td><td>${row.callOk}</td><td>${row.termOk}</td><td>${fail}</td><td>${retry}</td><td>${row.failWhy}</td><td>${row.first}</td><td>${row.bind}</td><td>${row.harm}</td><td>${row.leak}</td><td class="score">${row.score}</td><td>${effectiveOf(row)}</td>`;
      body.append(tr);
    }
  }

  function pickMetric(rows, ...keys) {
    for (const key of keys) {
      const hit = (rows || []).find((item) => item[0] === key);
      if (hit) return hit[1];
    }
    return '—';
  }

  const failNames = {
    MODEL_TIMEOUT: '超时',
    MODEL_OUTPUT_TRUNCATED: '截断',
    MODEL_STRUCTURED_OUTPUT_INVALID: '结构非法',
    MODEL_UNAVAILABLE: '不可用',
    MODEL_RATE_LIMITED: '限流',
  };

  function failCount(fails) {
    if (!fails || !fails.length) return 0;
    return fails.reduce((sum, item) => sum + item[1], 0);
  }

  function failText(fails) {
    if (!fails || !fails.length) return '—';
    return fails.map((item) => `${failNames[item[0]] || item[0]} ${item[1]}`).join(' · ');
  }

  function retryCell(slot) {
    if (!slot.retry) return '—';
    const r = slot.retry;
    if (typeof r === 'number') return String(r);
    if (!r.n) return '0';
    return r.avg ? `${r.n}（均${r.avg}）` : String(r.n);
  }

  function outcomeValue(slot, key) {
    if (!slot.outcome) return '—';
    if (key === 'retryOk') return slot.outcome.retry1 + slot.outcome.retry2;
    return slot.outcome[key];
  }

  function slotRow(kind, label, slot, id) {
    const cells = [
      label,
      slot.pinned || slot.model,
      pickMetric(slot.call, '样本') || slot.n || '—',
      pickMetric(slot.call, '调用成功') || slot.callOk || '—',
      outcomeValue(slot, 'first'),
      outcomeValue(slot, 'retry1'),
      outcomeValue(slot, 'retry2'),
      pickMetric(slot.call, 'P95'),
      pickMetric(slot.call, 'token'),
      pickMetric(slot.call, '单份') || slot.cost || '—',
      pickMetric(slot.call, '本窗口'),
      pickMetric(slot.quality, '绑定'),
      pickMetric(slot.quality, '伤害'),
      pickMetric(slot.quality, '主泄漏', '主泄漏抓错'),
      pickMetric(slot.quality, '可执行'),
      pickMetric(slot.quality, '综合分', '事实均分'),
      pickMetric(slot.quality, '判过', '首轮过') || slot.first || '—',
      slot.effective || '—',
      failCount(slot.fails),
      retryCell(slot),
      failText(slot.fails),
    ];
    const idAttr = id ? ` id="${id}"` : '';
    return `<tr class="${kind}"${idAttr}><th>${cells[0]}</th>${cells.slice(1).map((value) => `<td>${value}</td>`).join('')}</tr>`;
  }

  function challengerRow(kind, row) {
    const slim = {
      pinned: row.model,
      call: [['样本', row.n], ['调用成功', row.call], ['单份', row.cost]],
      quality: [[kind === 'review' ? '判过' : '首轮过', row.first]],
      effective: row.effective,
      fails: [],
    };
    return slotRow(kind + ' alt', '对照', slim);
  }

  function flowTable(flow) {
    const heads = ['岗位', '模型', '样本', '成功', '首次成功', '重试1次', '重试2次', 'P95', 'token', '单份', '窗口', '绑定', '伤害', '主泄漏', '可执行', '综合', '通过', '有效成本', '失败', '重试请求', '失败原因'];
    return `<div class="table-scroll"><table class="wide-slot">
      <thead><tr>${heads.map((name) => `<th>${name}</th>`).join('')}</tr></thead>
      <tbody>
        <tr class="prep"><th>准备</th><td colspan="${heads.length - 1}">${flow.prepare}</td></tr>
        ${slotRow('author', '生成', flow.generate, `slot-${flow.key}-author`)}
        ${flow.generate.challengers.map((row) => challengerRow('author', row)).join('')}
        ${slotRow('review', '审核', flow.review, `slot-${flow.key}-review`)}
        ${flow.review.challengers.map((row) => challengerRow('review', row)).join('')}
      </tbody>
    </table></div>`;
  }

  function callCell(kind, flow, slot, costHint) {
    return `<a class="call-cell ${kind}" href="#slot-${flow.key}-${kind === 'author' ? 'author' : 'review'}" data-report="${flow.key}">
      <span class="call-who">${slot.pinned}</span>
      <span class="call-cost">有效成本 ${slot.effective}${costHint}</span>
    </a>`;
  }

  function renderTypeFlows(report) {
    const box = document.getElementById('type-flows');
    box.replaceChildren();
    const chips = document.getElementById('flow-type-chips');
    if (chips) {
      for (const button of chips.querySelectorAll('[data-report]')) {
        button.setAttribute('aria-pressed', String(button.dataset.report === report));
      }
    }
    const matrix = document.createElement('table');
    matrix.className = 'call-matrix';
    matrix.innerHTML = `<colgroup><col class="type"><col><col></colgroup><thead><tr><th>报告类型</th><th>生成调用</th><th>审核调用</th></tr></thead><tbody>${callSlots.map((flow) => `<tr class="${report === 'ALL' || report === flow.key ? 'is-on' : 'is-dim'}">
      <th scope="row">${flow.name}</th>
      <td>${callCell('author', flow, flow.generate, ' / 过一份')}</td>
      <td>${callCell('review', flow, flow.review, ' / 次审核')}</td>
    </tr>`).join('')}</tbody>`;
    matrix.addEventListener('click', (event) => {
      const link = event.target.closest('[data-report]');
      if (!link) return;
      event.preventDefault();
      const id = link.getAttribute('href').slice(1);
      document.getElementById('eval-report-type').value = link.dataset.report;
      refreshEval();
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    box.append(matrix);
    const rows = report === 'ALL' ? callSlots : callSlots.filter((row) => row.key === report);
    rows.forEach((flow) => {
      const article = document.createElement('article');
      article.className = 'type-flow';
      article.innerHTML = `
        <div class="type-head">
          <h3>${flow.name}</h3>
          <span class="posts">生成 <em>${flow.generate.pinned}</em> · 审核 <em>${flow.review.pinned}</em></span>
          <span class="detail">${flow.job}</span>
        </div>
        ${flowTable(flow)}`;
      box.append(article);
    });
  }

  function rateText(ok, jobs) {
    if (!jobs) return '0%';
    return `${((ok / jobs) * 100).toFixed(2)}%`;
  }

  function shareText(n, total) {
    if (!total) return '0%';
    return `${((n / total) * 100).toFixed(1)}%`;
  }

  function pieCard(title, slices, centerLabel) {
    const total = slices.reduce((sum, item) => sum + item.n, 0) || 1;
    let acc = 0;
    const stops = slices.map((item) => {
      const start = acc;
      acc += (item.n / total) * 100;
      return `${item.color} ${start}% ${acc}%`;
    }).join(',');
    const main = slices[0];
    const legend = slices.map((item) => `<li><i style="background:${item.color}"></i>${item.label} <b>${item.n.toLocaleString('zh-CN')}</b> ${shareText(item.n, total)}</li>`).join('');
    return `<article class="pie-card">
      <h4>${title}</h4>
      <div class="pie-body">
        <div class="pie-wrap">
          <div class="pie" style="background:conic-gradient(${stops})"></div>
          <div class="pie-center"><strong>${centerLabel || shareText(main.n, total)}</strong><span>${main.hint || main.label}</span></div>
        </div>
        <ul class="pie-legend">${legend}</ul>
      </div>
    </article>`;
  }

  function sumOutcome(items) {
    return items.reduce((acc, item) => ({
      first: acc.first + item.first,
      retry1: acc.retry1 + item.retry1,
      retry2: acc.retry2 + item.retry2,
      fail: acc.fail + item.fail,
    }), { first: 0, retry1: 0, retry2: 0, fail: 0 });
  }

  function packOutcome(raw, name) {
    const ok = raw.first + raw.retry1 + raw.retry2;
    const jobs = ok + raw.fail;
    return Object.assign({ name, ok, jobs }, raw);
  }

  function statsFor(report) {
    if (report === 'ALL') {
      return {
        all: packOutcome(overallCallStats, '全部调用'),
        author: packOutcome(overallCallStats.author, '生成调用'),
        review: packOutcome(overallCallStats.review, '审核调用'),
        rows: [
          packOutcome(overallCallStats, '全部调用'),
          packOutcome(overallCallStats.author, '生成调用'),
          packOutcome(overallCallStats.review, '审核调用'),
        ],
        note: '全部口径与健康概览同一窗口：成功 7412 / 调用 7676。单次任务最多重试 2 次；重试请求另计，不重复计入分母。',
      };
    }
    const flow = callSlots.find((row) => row.key === report);
    const author = packOutcome(flow.generate.outcome, `${flow.name} · 生成`);
    const review = packOutcome(flow.review.outcome, `${flow.name} · 审核`);
    const all = packOutcome(sumOutcome([flow.generate.outcome, flow.review.outcome]), `${flow.name} · 全部`);
    return {
      all,
      author,
      review,
      rows: [all, author, review],
      note: `当前只看${flow.name}钉死岗位。混跑对照在表里，不进这组饼图。`,
    };
  }

  function failRowsFor(report) {
    return report === 'ALL' ? failDist : failDist.filter((row) => row.report === report);
  }

  function groupFail(rows, keyFn, nameFn, colorFn) {
    const map = new Map();
    for (const row of rows) {
      const key = keyFn(row);
      const cur = map.get(key) || { name: nameFn(row), n: 0, color: colorFn(row) };
      cur.n += row.n;
      map.set(key, cur);
    }
    return [...map.values()].filter((item) => item.n > 0).sort((a, b) => b.n - a.n);
  }

  function modelCallVolume(model) {
    const row = modelView.find((item) => item.model === model);
    if (!row) return 0;
    return reportKeys.reduce((sum, key) => sum + row.biz[key].jobs, 0);
  }

  function failShare(n, model) {
    const jobs = modelCallVolume(model);
    if (!jobs) return '—';
    return rateText(n, jobs);
  }

  function slotCallVolume(model, duty, report) {
    const row = modelView.find((item) => item.model === model);
    if (!row) return 0;
    const cell = row.biz[report];
    if (!cell) return 0;
    if (cell.author != null || cell.review != null) {
      return duty === 'AUTHOR' ? cell.author || 0 : cell.review || 0;
    }
    if (String(model).startsWith('gpt')) return duty === 'REVIEW' ? cell.jobs : 0;
    return duty === 'AUTHOR' ? cell.jobs : 0;
  }

  function slotShare(n, model, duty, report) {
    const jobs = slotCallVolume(model, duty, report);
    if (!jobs) return '—';
    return rateText(n, jobs);
  }

  function failMatrix(rows) {
    const map = new Map();
    const order = [];
    for (const row of rows) {
      const key = `${row.model}|${row.duty}|${row.report}`;
      if (!map.has(key)) {
        map.set(key, { model: row.model, reportName: row.reportName, dutyName: row.dutyName, duty: row.duty, counts: {}, n: 0 });
        order.push(key);
      }
      const group = map.get(key);
      group.counts[row.code] = (group.counts[row.code] || 0) + row.n;
      group.n += row.n;
    }
    return order.map((key) => map.get(key));
  }

  function topReason(counts) {
    let code = '';
    let max = 0;
    for (const [key, n] of Object.entries(counts)) {
      if (n > max) {
        code = key;
        max = n;
      }
    }
    if (!code) return '—';
    return `${failReasonMeta[code].name} ${max}`;
  }

  function renderFailDist(report) {
    const rows = failRowsFor(report);
    const total = rows.reduce((sum, row) => sum + row.n, 0);
    if (!total) {
      return `<div class="fail-block"><h3>失败分布</h3><p class="detail">当前筛选下无模型调用失败。</p></div>`;
    }
    const byReport = groupFail(rows, (row) => row.report, (row) => row.reportName, (row) => reportColors[row.report]);
    const byDuty = groupFail(rows, (row) => row.duty, (row) => row.dutyName, (row) => (row.duty === 'AUTHOR' ? '#176f59' : '#1677d2'));
    const byModel = groupFail(rows, (row) => row.model, (row) => modelShort[row.model] || row.model, (row) => modelColors[row.model] || '#637570');
    const byReason = groupFail(rows, (row) => row.code, (row) => failReasonMeta[row.code].name, (row) => failReasonMeta[row.code].color);
    const secondPie = report === 'ALL'
      ? pieCard('失败按报告类型', byReport.map((item) => ({ label: item.name, n: item.n, color: item.color, hint: '占失败' })), shareText(byReport[0].n, total))
      : pieCard('失败按岗位', byDuty.map((item) => ({ label: item.name, n: item.n, color: item.color, hint: '占失败' })), shareText(byDuty[0].n, total));
    const matrix = failMatrix(rows);
    const callRows = rows.slice().sort((a, b) => {
      const code = failCodes.indexOf(a.code) - failCodes.indexOf(b.code);
      if (code) return code;
      return b.n - a.n;
    });
    const scope = report === 'ALL' ? '全部报告' : rows[0].reportName;
    const extra = report === 'ALL'
      ? '准备失败 29 次不调模型，对手报告 16 次最多，属数据范围问题。失败占比相对该模型全部调用；占该调用点相对该模型在该岗位、该报告上的调用。'
      : '含该类型下混跑。钉死岗位上方饼图可能为 0，失败仍可能来自旧混跑模型。失败占比相对该模型全部调用，占该调用点相对该岗位。';
    return `<div class="fail-block">
      <h3>失败分布</h3>
      <p class="detail">${scope}按终态失败计，共 ${total.toLocaleString('zh-CN')} 次。审核不通过回修订不计。${extra}</p>
      <div class="pie-grid fail-pies">
        ${pieCard('失败按模型', byModel.map((item) => ({ label: item.name, n: item.n, color: item.color, hint: '占失败' })), shareText(byModel[0].n, total))}
        ${secondPie}
        ${pieCard('失败原因构成', byReason.map((item) => ({ label: item.name, n: item.n, color: item.color, hint: '占失败' })), shareText(byReason[0].n, total))}
      </div>
      <div class="table-scroll">
        <table class="wide-slot fail-matrix">
          <thead>
            <tr>
              <th>模型</th><th>岗位</th>${report === 'ALL' ? '<th>报告类型</th>' : ''}${failCodes.map((code) => `<th>${failReasonMeta[code].name}</th>`).join('')}<th>合计</th><th>失败占比</th><th>主因</th>
            </tr>
          </thead>
          <tbody>
            ${matrix.map((row) => `<tr class="${row.duty === 'AUTHOR' ? 'author' : 'review'}">
              <th>${row.model}</th>
              <td>${row.dutyName}</td>
              ${report === 'ALL' ? `<td>${row.reportName}</td>` : ''}
              ${failCodes.map((code) => `<td>${row.counts[code] || 0}</td>`).join('')}
              <td><span class="fail-n">${row.n}</span></td>
              <td>${failShare(row.n, row.model)}<span class="detail">占该模型 ${modelCallVolume(row.model).toLocaleString('zh-CN')} 次</span></td>
              <td>${topReason(row.counts)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div class="table-scroll">
        <table class="wide-slot fail-reason-table">
          <thead>
            <tr>
              <th>失败原因</th><th>模型</th><th>调用点</th>${report === 'ALL' ? '<th>报告类型</th>' : ''}<th>次数</th><th>占失败</th><th>占该模型调用</th><th>占该调用点</th><th>说明</th>
            </tr>
          </thead>
          <tbody>
            ${callRows.map((row) => {
              const slotJobs = slotCallVolume(row.model, row.duty, row.report);
              return `<tr class="${row.duty === 'AUTHOR' ? 'author' : 'review'}">
              <td>${failReasonMeta[row.code].name}<span class="detail">${row.code}</span></td>
              <th>${row.model}</th>
              <td>${row.dutyName}</td>
              ${report === 'ALL' ? `<td>${row.reportName}</td>` : ''}
              <td><span class="fail-n">${row.n}</span></td>
              <td>${shareText(row.n, total)}</td>
              <td>${failShare(row.n, row.model)}<span class="detail">/${modelCallVolume(row.model).toLocaleString('zh-CN')}</span></td>
              <td>${slotShare(row.n, row.model, row.duty, row.report)}<span class="detail">/${slotJobs.toLocaleString('zh-CN')}</span></td>
              <td>${failReasonMeta[row.code].detail}</td>
            </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
  }

  function renderCallCharts(report) {
    const box = document.getElementById('call-charts');
    if (!box) return;
    const stats = statsFor(report);
    const all = stats.all;
    box.innerHTML = `
      <h3>调用结果与重试构成</h3>
      <p class="detail">${stats.note} 数字为示意。调用成功不是报告通过。</p>
      <div class="pie-grid">
        ${pieCard('整体调用结果', [
          { label: '成功', n: all.ok, color: '#176f59', hint: '成功率' },
          { label: '失败', n: all.fail, color: '#a0392d' },
        ], rateText(all.ok, all.jobs))}
        ${pieCard('成功构成', [
          { label: '首次成功', n: all.first, color: '#176f59', hint: '首次占比' },
          { label: '重试 1 次成功', n: all.retry1, color: '#1677d2' },
          { label: '重试 2 次成功', n: all.retry2, color: '#7147d9' },
        ], shareText(all.first, all.ok))}
        ${pieCard('生成调用', [
          { label: '首次成功', n: stats.author.first, color: '#176f59', hint: '成功率' },
          { label: '经重试成功', n: stats.author.retry1 + stats.author.retry2, color: '#1677d2' },
          { label: '失败', n: stats.author.fail, color: '#a0392d' },
        ], rateText(stats.author.ok, stats.author.jobs))}
        ${pieCard('审核调用', [
          { label: '首次成功', n: stats.review.first, color: '#176f59', hint: '成功率' },
          { label: '经重试成功', n: stats.review.retry1 + stats.review.retry2, color: '#1677d2' },
          { label: '失败', n: stats.review.fail, color: '#a0392d' },
        ], rateText(stats.review.ok, stats.review.jobs))}
      </div>
      <div class="table-scroll">
        <table class="wide-slot outcome-table">
          <thead>
            <tr>
              <th>调用</th><th>任务</th><th>成功</th><th>失败</th><th>成功率</th><th>失败率</th><th>首次成功</th><th>首次占比</th><th>重试 1 次成功</th><th>重试 2 次成功</th><th>经重试成功</th>
            </tr>
          </thead>
          <tbody>
            ${stats.rows.map((row) => {
              const retryOkRow = row.retry1 + row.retry2;
              return `<tr>
                <th>${row.name}</th>
                <td>${row.jobs.toLocaleString('zh-CN')}</td>
                <td>${row.ok.toLocaleString('zh-CN')}</td>
                <td><span class="fail-n">${row.fail.toLocaleString('zh-CN')}</span></td>
                <td>${rateText(row.ok, row.jobs)}</td>
                <td>${rateText(row.fail, row.jobs)}</td>
                <td>${row.first.toLocaleString('zh-CN')}</td>
                <td>${shareText(row.first, row.ok)}</td>
                <td>${row.retry1.toLocaleString('zh-CN')}</td>
                <td>${row.retry2.toLocaleString('zh-CN')}</td>
                <td>${retryOkRow.toLocaleString('zh-CN')}（${shareText(retryOkRow, row.ok)}）</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
      ${renderFailDist(report)}`;
  }

  function sliceOf(row, report) {
    if (report === 'ALL') {
      return reportKeys.reduce((acc, key) => {
        const cell = row.biz[key];
        acc.jobs += cell.jobs;
        acc.fail += cell.fail;
        return acc;
      }, { jobs: 0, fail: 0, p50: row.p50, p95: row.p95 });
    }
    const cell = row.biz[report];
    return { jobs: cell.jobs, fail: cell.fail, p50: cell.p50, p95: cell.p95 };
  }

  function modelFailWhy(model, report) {
    const rows = failDist.filter((row) => row.model === model && (report === 'ALL' || row.report === report));
    const counts = {};
    for (const row of rows) counts[row.code] = (counts[row.code] || 0) + row.n;
    let code = '';
    let max = 0;
    for (const [key, n] of Object.entries(counts)) {
      if (n > max) {
        code = key;
        max = n;
      }
    }
    return code ? `${failReasonMeta[code].name} ${max}` : '—';
  }

  function mixTrack(items, total) {
    if (!total) return '<div class="mix-bar model-mix"></div>';
    return `<div class="mix-bar model-mix">${items.filter((item) => item.n > 0).map((item) => `<span style="width:${(item.n / total) * 100}%;background:${item.color}" title="${item.name} ${item.n}"></span>`).join('')}</div>`;
  }

  function rateClass(ok, jobs) {
    if (!jobs) return '';
    const pct = (ok / jobs) * 100;
    if (pct >= 97) return 'rate-ok';
    if (pct >= 92) return 'rate-mid';
    return 'rate-bad';
  }

  function speedClass(text) {
    const n = Number(String(text).replace('秒', ''));
    return n >= 20 ? 'speed-slow' : '';
  }

  function bizItems(row, field) {
    return reportKeys.map((key) => {
      const cell = row.biz[key];
      const n = field === 'ok' ? cell.jobs - cell.fail : cell.jobs;
      return { key, name: reportShort[key], n, color: reportColors[key] };
    });
  }

  function successAnchor(row, ok) {
    const ranked = bizItems(row, 'ok').slice().sort((a, b) => b.n - a.n);
    const top = ranked[0];
    if (!top || !ok) return '—';
    return `${top.name} ${shareText(top.n, ok)}`;
  }

  function renderModelView(report) {
    const box = document.getElementById('model-view');
    if (!box) return;
    const rows = modelView.map((row) => {
      const slice = sliceOf(row, report);
      return { row, slice, ok: slice.jobs - slice.fail };
    }).filter((item) => item.slice.jobs > 0);
    const jobsAll = rows.reduce((sum, item) => sum + item.slice.jobs, 0);
    const okAll = rows.reduce((sum, item) => sum + item.ok, 0);
    const failAll = rows.reduce((sum, item) => sum + item.slice.fail, 0);
    const failSlices = rows.filter((item) => item.slice.fail).sort((a, b) => b.slice.fail - a.slice.fail);
    const scope = report === 'ALL' ? '全部报告' : callSlots.find((item) => item.key === report).name;
    const bizHead = report === 'ALL'
      ? reportKeys.map((key) => `<th>${reportShort[key]}成功率</th>`).join('') + '<th>成功落点</th>'
      : '<th>占该模型调用</th><th>占该报告调用</th><th>占该报告成功</th>';
    const body = rows.map(({ row, slice, ok }) => {
      const modelJobs = sliceOf(row, 'ALL').jobs;
      const bizCells = report === 'ALL'
        ? reportKeys.map((key) => {
            const cell = row.biz[key];
            const cellOk = cell.jobs - cell.fail;
            return `<td class="${rateClass(cellOk, cell.jobs)}">${rateText(cellOk, cell.jobs)}<span class="detail">占成功 ${shareText(cellOk, ok)}</span></td>`;
          }).join('') + `<td>${mixTrack(bizItems(row, 'ok'), ok)}<span class="detail">${successAnchor(row, ok)}</span></td>`
        : `<td>${shareText(slice.jobs, modelJobs)}</td><td>${shareText(slice.jobs, jobsAll)}</td><td>${shareText(ok, okAll)}</td>`;
      return `<tr>
        <th>${row.model}<span class="detail">${row.work}</span></th>
        <td>${slice.jobs.toLocaleString('zh-CN')}</td>
        <td>${ok.toLocaleString('zh-CN')}</td>
        <td><span class="fail-n">${slice.fail.toLocaleString('zh-CN')}</span></td>
        <td class="${rateClass(ok, slice.jobs)}">${rateText(ok, slice.jobs)}</td>
        <td>${rateText(slice.fail, slice.jobs)}</td>
        ${bizCells}
        <td>${slice.p50}</td>
        <td class="${speedClass(slice.p95)}">${slice.p95}</td>
        <td>${modelFailWhy(row.model, report)}</td>
      </tr>`;
    }).join('');
    const callSlices = rows.slice().sort((a, b) => b.slice.jobs - a.slice.jobs);
    const okSlices = rows.slice().sort((a, b) => b.ok - a.ok);
    const failPie = failAll
      ? pieCard('失败按模型', failSlices.map(({ row, slice }) => ({ label: modelShort[row.model] || row.model, n: slice.fail, color: modelColors[row.model], hint: '占失败' })), shareText(failSlices[0].slice.fail, failAll))
      : pieCard('失败按模型', [{ label: '无失败', n: 1, color: '#dce5e1', hint: '无失败' }], '0%');
    box.innerHTML = `<div class="model-panel">
      <h3>按模型看</h3>
      <p class="detail">${scope}按模型汇总调用成败、各报告成功率和时延。成功率是调用成功，不是报告通过。成功落点看成功次数落在哪类报告。数字为示意。</p>
      <div class="pie-grid fail-pies">
        ${pieCard('调用按模型', callSlices.map(({ row, slice }) => ({ label: modelShort[row.model] || row.model, n: slice.jobs, color: modelColors[row.model], hint: '占调用' })), shareText(callSlices[0].slice.jobs, jobsAll))}
        ${pieCard('成功按模型', okSlices.map(({ row, ok }) => ({ label: modelShort[row.model] || row.model, n: ok, color: modelColors[row.model], hint: '占成功' })), shareText(okSlices[0].ok, okAll))}
        ${failPie}
      </div>
      ${report === 'ALL' ? `<div class="mix-legend">${reportKeys.map((key) => `<span><i style="background:${reportColors[key]}"></i>${reportShort[key]}</span>`).join('')}</div>` : ''}
      <div class="table-scroll">
        <table class="wide-slot model-table">
          <thead>
            <tr>
              <th>模型</th><th>调用</th><th>成功</th><th>失败</th><th>成功率</th><th>失败率</th>${bizHead}<th>P50</th><th>P95</th><th>主失败原因</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </div>`;
  }

  function renderSpend() {
    const box = document.getElementById('spend-share');
    if (!box) return;
    const total = spendShare.reduce((sum, row) => sum + row.yen, 0);
    const bars = spendShare.map((row) => `<span style="width:${row.pct}%;background:${row.color}" title="${row.model} ¥${row.yen}（${row.pct}%）">${row.pct >= 8 ? row.pct + '%' : ''}</span>`).join('');
    const legend = spendShare.map((row) => `<span><i style="background:${row.color}"></i>${row.model} ${row.pct}%</span>`).join('');
    box.innerHTML = `<div class="spend-panel">
      <h3>本窗口消费占比</h3>
      <p class="detail">按示意单价估算，合计 ¥${total}。Gemini 评审调用量大，占了窗口六成。调用失败后的重试也计入成本；审核不通过回修订不算调用失败重试。</p>
      <div class="spend-track">${bars}</div>
      <div class="mix-legend">${legend}</div>
      <div class="table-scroll">
        <table class="wide-slot spend-table">
          <thead><tr><th>模型</th><th>工作</th><th>调用</th><th>窗口成本</th><th>占比</th><th>单次均费</th></tr></thead>
          <tbody>${spendShare.map((row) => `<tr><td>${row.model}</td><td>${row.work}</td><td>${row.calls}</td><td>¥${row.yen}</td><td>${row.pct}%</td><td>${row.unit}</td></tr>`).join('')}</tbody>
        </table>
      </div>
    </div>`;
  }

  function refreshEval() {
    const report = document.getElementById('eval-report-type').value;
    renderCallCharts(report);
    renderModelView(report);
    renderSpend();
    renderReportStats(report, evalDuty);
    renderTypeFlows(report);
  }

  function qualityCell(item) {
    const td = document.createElement('td');
    const wrap = document.createElement('div');
    wrap.className = 'score-pills';
    const pills = [];
    const q = item.quality;
    if (q) {
      if (q.bind) pills.push(['绑定 ' + q.bind, q.bindOk === false ? 'bad' : q.bindOk ? 'ok' : '']);
      if (q.harm) pills.push(['伤害 ' + q.harm, q.harm === '有' ? 'bad' : q.harm === '无' ? 'ok' : '']);
      if (q.leak) pills.push(['主泄漏 ' + q.leak, q.leak === '抓错' ? 'bad' : q.leak === '抓对' ? 'ok' : '']);
      if (q.action) pills.push(['建议 ' + q.action, q.action === '可执行' ? 'ok' : q.action === '套话' ? 'bad' : '']);
    }
    if (item.score) {
      pills.push(['事实 ' + item.score.fact, item.score.fact <= 2 ? 'bad' : item.score.fact >= 4 ? 'ok' : '']);
      pills.push(['综合 ' + item.score.total, Number(item.score.total) >= 4 ? 'ok' : 'bad']);
    }
    if (!pills.length) {
      td.textContent = '不打分';
      return td;
    }
    wrap.innerHTML = pills.map(([text, cls]) => `<span class="${cls}">${text}</span>`).join('');
    td.append(wrap);
    return td;
  }

  function cell(tr, text, detail) {
    const td = document.createElement('td');
    td.textContent = text ?? '—';
    if (detail) {
      const sub = document.createElement('span');
      sub.className = 'detail';
      sub.textContent = detail;
      td.append(sub);
    }
    tr.append(td);
    return td;
  }

  function showDetail(id) {
    const data = details[id];
    const dialog = document.getElementById('detail-dialog');
    document.getElementById('detail-title').textContent = data.title;
    document.getElementById('detail-state').textContent = data.state;
    const meta = document.getElementById('detail-metadata');
    meta.replaceChildren();
    for (const [label, value] of data.meta) {
      const group = document.createElement('div');
      const dt = document.createElement('dt');
      dt.textContent = label;
      const dd = document.createElement('dd');
      dd.textContent = value;
      group.append(dt, dd);
      meta.append(group);
    }
    const content = document.getElementById('detail-content');
    content.replaceChildren();
    if (data.path && data.path.length) {
      const path = document.createElement('ol');
      path.className = 'path-track';
      data.path.forEach((step) => {
        const li = document.createElement('li');
        li.className = step.state;
        li.innerHTML = `<span class="who">${step.who}</span><span class="label">${step.label}</span>`;
        path.append(li);
      });
      content.append(path);
    }
    const section = document.createElement('section');
    section.className = 'report-section';
    const title = document.createElement('h3');
    title.textContent = '本次执行 · 谁写、谁评、为什么过或不过';
    section.append(title);
    if (data.message) {
      const p = document.createElement('p');
      p.textContent = data.message;
      section.append(p);
    }
    if (data.attempts.length) {
      const scroll = document.createElement('div');
      scroll.className = 'table-scroll';
      const table = document.createElement('table');
      table.id = 'model-attempts';
      const head = table.createTHead().insertRow();
      for (const text of ['序号', '职责', '轮次', '模型', '判定', '质量指标', '成本']) {
        const th = document.createElement('th');
        th.textContent = text;
        head.append(th);
      }
      const body = table.createTBody();
      data.attempts.forEach((item) => {
        const tr = body.insertRow();
        if (item.kind === 'fail') tr.className = 'attempt-fail';
        if (item.kind === 'pass') tr.className = 'attempt-pass';
        cell(tr, item.seq);
        cell(tr, item.duty);
        cell(tr, item.round);
        cell(tr, item.model, item.duration);
        cell(tr, item.result, item.note);
        tr.append(qualityCell(item));
        cell(tr, item.cost, item.tokens);
      });
      scroll.append(table);
      section.append(scroll);
    }
    content.append(section);
    dialog.showModal();
  }

  function drawTrend() {
    const canvas = document.getElementById('health-trend');
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const dates = ['09-15', '09-16', '09-17'];
    const series = [
      { name: 'deepseek-v4-flash', color: '#17795f', points: [97.13, 99.54, 98.79] },
      { name: 'doubao', color: '#1677d2', points: [98.79, 95.0, 100] },
      { name: 'gemini-3.7-flash', color: '#e86f16', points: [95.64, 92.55, 94.1] },
    ];
    ctx.strokeStyle = '#dce5e1';
    ctx.beginPath();
    ctx.moveTo(48, 18);
    ctx.lineTo(48, 220);
    ctx.lineTo(780, 220);
    ctx.stroke();
    series.forEach((line, i) => {
      ctx.strokeStyle = line.color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      line.points.forEach((value, j) => {
        const x = 48 + j * 366;
        const y = 220 - (value - 80) * 10.1;
        j ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.stroke();
      ctx.fillStyle = line.color;
      ctx.fillText(line.name, 58 + i * 180, 248);
    });
    ctx.fillStyle = '#6a7a74';
    dates.forEach((date, j) => ctx.fillText(date, 36 + j * 366, 236));
  }

  document.getElementById('jump-rules').addEventListener('click', () => {
    showTab('eval');
    const box = document.getElementById('score-rules');
    box.open = true;
    box.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  document.getElementById('health-tab').addEventListener('click', () => showTab('health'));
  document.getElementById('eval-tab').addEventListener('click', () => showTab('eval'));
  document.getElementById('query-tab').addEventListener('click', () => showTab('query'));
  document.getElementById('failure-chips').addEventListener('click', (event) => {
    const chip = event.target.closest('[data-stage]');
    if (!chip) return;
    for (const button of event.currentTarget.querySelectorAll('.chip')) {
      button.setAttribute('aria-pressed', String(button === chip));
    }
    renderFailures(chip.dataset.stage);
  });
  document.getElementById('eval-report-type').addEventListener('change', refreshEval);
  document.getElementById('flow-type-chips').addEventListener('click', (event) => {
    const chip = event.target.closest('[data-report]');
    if (!chip) return;
    document.getElementById('eval-report-type').value = chip.dataset.report;
    refreshEval();
  });
  document.getElementById('report-duty-chips').addEventListener('click', (event) => {
    const chip = event.target.closest('[data-duty]');
    if (!chip) return;
    evalDuty = chip.dataset.duty;
    for (const button of event.currentTarget.querySelectorAll('.chip')) {
      button.setAttribute('aria-pressed', String(button === chip));
    }
    refreshEval();
  });
  document.getElementById('detail-close').addEventListener('click', () => document.getElementById('detail-dialog').close());
  document.getElementById('query-tab-panel').addEventListener('click', (event) => {
    const detail = event.target.closest('[data-detail]');
    if (detail) showDetail(detail.dataset.detail);
    const rerun = event.target.closest('[data-rerun]');
    if (rerun) {
      document.getElementById('confirm-target').textContent = `任务 #${rerun.dataset.rerun}`;
      document.getElementById('confirm-dialog').showModal();
    }
  });
  document.getElementById('rerun-custom').closest('.radio-list').addEventListener('change', () => {
    document.getElementById('rerun-model').disabled = !document.getElementById('rerun-custom').checked;
  });

  renderFailures('ALL');
  refreshEval();
  drawTrend();
})();
