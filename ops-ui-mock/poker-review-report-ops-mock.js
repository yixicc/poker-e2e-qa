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

  const reportFlows = [
    {
      key: 'SESSION',
      name: '场次报告',
      job: '这场怎么打、主泄漏在哪',
      author: 'deepseek-v4-flash',
      reviewer: 'gemini-3.7-flash',
      mix: '实际写稿 deepseek 81% · gemini 14% · 豆包 5%',
      term: '99.5%',
      first: '21%',
      stages: [
        { kind: 'prepare', step: '1', whoKind: '程序', title: '数据准备', who: '程序，不调模型', okLine: '进入 418 · 成功 412 · 失败 6（1.4%）', metrics: [['进入', '418'], ['成功', '98.6%'], ['失败', '6'], ['范围无效', '4'], ['事实未就绪', '2']], fails: [['INPUT_SCOPE_INVALID', 4, '没有手牌匹配所选范围'], ['DATA_PLATFORM_NOT_READY', 2, '事实未就绪']], note: '失败直接结束，不进生成。' },
        { kind: 'author', step: '2', whoKind: '生成', title: '报告生成', who: 'deepseek-v4-flash', okLine: '样本 412 · 调用成功 98.5% · 终态 99.5%', metrics: [['进入', '412'], ['调用成功', '98.5%'], ['写出', '410'], ['绑定', '64%'], ['伤害', '2.4%'], ['主泄漏', '46%'], ['可执行', '58%'], ['综合分', '3.2'], ['首轮过', '21%'], ['P95', '10.9秒'], ['成本', '¥0.13']], fails: [['MODEL_TIMEOUT', 2, '写稿超时，报告未写出']], note: '调用成功 ≠ 审核通过。' },
        { kind: 'check', step: '3', whoKind: '程序', title: '硬指标', who: '程序，交给审核', okLine: '不单独终态失败。', metrics: [['绑定达标', '64%'], ['绑定<80%', '148'], ['伤害错误', '10'], ['可执行不足', '173'], ['可执行率', '58%']], fails: [['绑定不够', 148, '亮点/改进没挂本场真实手'], ['伤害性错误', 10, '盈亏/位置/摊牌写反或引用不存在的手']], note: '出现伤害即一票否决。' },
        { kind: 'review', step: '4', whoKind: '审核', title: '报告审核', who: 'gemini-3.7-flash', okLine: '首轮审核 412 · 调用成功 95.4% · 判过 21%', metrics: [['进入', '412'], ['调用成功', '95.4%'], ['判过', '21%'], ['业务不过', '79%'], ['调用失败', '19'], ['事实均分', '3.6'], ['P95', '25秒'], ['成本', '¥0.19']], fails: [['MODEL_TIMEOUT', 13, '审核调用超时，没打出分'], ['MODEL_OUTPUT_TRUNCATED', 4, '审核输出被截断'], ['MODEL_UNAVAILABLE', 2, '审核不可用'], ['主泄漏抓错', 110, '业务不通过：rank1 不是最大的钱'], ['事实<4', 42, '业务不通过：事实分不够']], note: '调用失败和业务不通过要分开记。' },
        { kind: 'revise', step: '5', whoKind: '生成', title: '修订', who: '仍由 deepseek 改', okLine: '326 份回修订 · 变好 43% · 终态出报告 410', metrics: [['回改', '326'], ['变好', '43%'], ['终态出报告', '410'], ['兜底', '已关闭']], fails: [['MODEL_TIMEOUT', 1, '修订超时'], ['仍未过线', 1, '多轮后仍未过硬指标，最终失败']], note: '不通过才走这里，不换审核模型来改。' },
      ],
    },
    {
      key: 'POSITION',
      name: '位置报告',
      job: '这个位置长期泄漏',
      author: 'deepseek-v4-flash',
      reviewer: 'gemini-3.7-flash',
      mix: '实际写稿 deepseek 88% · gemini 12%',
      term: '99.3%',
      first: '16%',
      stages: [
        { kind: 'prepare', step: '1', whoKind: '程序', title: '数据准备', who: '程序，不调模型', okLine: '进入 152 · 成功 148 · 失败 4（2.6%）', metrics: [['进入', '152'], ['成功', '97.4%'], ['失败', '4'], ['范围无效', '3'], ['事实未就绪', '1']], fails: [['INPUT_SCOPE_INVALID', 3, '该位置没有匹配手牌'], ['DATA_PLATFORM_NOT_READY', 1, '事实未就绪']], note: '失败直接结束，不进生成。' },
        { kind: 'author', step: '2', whoKind: '生成', title: '报告生成', who: 'deepseek-v4-flash', okLine: '样本 148 · 调用成功 99.0% · 终态 99.3%', metrics: [['进入', '148'], ['调用成功', '99.0%'], ['写出', '147'], ['绑定', '58%'], ['伤害', '3.0%'], ['主泄漏', '41%'], ['可执行', '51%'], ['综合分', '3.0'], ['首轮过', '16%'], ['P95', '11.4秒'], ['成本', '¥0.14']], fails: [['MODEL_OUTPUT_TRUNCATED', 1, '写稿被截断']], note: '跨手证据更难挂。' },
        { kind: 'check', step: '3', whoKind: '程序', title: '硬指标', who: '程序，交给审核', okLine: '不单独终态失败。', metrics: [['绑定达标', '58%'], ['绑定<80%', '62'], ['伤害错误', '4'], ['可执行不足', '72'], ['可执行率', '51%']], fails: [['绑定不够', 62, '位置建议常不挂具体手'], ['伤害性错误', 4, '位置写反']], note: '套话比例高于场次。' },
        { kind: 'review', step: '4', whoKind: '审核', title: '报告审核', who: 'gemini-3.7-flash', okLine: '首轮审核 148 · 调用成功 95.0% · 判过 16%', metrics: [['进入', '148'], ['调用成功', '95.0%'], ['判过', '16%'], ['业务不过', '84%'], ['调用失败', '7'], ['事实均分', '3.4'], ['P95', '28秒'], ['成本', '¥0.20']], fails: [['MODEL_TIMEOUT', 5, '审核超时'], ['MODEL_OUTPUT_TRUNCATED', 2, '审核截断'], ['主泄漏抓错', 48, '被单手戏剧带偏'], ['事实<4', 18, '跨场统计写错']], note: '长期泄漏有时被单手带偏。' },
        { kind: 'revise', step: '5', whoKind: '生成', title: '修订', who: '仍由 deepseek 改', okLine: '124 份回修订 · 变好 39% · 终态出报告 147', metrics: [['回改', '124'], ['变好', '39%'], ['终态出报告', '147'], ['兜底', '已关闭']], fails: [['仍未过线', 1, '修订后仍未过线']], note: '不通过才走这里。' },
      ],
    },
    {
      key: 'OPPONENT',
      name: '对手报告',
      job: '对面风格和应对',
      author: 'deepseek-v4-flash',
      reviewer: 'gemini-3.7-flash',
      mix: '实际写稿 deepseek 79% · gemini 16% · 豆包 5%',
      term: '98.0%',
      first: '12%',
      stages: [
        { kind: 'prepare', step: '1', whoKind: '程序', title: '数据准备', who: '程序，不调模型', okLine: '进入 118 · 成功 102 · 失败 16（13.6%）', metrics: [['进入', '118'], ['成功', '86.4%'], ['失败', '16'], ['范围无效', '11'], ['事实未就绪', '5']], fails: [['INPUT_SCOPE_INVALID', 11, '对手范围内没有匹配手'], ['DATA_PLATFORM_NOT_READY', 5, '对手统计未就绪']], note: '四种里准备失败最多，不是模型问题。' },
        { kind: 'author', step: '2', whoKind: '生成', title: '报告生成', who: 'deepseek-v4-flash', okLine: '样本 102 · 调用成功 97.2% · 终态 98.0%', metrics: [['进入', '102'], ['调用成功', '97.2%'], ['写出', '100'], ['绑定', '52%'], ['伤害', '4.8%'], ['主泄漏', '31%'], ['可执行', '41%'], ['综合分', '2.8'], ['首轮过', '12%'], ['P95', '12.6秒'], ['成本', '¥0.16']], fails: [['MODEL_TIMEOUT', 1, '写稿超时'], ['MODEL_STRUCTURED_OUTPUT_INVALID', 1, '结构化输出非法']], note: '风格判断最容易写反。' },
        { kind: 'check', step: '3', whoKind: '程序', title: '硬指标', who: '程序，交给审核', okLine: '不单独终态失败。', metrics: [['绑定达标', '52%'], ['绑定<80%', '49'], ['伤害错误', '5'], ['可执行不足', '60'], ['可执行率', '41%']], fails: [['绑定不够', 49, '引用对手手常对不上'], ['伤害性错误', 5, '风格/位置/盈亏写反']], note: '套话「打得紧一点」最多。' },
        { kind: 'review', step: '4', whoKind: '审核', title: '报告审核', who: 'gemini-3.7-flash', okLine: '首轮审核 102 · 调用成功 94.1% · 判过 12%', metrics: [['进入', '102'], ['调用成功', '94.1%'], ['判过', '12%'], ['业务不过', '88%'], ['调用失败', '6'], ['事实均分', '3.1'], ['P95', '31秒'], ['成本', '¥0.22']], fails: [['MODEL_TIMEOUT', 4, '审核超时'], ['MODEL_UNAVAILABLE', 2, '审核不可用'], ['主泄漏抓错', 41, '抓最戏剧的一手'], ['事实<4', 22, '对手统计写错']], note: '判过最低，主要是稿差，不是审核更严。' },
        { kind: 'revise', step: '5', whoKind: '生成', title: '修订', who: '仍由 deepseek 改', okLine: '90 份回修订 · 变好 33% · 终态出报告 100', metrics: [['回改', '90'], ['变好', '33%'], ['终态出报告', '100'], ['兜底', '已关闭']], fails: [['MODEL_TIMEOUT', 1, '修订超时'], ['仍未过线', 1, '多轮后仍未过线']], note: '修订对对手报告最不值钱。' },
      ],
    },
    {
      key: 'HOME',
      name: '首页总结',
      job: '多场汇总给用户看',
      author: 'deepseek-v4-flash',
      reviewer: 'gemini-3.7-flash',
      mix: '实际写稿 deepseek 90% · gemini 10%',
      term: '100%',
      first: '23%',
      stages: [
        { kind: 'prepare', step: '1', whoKind: '程序', title: '数据准备', who: '程序，不调模型', okLine: '进入 48 · 成功 45 · 失败 3（6.3%）', metrics: [['进入', '48'], ['成功', '93.8%'], ['失败', '3'], ['事实未就绪', '3']], fails: [['DATA_PLATFORM_NOT_READY', 3, '多场汇总事实未就绪']], note: '失败直接结束，不进生成。' },
        { kind: 'author', step: '2', whoKind: '生成', title: '报告生成', who: 'deepseek-v4-flash', okLine: '样本 45 · 调用成功 99.1% · 终态 100%', metrics: [['进入', '45'], ['调用成功', '99.1%'], ['写出', '45'], ['绑定', '70%'], ['伤害', '1.8%'], ['主泄漏', '48%'], ['可执行', '61%'], ['综合分', '3.3'], ['首轮过', '24%'], ['P95', '9.8秒'], ['成本', '¥0.11']], fails: [], note: '较少点名单手，伤害低。n 小，数字会跳。' },
        { kind: 'check', step: '3', whoKind: '程序', title: '硬指标', who: '程序，交给审核', okLine: '不单独终态失败。', metrics: [['绑定达标', '70%'], ['绑定<80%', '14'], ['伤害错误', '1'], ['可执行不足', '17'], ['可执行率', '61%']], fails: [['绑定不够', 14, '总结里仍有未挂手的套话'], ['伤害性错误', 1, '汇总盈亏写反']], note: '硬指标相对最好过。' },
        { kind: 'review', step: '4', whoKind: '审核', title: '报告审核', who: 'gemini-3.7-flash', okLine: '首轮审核 45 · 调用成功 96.2% · 判过 24%', metrics: [['进入', '45'], ['调用成功', '96.2%'], ['判过', '24%'], ['业务不过', '76%'], ['调用失败', '2'], ['事实均分', '3.8'], ['P95', '22秒'], ['成本', '¥0.18']], fails: [['MODEL_TIMEOUT', 2, '审核超时'], ['主泄漏抓错', 12, '主线抓偏'], ['事实<4', 6, '汇总数字对不上']], note: '四种里最好看，但样本少。' },
        { kind: 'revise', step: '5', whoKind: '生成', title: '修订', who: '仍由 deepseek 改', okLine: '34 份回修订 · 变好 48% · 终态出报告 45', metrics: [['回改', '34'], ['变好', '48%'], ['终态出报告', '45'], ['兜底', '已关闭']], fails: [], note: '本窗口无修订失败。' },
      ],
    },
  ];

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

  function recoClass(kind) {
    return ({ keep: 'keep', wait: 'wait', stop: 'stop', thin: 'thin' })[kind] || 'thin';
  }

  function renderEval(stage) {
    const body = document.getElementById('eval-rows');
    body.replaceChildren();
    const rows = evalRows.filter((row) => stage === 'ALL' || row.stage === stage);
    for (const row of rows) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${row.model}</td><td>${row.stageName}<span class="detail">n=${row.n}</span></td><td><span class="reco ${recoClass(row.reco)}">${row.recoText}</span></td><td>${row.bind}</td><td>${row.harm}</td><td>${row.leak}</td><td class="score">${row.score}</td><td>${row.pass}</td><td>${row.effective}</td>`;
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

  function renderReportStats(report, duty) {
    const body = document.getElementById('report-stats-rows');
    body.replaceChildren();
    const rows = reportStats.filter((row) => (report === 'ALL' || row.report === report) && (duty === 'ALL' || row.duty === duty));
    for (const row of rows) {
      const tr = document.createElement('tr');
      const fail = row.fail ? `<span class="fail-n">${row.fail}</span>` : '0';
      tr.innerHTML = `<td>${row.model}</td><td>${row.reportName}</td><td><span class="stage stage-${row.duty.toLowerCase()}">${row.dutyName}</span></td><td>${row.n}</td><td>${row.callOk}</td><td>${row.termOk}</td><td>${fail}<span class="detail">${row.failWhy}</span></td><td>${row.first}</td><td>${row.bind}</td><td>${row.harm}</td><td>${row.leak}</td><td class="score">${row.score}</td>`;
      body.append(tr);
    }
  }

  function stageOf(flow, kind) {
    return flow.stages.find((stage) => stage.kind === kind);
  }

  function metricGrid(metrics) {
    return `<div class="stage-metrics">${metrics.map((item) => `<span><em>${item[0]}</em>${item[1]}</span>`).join('')}</div>`;
  }

  function failBlock(fails) {
    if (!fails.length) return '<p class="detail">本环无失败样本</p>';
    return `<ol class="fail-list">${fails.map((item) => `<li><strong>${item[1]}</strong> ${item[0]}<span class="detail">${item[2]}</span></li>`).join('')}</ol>`;
  }

  function laneHtml(title, stage, extra) {
    return `<section class="lane ${stage.kind}"><h4>${title}</h4><p class="who-line">谁：<em>${stage.who}</em></p>${metricGrid(stage.metrics)}<span class="flow-vol">${stage.okLine}</span>${failBlock(stage.fails)}<p class="detail">${stage.note}</p>${extra || ''}</section>`;
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
    const rows = report === 'ALL' ? reportFlows : reportFlows.filter((row) => row.key === report);
    rows.forEach((flow) => {
      const prepare = stageOf(flow, 'prepare');
      const author = stageOf(flow, 'author');
      const check = stageOf(flow, 'check');
      const review = stageOf(flow, 'review');
      const revise = stageOf(flow, 'revise');
      const article = document.createElement('article');
      article.className = 'type-flow';
      article.innerHTML = `
        <div class="type-head">
          <h3>${flow.name}</h3>
          <span class="posts">生成 <em>${flow.author}</em> · 审核 <em>${flow.reviewer}</em></span>
          <span class="detail">${flow.job} · ${flow.mix}</span>
          <span class="type-kpis">终态成功 ${flow.term} · 首轮通过 ${flow.first}</span>
        </div>
        <div class="prep-bar">
          <div><strong>进入前 · ${prepare.title}</strong><span class="who-line">谁：<em>${prepare.who}</em></span></div>
          ${metricGrid(prepare.metrics)}
          ${failBlock(prepare.fails)}
          <p class="detail">${prepare.note}</p>
        </div>
        <div class="skeleton-pair">
          ${laneHtml('报告生成', author, `<div class="lane-sub"><h5>${revise.title}</h5>${metricGrid(revise.metrics)}${failBlock(revise.fails)}<p class="detail">${revise.note}</p></div>`)}
          ${laneHtml('报告审核', review, `<div class="lane-sub"><h5>${check.title}</h5>${metricGrid(check.metrics)}${failBlock(check.fails)}<p class="detail">${check.note}</p></div>`)}
        </div>`;
      box.append(article);
    });
  }

  function refreshEval() {
    const report = document.getElementById('eval-report-type').value;
    const stage = document.getElementById('eval-stage').value;
    renderKpis(report);
    renderReportStats(report, evalDuty);
    renderTypeFlows(report);
    renderEval(stage);
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
  document.getElementById('eval-stage').addEventListener('change', refreshEval);
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
  renderHeat();
  refreshEval();
  drawTrend();
})();
