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
    { model: 'doubao-seed-2-1-pro-260628', stage: 'AUTHOR', stageName: '报告生成', n: 37, bind: '48%', harm: '8.1%', leak: '27%', score: '2.9', pass: '14%', reco: 'wait', recoText: '停混跑', effective: '¥0.37' },
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

  const scoreStats = [
    { author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', report: 'SESSION', n: 412, fact: 3.4, logic: 3.0, structure: 3.6, scope: 3.5, total: 3.2, factGe4: 114, totalGe4: 86, bindGe80: 128, noHarm: 402, leakOk: 189, pass: 86, veto: 38, band: [98, 228, 86] },
    { author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', report: 'POSITION', n: 148, fact: 3.2, logic: 2.9, structure: 3.4, scope: 3.3, total: 3.0, factGe4: 32, totalGe4: 24, bindGe80: 38, noHarm: 142, leakOk: 59, pass: 24, veto: 18, band: [42, 82, 24] },
    { author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', report: 'OPPONENT', n: 102, fact: 3.0, logic: 2.6, structure: 3.2, scope: 2.9, total: 2.8, factGe4: 18, totalGe4: 12, bindGe80: 20, noHarm: 97, leakOk: 32, pass: 12, veto: 16, band: [40, 50, 12] },
    { author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', report: 'HOME', n: 45, fact: 3.5, logic: 3.2, structure: 3.6, scope: 3.4, total: 3.3, factGe4: 14, totalGe4: 11, bindGe80: 16, noHarm: 44, leakOk: 22, pass: 11, veto: 3, band: [8, 26, 11] },
    { author: 'gemini-3.7-flash', reviewer: 'gemini-3.7-flash', report: 'SESSION', n: 180, fact: 2.9, logic: 2.5, structure: 3.2, scope: 2.8, total: 2.7, factGe4: 28, totalGe4: 23, bindGe80: 32, noHarm: 171, leakOk: 63, pass: 23, veto: 28, band: [72, 85, 23] },
    { author: 'gemini-3.7-flash', reviewer: 'gemini-3.7-flash', report: 'POSITION', n: 68, fact: 2.8, logic: 2.4, structure: 3.1, scope: 2.7, total: 2.6, factGe4: 9, totalGe4: 7, bindGe80: 11, noHarm: 64, leakOk: 22, pass: 7, veto: 12, band: [30, 31, 7] },
    { author: 'gemini-3.7-flash', reviewer: 'gemini-3.7-flash', report: 'OPPONENT', n: 55, fact: 2.6, logic: 2.2, structure: 3.0, scope: 2.5, total: 2.4, factGe4: 6, totalGe4: 4, bindGe80: 7, noHarm: 51, leakOk: 13, pass: 4, veto: 11, band: [28, 23, 4] },
    { author: 'gemini-3.7-flash', reviewer: 'gemini-3.7-flash', report: 'HOME', n: 20, fact: 3.0, logic: 2.7, structure: 3.3, scope: 2.9, total: 2.8, factGe4: 4, totalGe4: 3, bindGe80: 5, noHarm: 19, leakOk: 8, pass: 3, veto: 2, band: [7, 10, 3] },
    { author: 'doubao-seed-2-1-pro', reviewer: 'gemini-3.7-flash', report: 'SESSION', n: 22, fact: 3.1, logic: 2.8, structure: 3.3, scope: 3.0, total: 2.9, factGe4: 5, totalGe4: 4, bindGe80: 5, noHarm: 20, leakOk: 6, pass: 4, veto: 3, band: [7, 11, 4] },
    { author: 'doubao-seed-2-1-pro', reviewer: 'gemini-3.7-flash', report: 'POSITION', n: 6, fact: 3.0, logic: 2.7, structure: 3.2, scope: 2.9, total: 2.8, factGe4: 1, totalGe4: 1, bindGe80: 1, noHarm: 6, leakOk: 2, pass: 1, veto: 1, band: [2, 3, 1] },
    { author: 'doubao-seed-2-1-pro', reviewer: 'gemini-3.7-flash', report: 'OPPONENT', n: 7, fact: 2.7, logic: 2.3, structure: 3.0, scope: 2.6, total: 2.5, factGe4: 1, totalGe4: 1, bindGe80: 1, noHarm: 6, leakOk: 1, pass: 1, veto: 2, band: [3, 3, 1] },
    { author: 'deepseek-flash', reviewer: 'gemini-3.7-flash', report: 'SESSION', n: 48, fact: 3.1, logic: 2.8, structure: 3.3, scope: 3.1, total: 3.0, factGe4: 10, totalGe4: 8, bindGe80: 11, noHarm: 46, leakOk: 18, pass: 8, veto: 6, band: [14, 26, 8] },
    { author: 'deepseek-flash', reviewer: 'gemini-3.7-flash', report: 'POSITION', n: 18, fact: 3.0, logic: 2.7, structure: 3.2, scope: 3.0, total: 2.9, factGe4: 3, totalGe4: 2, bindGe80: 4, noHarm: 17, leakOk: 6, pass: 2, veto: 3, band: [6, 10, 2] },
    { author: 'deepseek-flash', reviewer: 'gemini-3.7-flash', report: 'OPPONENT', n: 12, fact: 2.8, logic: 2.5, structure: 3.1, scope: 2.7, total: 2.7, factGe4: 2, totalGe4: 1, bindGe80: 2, noHarm: 11, leakOk: 3, pass: 1, veto: 3, band: [5, 6, 1] },
    { author: 'deepseek-flash', reviewer: 'gemini-3.7-flash', report: 'HOME', n: 6, fact: 3.2, logic: 3.0, structure: 3.4, scope: 3.1, total: 3.1, factGe4: 2, totalGe4: 1, bindGe80: 2, noHarm: 6, leakOk: 3, pass: 1, veto: 1, band: [1, 4, 1] },
  ];

  const scoreCalls = [
    { id: 7122, report: 'SESSION', author: 'doubao-seed-2-1-pro', reviewer: 'gemini-3.7-flash', round: 1, fact: 3, logic: 2, structure: 4, scope: 4, total: 3.0, bind: 48, harm: '无', leak: '抓错', result: '不通过' },
    { id: 7122, report: 'SESSION', author: 'doubao-seed-2-1-pro', reviewer: 'gemini-3.7-flash', round: 2, fact: 2, logic: 3, structure: 4, scope: 4, total: 2.9, bind: 52, harm: '有', leak: '抓错', result: '一票否决' },
    { id: 7088, report: 'SESSION', author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', round: 1, fact: 4, logic: 4, structure: 5, scope: 4, total: 4.2, bind: 84, harm: '无', leak: '抓对', result: '通过' },
    { id: 6901, report: 'SESSION', author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', round: 1, fact: 3, logic: 3, structure: 4, scope: 3, total: 3.2, bind: 61, harm: '无', leak: '抓错', result: '不通过' },
    { id: 6814, report: 'POSITION', author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', round: 1, fact: 4, logic: 3, structure: 4, scope: 4, total: 3.7, bind: 82, harm: '无', leak: '抓对', result: '不通过' },
    { id: 6740, report: 'POSITION', author: 'gemini-3.7-flash', reviewer: 'gemini-3.7-flash', round: 1, fact: 2, logic: 2, structure: 3, scope: 3, total: 2.4, bind: 41, harm: '无', leak: '抓错', result: '一票否决' },
    { id: 6592, report: 'OPPONENT', author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', round: 1, fact: 3, logic: 2, structure: 3, scope: 2, total: 2.6, bind: 44, harm: '有', leak: '抓错', result: '一票否决' },
    { id: 6488, report: 'OPPONENT', author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', round: 2, fact: 4, logic: 3, structure: 4, scope: 3, total: 3.6, bind: 71, harm: '无', leak: '抓对', result: '不通过' },
    { id: 6320, report: 'HOME', author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', round: 1, fact: 4, logic: 4, structure: 4, scope: 5, total: 4.2, bind: 88, harm: '无', leak: '抓对', result: '通过' },
    { id: 6211, report: 'SESSION', author: 'gemini-3.7-flash', reviewer: 'gemini-3.7-flash', round: 1, fact: 3, logic: 2, structure: 4, scope: 3, total: 2.9, bind: 55, harm: '无', leak: '抓错', result: '不通过' },
    { id: 6104, report: 'SESSION', author: 'deepseek-v4-flash', reviewer: 'gemini-3.7-flash', round: 1, fact: 5, logic: 4, structure: 4, scope: 4, total: 4.4, bind: 91, harm: '无', leak: '抓对', result: '通过' },
    { id: 5980, report: 'HOME', author: 'gemini-3.7-flash', reviewer: 'gemini-3.7-flash', round: 1, fact: 3, logic: 3, structure: 3, scope: 3, total: 3.0, bind: 62, harm: '无', leak: '抓对', result: '不通过' },
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
        mix: '当前生成是 deepseek。混跑残留：Gemini 写了 14%，豆包 5%。',
        did: '写了 412 份场次稿，按审核意见改了 326 份。不给自己打分，也不当审核。',
        call: [['样本', '412'], ['调用成功', '98.5%'], ['超时', '2'], ['截断', '0'], ['P95', '10.9秒'], ['token', '56k / 1.1k'], ['单份', '¥0.13'], ['本窗口', '¥53']],
        quality: [['绑定', '64%'], ['伤害', '2.4%'], ['主泄漏', '46%'], ['可执行', '58%'], ['综合分', '3.2'], ['首轮过', '21%'], ['修订变好', '43%']],
        effective: '¥0.62',
        reco: 'keep',
        recoText: '留用生成基线',
        recoWhy: '四种里场次最好写。先把生成基线定下来。',
        fails: [['MODEL_TIMEOUT', 2, '写稿超时，报告未写出']],
        retry: { n: 6, avg: '1.2', max: 2, recovered: 5 },
        outcome: { first: 405, retry1: 4, retry2: 1, fail: 2 }
      },
      review: {
        pinned: 'gemini-3.7-flash',
        mix: '当前审核是 Gemini。混跑残留：Gemini 自己写过 14% 的场次稿。',
        did: '评了 412 份，判过 86 份（21%）。只打分、抓主泄漏，不改正文。程序先算绑定和伤害。',
        call: [['样本', '412'], ['调用成功', '95.4%'], ['超时', '13'], ['截断', '4'], ['不可用', '2'], ['P95', '25秒'], ['token', '61k / 0.8k'], ['单份', '¥0.19'], ['本窗口', '¥78']],
        quality: [['判过', '21%'], ['业务不过', '79%'], ['调用失败', '19'], ['事实均分', '3.6'], ['主泄漏抓错', '110']],
        effective: '¥0.20',
        reco: 'keep',
        recoText: '留用主审',
        recoWhy: '调用失败和业务不通过要分开。判过低主要是稿差。GPT 样本不够，不能换。',
        fails: [['MODEL_TIMEOUT', 13, '审核超时，没打出分'], ['MODEL_OUTPUT_TRUNCATED', 4, '审核输出被截断'], ['MODEL_UNAVAILABLE', 2, '审核不可用']],
        retry: { n: 24, avg: '1.3', max: 2, recovered: 12 },
        outcome: { first: 381, retry1: 9, retry2: 3, fail: 19 }
      },
    },
    {
      key: 'POSITION',
      name: '位置报告',
      job: '这个位置长期泄漏',
      prepare: '进入 152，程序失败 4（该位置无匹配手 3 · 事实未就绪 1）。不进生成。',
      generate: {
        pinned: 'deepseek-v4-flash',
        mix: '当前生成是 deepseek。混跑残留：Gemini 写了 12%。',
        did: '写了 148 份位置稿，改了 124 份。跨手证据比场次更难挂。',
        call: [['样本', '148'], ['调用成功', '99.0%'], ['超时', '0'], ['截断', '1'], ['P95', '11.4秒'], ['token', '58k / 1.2k'], ['单份', '¥0.14'], ['本窗口', '¥21']],
        quality: [['绑定', '58%'], ['伤害', '3.0%'], ['主泄漏', '41%'], ['可执行', '51%'], ['综合分', '3.0'], ['首轮过', '16%'], ['修订变好', '39%']],
        effective: '¥0.88',
        reco: 'keep',
        recoText: '留用，质量弱于场次',
        recoWhy: '套话比例高。生成岗先定下来，位置报告单独看。',
        fails: [['MODEL_OUTPUT_TRUNCATED', 1, '写稿被截断']],
        retry: { n: 2, avg: '1.0', max: 2, recovered: 2 },
        outcome: { first: 145, retry1: 2, retry2: 0, fail: 1 }
      },
      review: {
        pinned: 'gemini-3.7-flash',
        mix: '当前审核是 Gemini。长期泄漏有时被单手戏剧带偏。',
        did: '评了 148 份，判过 24 份（16%）。不改正文。',
        call: [['样本', '148'], ['调用成功', '95.0%'], ['超时', '5'], ['截断', '2'], ['P95', '28秒'], ['token', '63k / 0.9k'], ['单份', '¥0.20'], ['本窗口', '¥30']],
        quality: [['判过', '16%'], ['业务不过', '84%'], ['调用失败', '7'], ['事实均分', '3.4'], ['主泄漏抓错', '48']],
        effective: '¥0.21',
        reco: 'keep',
        recoText: '留用主审',
        recoWhy: '超时略高于场次。判过低仍是稿差。',
        fails: [['MODEL_TIMEOUT', 5, '审核超时'], ['MODEL_OUTPUT_TRUNCATED', 2, '审核截断']],
        retry: { n: 11, avg: '1.2', max: 2, recovered: 7 },
        outcome: { first: 134, retry1: 5, retry2: 2, fail: 7 }
      },
    },
    {
      key: 'OPPONENT',
      name: '对手报告',
      job: '对面风格和应对',
      prepare: '进入 118，程序失败 16（13.6%，四种最高：对手范围无匹配手 11 · 统计未就绪 5）。这是数据问题，不是模型质量。',
      generate: {
        pinned: 'deepseek-v4-flash',
        mix: '当前生成是 deepseek。混跑残留：Gemini 写了 16%，豆包 5%。',
        did: '写了 102 份对手稿，改了 90 份。风格判断最容易写反，修订也最不值钱。',
        call: [['样本', '102'], ['调用成功', '97.2%'], ['超时', '1'], ['非法输出', '1'], ['P95', '12.6秒'], ['token', '62k / 1.3k'], ['单份', '¥0.16'], ['本窗口', '¥16']],
        quality: [['绑定', '52%'], ['伤害', '4.8%'], ['主泄漏', '31%'], ['可执行', '41%'], ['综合分', '2.8'], ['首轮过', '12%'], ['修订变好', '33%']],
        effective: '¥1.33',
        reco: 'wait',
        recoText: '留用但优先换生成',
        recoWhy: '质量最差、有效成本最高。这里是下一次选模的第一优先级。',
        fails: [['MODEL_TIMEOUT', 1, '写稿超时'], ['MODEL_STRUCTURED_OUTPUT_INVALID', 1, '结构化输出非法']],
        retry: { n: 5, avg: '1.7', max: 2, recovered: 3 },
        outcome: { first: 97, retry1: 2, retry2: 1, fail: 2 }
      },
      review: {
        pinned: 'gemini-3.7-flash',
        mix: '当前审核是 Gemini。判过最低，主要是稿差，不是审核更严。',
        did: '评了 102 份，判过 12 份（12%）。不改正文。',
        call: [['样本', '102'], ['调用成功', '94.1%'], ['超时', '4'], ['不可用', '2'], ['P95', '31秒'], ['token', '66k / 1.0k'], ['单份', '¥0.22'], ['本窗口', '¥22']],
        quality: [['判过', '12%'], ['业务不过', '88%'], ['调用失败', '6'], ['事实均分', '3.1'], ['主泄漏抓错', '41']],
        effective: '¥0.23',
        reco: 'keep',
        recoText: '留用主审',
        recoWhy: '不要因为判过低就换审核。先把生成岗换好。',
        fails: [['MODEL_TIMEOUT', 4, '审核超时'], ['MODEL_UNAVAILABLE', 2, '审核不可用']],
        retry: { n: 10, avg: '1.3', max: 2, recovered: 6 },
        outcome: { first: 90, retry1: 4, retry2: 2, fail: 6 }
      },
    },
    {
      key: 'HOME',
      name: '首页总结',
      job: '多场汇总给用户看',
      prepare: '进入 48，程序失败 3（多场汇总事实未就绪）。',
      generate: {
        pinned: 'deepseek-v4-flash',
        mix: '当前生成是 deepseek。混跑残留：Gemini 写了 10%。',
        did: '写了 45 份首页总结，改了 34 份。较少点名单手，伤害低。',
        call: [['样本', '45'], ['调用成功', '99.1%'], ['超时', '0'], ['截断', '0'], ['P95', '9.8秒'], ['token', '48k / 0.9k'], ['单份', '¥0.11'], ['本窗口', '¥5']],
        quality: [['绑定', '70%'], ['伤害', '1.8%'], ['主泄漏', '48%'], ['可执行', '61%'], ['综合分', '3.3'], ['首轮过', '24%'], ['修订变好', '48%']],
        effective: '¥0.46',
        reco: 'thin',
        recoText: '留用 · 样本偏少',
        recoWhy: '四种里最好看，但 n=45，数字会跳。不要据此换别的岗。',
        fails: [],
        retry: { n: 0, avg: '0', max: 2, recovered: 0 },
        outcome: { first: 45, retry1: 0, retry2: 0, fail: 0 }
      },
      review: {
        pinned: 'gemini-3.7-flash',
        mix: '当前审核是 Gemini。四种里最好看，同样受样本限制。',
        did: '评了 45 份，判过 11 份（24%）。不改正文。',
        call: [['样本', '45'], ['调用成功', '96.2%'], ['超时', '2'], ['P95', '22秒'], ['token', '52k / 0.7k'], ['单份', '¥0.18'], ['本窗口', '¥8']],
        quality: [['判过', '24%'], ['业务不过', '76%'], ['调用失败', '2'], ['事实均分', '3.8'], ['主泄漏抓错', '12']],
        effective: '¥0.19',
        reco: 'thin',
        recoText: '留用 · 样本偏少',
        recoWhy: '不能用首页总结的分数去证明 Gemini 适合写稿。',
        fails: [['MODEL_TIMEOUT', 2, '审核超时']],
        retry: { n: 3, avg: '1.5', max: 2, recovered: 2 },
        outcome: { first: 41, retry1: 2, retry2: 0, fail: 2 }
      },
    },
  ];

  const spendShare = [
    { model: 'gemini-3.7-flash', work: '评审 ¥214 · 写稿 ¥88', calls: 3044, yen: 302, pct: 59, unit: '¥0.10', color: '#1677d2' },
    { model: 'deepseek-v4-flash', work: '当前生成', calls: 4081, yen: 126, pct: 25, unit: '¥0.03', color: '#176f59' },
    { model: 'doubao-seed-2-1-pro', work: '历史混跑写稿', calls: 223, yen: 41, pct: 8, unit: '¥0.18', color: '#7147d9' },
    { model: 'gpt-5.6-luna', work: '评审 ¥16 · 写稿 ¥9', calls: 43, yen: 25, pct: 5, unit: '¥0.58', color: '#e86f16' },
    { model: 'deepseek-flash', work: '旧生成线路', calls: 285, yen: 18, pct: 3, unit: '¥0.06', color: '#c4b078' },
  ];

  const modelView = [
    {
      model: 'deepseek-v4-flash',
      work: '当前生成',
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
      work: '当前审核 · 旧混跑写稿',
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
      work: '历史混跑审核',
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
    if (row.model === 'deepseek-v4-flash' && row.duty === 'AUTHOR') return '当前生成';
    if (row.model === 'gemini-3.7-flash' && row.duty === 'REVIEW') return '当前审核';
    if (row.model === 'gemini-3.7-flash' && row.duty === 'AUTHOR') return '旧混跑写稿';
    if (String(row.model).startsWith('doubao')) return '旧混跑写稿';
    if (String(row.model).startsWith('gpt')) return '历史混跑审核';
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

  function flowTable(flow) {
    const heads = ['岗位', '模型', '样本', '成功', '首次成功', '重试1次', '重试2次', 'P95', 'token', '单份', '窗口', '绑定', '伤害', '主泄漏', '可执行', '综合', '通过', '有效成本', '失败', '重试请求', '失败原因'];
    return `<div class="table-scroll"><table class="wide-slot">
      <thead><tr>${heads.map((name) => `<th>${name}</th>`).join('')}</tr></thead>
      <tbody>
        <tr class="prep"><th>准备</th><td colspan="${heads.length - 1}">${flow.prepare}</td></tr>
        ${slotRow('author', '生成', flow.generate, `slot-${flow.key}-author`)}
        ${slotRow('review', '审核', flow.review, `slot-${flow.key}-review`)}
      </tbody>
    </table></div>`;
  }

  function showEvalPane(id) {
    document.querySelectorAll('.eval-nav [role="tab"]').forEach((btn) => {
      btn.setAttribute('aria-selected', String(btn.dataset.pane === id));
    });
    document.querySelectorAll('.eval-pane').forEach((pane) => {
      pane.hidden = pane.id !== id;
    });
  }

  function callCell(kind, flow, slot, costHint) {
    return `<a class="call-cell ${kind}" href="#slot-${flow.key}-${kind === 'author' ? 'author' : 'review'}" data-report="${flow.key}">
      <span class="call-who">${slot.pinned}</span>
      <span class="call-cost">有效成本 ${slot.effective}${costHint}</span>
    </a>`;
  }

  function stepHead(tag) {
    return tag ? `<p class="eval-scope">${tag}</p>` : '';
  }

  function scopeName(report) {
    if (report === 'ALL') return '全部报告';
    return callSlots.find((item) => item.key === report).name;
  }

  function syncTypeChips(report) {
    const chips = document.getElementById('flow-type-chips');
    if (!chips) return;
    for (const button of chips.querySelectorAll('[data-report]')) {
      button.setAttribute('aria-pressed', String(button.dataset.report === report));
    }
  }

  function renderSlots(report) {
    const box = document.getElementById('eval-slots');
    if (!box) return;
    syncTypeChips(report);
    const matrix = document.createElement('table');
    matrix.className = 'call-matrix';
    matrix.innerHTML = `<colgroup><col class="type"><col><col></colgroup><thead><tr><th>报告类型</th><th>生成</th><th>审核</th></tr></thead><tbody>${callSlots.map((flow) => `<tr class="${report === 'ALL' || report === flow.key ? 'is-on' : 'is-dim'}">
      <th scope="row">${flow.name}</th>
      <td>${callCell('author', flow, flow.generate, ' / 过一份')}</td>
      <td>${callCell('review', flow, flow.review, ' / 次审核')}</td>
    </tr>`).join('')}</tbody>`;
    matrix.addEventListener('click', (event) => {
      const link = event.target.closest('[data-report]');
      if (!link) return;
      event.preventDefault();
      document.getElementById('eval-report-type').value = link.dataset.report;
      refreshEval();
      showEvalPane('eval-reports');
    });
    box.replaceChildren();
    box.append(matrix);
  }

  function renderReports(report) {
    const box = document.getElementById('eval-reports');
    if (!box) return;
    const rows = report === 'ALL' ? callSlots : callSlots.filter((row) => row.key === report);
    box.innerHTML = `${stepHead(report === 'ALL' ? '' : scopeName(report))}
      ${rows.map((flow) => `<article class="type-flow">
        <div class="type-head">
          <h3>${flow.name}</h3>
          <span class="posts">生成 <em>${flow.generate.pinned}</em> · 审核 <em>${flow.review.pinned}</em></span>
        </div>
        ${flowTable(flow)}
      </article>`).join('')}`;
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
    const main = slices[0] || { n: 0, label: '无', hint: '无' };
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

  function sumOutcome(items) {
    return items.reduce((acc, item) => ({
      first: acc.first + item.first,
      retry1: acc.retry1 + item.retry1,
      retry2: acc.retry2 + item.retry2,
      fail: acc.fail + item.fail,
    }), { first: 0, retry1: 0, retry2: 0, fail: 0 });
  }

  function packOutcome(raw, name, model) {
    const ok = raw.first + raw.retry1 + raw.retry2;
    const jobs = ok + raw.fail;
    return Object.assign({ name, model: model || '', ok, jobs }, raw);
  }

  function statsFor(report) {
    if (report === 'ALL') {
      return {
        all: packOutcome(overallCallStats, '全部调用', '生成 deepseek-v4-flash · 审核 gemini-3.7-flash'),
        author: packOutcome(overallCallStats.author, '生成调用', 'deepseek-v4-flash'),
        review: packOutcome(overallCallStats.review, '审核调用', 'gemini-3.7-flash'),
        rows: [
          packOutcome(overallCallStats, '全部调用', '生成 deepseek-v4-flash · 审核 gemini-3.7-flash'),
          packOutcome(overallCallStats.author, '生成调用', 'deepseek-v4-flash'),
          packOutcome(overallCallStats.review, '审核调用', 'gemini-3.7-flash'),
        ],
      };
    }
    const flow = callSlots.find((row) => row.key === report);
    const author = packOutcome(flow.generate.outcome, `${flow.name} · 生成`, flow.generate.pinned);
    const review = packOutcome(flow.review.outcome, `${flow.name} · 审核`, flow.review.pinned);
    const all = packOutcome(sumOutcome([flow.generate.outcome, flow.review.outcome]), `${flow.name} · 全部`, `生成 ${flow.generate.pinned} · 审核 ${flow.review.pinned}`);
    return {
      all,
      author,
      review,
      rows: [all, author, review],
    };
  }

  function failRowsFor(report) {
    return report === 'ALL' ? failDist : failDist.filter((row) => row.report === report);
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

  function renderFails(report) {
    const box = document.getElementById('eval-fails');
    if (!box) return;
    const rows = failRowsFor(report);
    const total = rows.reduce((sum, row) => sum + row.n, 0);
    if (!total) {
      box.innerHTML = `<p class="detail">当前筛选下无模型调用失败。</p>`;
      return;
    }
    const byReport = groupFail(rows, (row) => row.report, (row) => row.reportName, (row) => reportColors[row.report]);
    const byDuty = groupFail(rows, (row) => row.duty, (row) => row.dutyName, (row) => (row.duty === 'AUTHOR' ? '#176f59' : '#1677d2'));
    const byModel = groupFail(rows, (row) => row.model, (row) => modelShort[row.model] || row.model, (row) => modelColors[row.model] || '#637570');
    const byReason = groupFail(rows, (row) => row.code, (row) => failReasonMeta[row.code].name, (row) => failReasonMeta[row.code].color);
    const secondPie = report === 'ALL'
      ? pieCard('失败按报告类型', byReport.map((item) => ({ label: item.name, n: item.n, color: item.color, hint: '占失败' })), shareText(byReport[0].n, total))
      : pieCard('失败按岗位', byDuty.map((item) => ({ label: item.name, n: item.n, color: item.color, hint: '占失败' })), shareText(byDuty[0].n, total));
    const callRows = rows.slice().sort((a, b) => {
      const code = failCodes.indexOf(a.code) - failCodes.indexOf(b.code);
      if (code) return code;
      return b.n - a.n;
    });
    box.innerHTML = `${stepHead(report === 'ALL' ? `${total.toLocaleString('zh-CN')} 次失败` : `${scopeName(report)} · ${total.toLocaleString('zh-CN')} 次失败`)}
      <div class="pie-grid fail-pies">
        ${pieCard('失败按模型', byModel.map((item) => ({ label: item.name, n: item.n, color: item.color, hint: '占失败' })), shareText(byModel[0].n, total))}
        ${secondPie}
        ${pieCard('失败原因构成', byReason.map((item) => ({ label: item.name, n: item.n, color: item.color, hint: '占失败' })), shareText(byReason[0].n, total))}
      </div>
      <div class="table-scroll">
        <table class="wide-slot fail-reason-table">
          <thead>
            <tr>
              <th>模型</th><th>调用点</th>${report === 'ALL' ? '<th>报告类型</th>' : ''}<th>失败原因</th><th>次数</th><th>占失败</th><th>占该模型调用</th><th>占该调用点</th><th>说明</th>
            </tr>
          </thead>
          <tbody>
            ${callRows.map((row) => {
              const slotJobs = slotCallVolume(row.model, row.duty, row.report);
              return `<tr class="${row.duty === 'AUTHOR' ? 'author' : 'review'}">
              <th>${row.model}</th>
              <td>${row.dutyName}</td>
              ${report === 'ALL' ? `<td>${row.reportName}</td>` : ''}
              <td>${failReasonMeta[row.code].name}<span class="detail">${row.code}</span></td>
              <td><span class="fail-n">${row.n}</span></td>
              <td>${shareText(row.n, total)}</td>
              <td>${failShare(row.n, row.model)}<span class="detail">/${modelCallVolume(row.model).toLocaleString('zh-CN')}</span></td>
              <td>${slotShare(row.n, row.model, row.duty, row.report)}<span class="detail">/${slotJobs.toLocaleString('zh-CN')}</span></td>
              <td>${failReasonMeta[row.code].detail}</td>
            </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function renderOverview(report) {
    const box = document.getElementById('eval-overview');
    if (!box) return;
    const stats = statsFor(report);
    const all = stats.all;
    const spendTotal = modelView.reduce((sum, row) => sum + spendSlice(row.model, report).yen, 0);
    const p95Gen = report === 'ALL' ? '11.2秒' : pickMetric(callSlots.find((row) => row.key === report).generate.call, 'P95');
    const p95Rev = report === 'ALL' ? '25.8秒' : pickMetric(callSlots.find((row) => row.key === report).review.call, 'P95');
    const failHint = report === 'ALL' ? '主因超时' : '';
    box.innerHTML = `
      <div class="kpi-grid five eval-kpis">
        <article><span>调用</span><strong>${all.jobs.toLocaleString('zh-CN')}</strong><span class="detail">本窗口任务数</span></article>
        <article><span>成功率</span><strong>${rateText(all.ok, all.jobs)}</strong><span class="detail">成功 ${all.ok.toLocaleString('zh-CN')}</span></article>
        <article><span>失败</span><strong>${all.fail.toLocaleString('zh-CN')}</strong>${failHint ? `<span class="detail">${failHint}</span>` : ''}</article>
        <article><span>${report === 'ALL' ? '窗口成本' : '该报告成本'}</span><strong>¥${spendTotal}</strong></article>
        <article><span>P95</span><strong>${p95Gen} / ${p95Rev}</strong><span class="detail">生成 / 审核</span></article>
      </div>
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
              <th>调用</th><th>模型</th><th>任务</th><th>成功</th><th>失败</th><th>成功率</th><th>失败率</th><th>首次成功</th><th>首次占比</th><th>重试 1 次</th><th>重试 2 次</th><th>经重试成功</th>
            </tr>
          </thead>
          <tbody>
            ${stats.rows.map((row) => {
              const retryOkRow = row.retry1 + row.retry2;
              return `<tr>
                <th>${row.name}</th>
                <td>${row.model}</td>
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
      </div>`;
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

  function spendOf(model) {
    return spendShare.find((row) => row.model === model) || { yen: 0, pct: 0, unit: '—', color: '#637570' };
  }

  function spendSlice(model, report) {
    const spend = spendOf(model);
    const row = modelView.find((item) => item.model === model);
    if (!row) return { yen: 0, color: spend.color };
    if (report === 'ALL') return { yen: spend.yen, color: spend.color };
    const allJobs = sliceOf(row, 'ALL').jobs;
    const jobs = sliceOf(row, report).jobs;
    return { yen: allJobs ? Math.round(spend.yen * jobs / allJobs) : 0, color: spend.color };
  }

  function spendTrackHtml(items) {
    const ranked = items.filter((row) => row.yen > 0).slice().sort((a, b) => b.yen - a.yen);
    const total = ranked.reduce((sum, row) => sum + row.yen, 0);
    if (!total) return '';
    return `<div class="spend-track">${ranked.map((row) => {
      const pct = row.pct != null ? row.pct : (row.yen / total) * 100;
      return `<span style="width:${pct}%;background:${row.color}" title="${row.model} ¥${row.yen}（${Math.round(pct)}%）">${pct >= 8 ? `${Math.round(pct)}%` : ''}</span>`;
    }).join('')}</div>
      <div class="mix-legend">${ranked.map((row) => {
        const pct = row.pct != null ? row.pct : (row.yen / total) * 100;
        return `<span><i style="background:${row.color}"></i>${modelShort[row.model] || row.model} ${Math.round(pct)}%</span>`;
      }).join('')}</div>`;
  }

  function renderModels(report) {
    const box = document.getElementById('eval-models');
    if (!box) return;
    const rows = modelView.map((row) => {
      const slice = sliceOf(row, report);
      const spend = spendSlice(row.model, report);
      return { row, slice, ok: slice.jobs - slice.fail, spend };
    }).filter((item) => item.slice.jobs > 0);
    const jobsAll = rows.reduce((sum, item) => sum + item.slice.jobs, 0);
    const okAll = rows.reduce((sum, item) => sum + item.ok, 0);
    const spendTotal = rows.reduce((sum, item) => sum + item.spend.yen, 0);
    const isAll = report === 'ALL';
    const tag = isAll ? '全部报告' : scopeName(report);
    const bizHead = isAll
      ? reportKeys.map((key) => `<th>${reportShort[key]}成功率</th>`).join('') + '<th>成功落点</th><th>成本</th><th>成本占比</th>'
      : '<th>占该模型调用</th><th>占该报告调用</th><th>占该报告成功</th><th>成本</th><th>成本占比</th>';
    const body = rows.map(({ row, slice, ok, spend }) => {
      const modelJobs = sliceOf(row, 'ALL').jobs;
      const spendPct = isAll
        ? `${spendOf(row.model).pct}%`
        : (spendTotal ? `${((spend.yen / spendTotal) * 100).toFixed(0)}%` : '—');
      const bizCells = isAll
        ? reportKeys.map((key) => {
            const cell = row.biz[key];
            const cellOk = cell.jobs - cell.fail;
            return `<td class="${rateClass(cellOk, cell.jobs)}">${rateText(cellOk, cell.jobs)}</td>`;
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
        <td>¥${spend.yen}</td>
        <td>${spendPct}</td>
        <td>${slice.p50}</td>
        <td class="${speedClass(slice.p95)}">${slice.p95}</td>
        <td>${modelFailWhy(row.model, report)}</td>
      </tr>`;
    }).join('');
    const bars = spendTrackHtml(isAll
      ? spendShare
      : rows.map(({ row, spend }) => ({ model: row.model, yen: spend.yen, color: spend.color })));
    box.innerHTML = `${stepHead(tag)}
      ${bars}
      <div class="table-scroll">
        <table class="wide-slot model-table">
          <thead>
            <tr>
              <th>模型</th><th>调用</th><th>成功</th><th>失败</th><th>成功率</th><th>失败率</th>${bizHead}<th>P50</th><th>P95</th><th>主失败原因</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>`;
  }

  function dimClass(value, line) {
    if (value >= line) return 'score-ok';
    if (value <= 2) return 'score-bad';
    return 'score-mid';
  }

  function resultClass(result) {
    if (result === '通过') return 'score-ok';
    if (result === '一票否决') return 'score-mid';
    return 'score-bad';
  }

  function modelWork(name) {
    const row = modelView.find((item) => item.model === name);
    return row ? row.work : '';
  }

  function rollupByAuthor(rows) {
    const map = new Map();
    for (const row of rows) {
      let cur = map.get(row.author);
      if (!cur) {
        cur = {
          author: row.author,
          reviewer: row.reviewer,
          n: 0,
          fact: 0,
          logic: 0,
          structure: 0,
          scope: 0,
          total: 0,
          factGe4: 0,
          totalGe4: 0,
          bindGe80: 0,
          noHarm: 0,
          leakOk: 0,
          pass: 0,
          veto: 0,
          band: [0, 0, 0],
        };
        map.set(row.author, cur);
      }
      cur.n += row.n;
      cur.fact += row.fact * row.n;
      cur.logic += row.logic * row.n;
      cur.structure += row.structure * row.n;
      cur.scope += row.scope * row.n;
      cur.total += row.total * row.n;
      cur.factGe4 += row.factGe4;
      cur.totalGe4 += row.totalGe4;
      cur.bindGe80 += row.bindGe80;
      cur.noHarm += row.noHarm;
      cur.leakOk += row.leakOk;
      cur.pass += row.pass;
      cur.veto += row.veto;
      cur.band = cur.band.map((v, i) => v + row.band[i]);
    }
    return [...map.values()].map((cur) => ({
      ...cur,
      fact: cur.fact / cur.n,
      logic: cur.logic / cur.n,
      structure: cur.structure / cur.n,
      scope: cur.scope / cur.n,
      total: cur.total / cur.n,
    })).sort((a, b) => b.n - a.n);
  }

  function scoreModelRow(row) {
    return `<tr>
      <th>${row.author}<span class="detail">${modelWork(row.author)}</span></th>
      <td>${row.n.toLocaleString('zh-CN')}</td>
      <td class="${dimClass(row.fact, 4)}">${row.fact.toFixed(1)}</td>
      <td class="${dimClass(row.logic, 4)}">${row.logic.toFixed(1)}</td>
      <td class="${dimClass(row.structure, 4)}">${row.structure.toFixed(1)}</td>
      <td class="${dimClass(row.scope, 4)}">${row.scope.toFixed(1)}</td>
      <td class="${dimClass(row.total, 4)}"><span class="score-total">${row.total.toFixed(1)}</span></td>
      <td class="score-ok">${rateText(row.pass, row.n)}</td>
      <td class="score-mid">${rateText(row.veto, row.n)}</td>
      <td>${rateText(row.totalGe4, row.n)}</td>
      <td>${rateText(row.factGe4, row.n)}</td>
      <td>${rateText(row.bindGe80, row.n)}</td>
      <td>${rateText(row.noHarm, row.n)}</td>
      <td>${rateText(row.leakOk, row.n)}</td>
    </tr>`;
  }

  function renderScores(report) {
    const box = document.getElementById('eval-scores');
    if (!box) return;
    const rows = report === 'ALL' ? scoreStats : scoreStats.filter((row) => row.report === report);
    const models = rollupByAuthor(rows);
    const calls = report === 'ALL' ? scoreCalls : scoreCalls.filter((row) => row.report === report);
    const n = rows.reduce((sum, row) => sum + row.n, 0);
    const wavg = (key) => (n ? rows.reduce((sum, row) => sum + row[key] * row.n, 0) / n : 0);
    const sumKey = (key) => rows.reduce((sum, row) => sum + row[key], 0);
    const pass = sumKey('pass');
    const veto = sumKey('veto');
    const bind = sumKey('bindGe80');
    const leak = sumKey('leakOk');
    const factGe4 = sumKey('factGe4');
    const totalGe4 = sumKey('totalGe4');
    const noHarm = sumKey('noHarm');
    const band = rows.reduce((acc, row) => acc.map((v, i) => v + row.band[i]), [0, 0, 0]);
    const tag = report === 'ALL' ? '全部报告' : scopeName(report);
    const split = report === 'ALL' ? `
      <h4 class="score-block-title">按报告拆开</h4>
      <p class="detail">同一模型在不同报告上的分。选上面的场次 / 位置 / 对手 / 首页，只看那一类。</p>
      <div class="table-scroll">
        <table class="wide-slot score-table">
          <thead>
            <tr>
              <th>模型</th><th>报告</th><th>打分次数</th>
              <th>事实</th><th>逻辑</th><th>结构</th><th>范围</th><th>综合</th>
              <th>通过</th><th>否决</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => `<tr>
              <th>${row.author}</th>
              <td>${scopeName(row.report)}</td>
              <td>${row.n.toLocaleString('zh-CN')}</td>
              <td class="${dimClass(row.fact, 4)}">${row.fact.toFixed(1)}</td>
              <td class="${dimClass(row.logic, 4)}">${row.logic.toFixed(1)}</td>
              <td class="${dimClass(row.structure, 4)}">${row.structure.toFixed(1)}</td>
              <td class="${dimClass(row.scope, 4)}">${row.scope.toFixed(1)}</td>
              <td class="${dimClass(row.total, 4)}">${row.total.toFixed(1)}</td>
              <td class="score-ok">${rateText(row.pass, row.n)}</td>
              <td class="score-mid">${rateText(row.veto, row.n)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>` : '';
    box.innerHTML = `${stepHead(tag)}
      <h4 class="score-block-title" style="margin-top:0">各模型得分</h4>
      <p class="detail">一行一个生成模型。分数是评审（gemini-3.7-flash）打的，不是自评。gpt-5.6-luna 只审核、不打质量分，所以没有被评分。</p>
      <div class="table-scroll">
        <table class="wide-slot score-model-table">
          <thead>
            <tr>
              <th>模型</th><th>打分次数</th>
              <th>事实</th><th>逻辑</th><th>结构</th><th>范围</th><th>综合</th>
              <th>通过</th><th>否决</th><th>综合≥4.0</th><th>事实≥4</th><th>绑定≥80%</th><th>无伤害</th><th>主泄漏抓对</th>
            </tr>
          </thead>
          <tbody>${models.map(scoreModelRow).join('')}</tbody>
        </table>
      </div>
      <div class="kpi-grid five eval-kpis" style="margin-top:16px">
        <article><span>已打分</span><strong>${n.toLocaleString('zh-CN')}</strong><span class="detail">评审对生成稿的打分次数</span></article>
        <article><span>综合均分</span><strong>${wavg('total').toFixed(1)}</strong><span class="detail">加权 · 过线 4.0</span></article>
        <article><span>通过</span><strong>${rateText(pass, n)}</strong><span class="detail">${pass.toLocaleString('zh-CN')} 次硬指标全过</span></article>
        <article><span>一票否决</span><strong>${rateText(veto, n)}</strong><span class="detail">${veto.toLocaleString('zh-CN')} 次</span></article>
        <article><span>综合分分布</span><strong>${shareText(band[2], n)}</strong><span class="detail">低于3分 ${band[0]} · 3到4分 ${band[1]} · 过线 ${band[2]}</span></article>
      </div>
      <div class="kpi-grid five" style="margin-top:10px">
        <article><span>事实≥4</span><strong>${rateText(factGe4, n)}</strong></article>
        <article><span>综合≥4.0</span><strong>${rateText(totalGe4, n)}</strong></article>
        <article><span>绑定≥80%</span><strong>${rateText(bind, n)}</strong></article>
        <article><span>无伤害</span><strong>${rateText(noHarm, n)}</strong></article>
        <article><span>主泄漏抓对</span><strong>${rateText(leak, n)}</strong></article>
      </div>
      ${split}
      <h4 class="score-block-title">单次打分明细</h4>
      <p class="detail">抽样示意。同一任务多轮会各记一条，用来看修订有没有把分打上去。</p>
      <div class="table-scroll">
        <table class="wide-slot score-call-table">
          <thead>
            <tr>
              <th>任务</th><th>报告</th><th>生成</th><th>评审</th><th>轮次</th>
              <th>事实</th><th>逻辑</th><th>结构</th><th>范围</th><th>综合</th>
              <th>绑定</th><th>伤害</th><th>主泄漏</th><th>结果</th>
            </tr>
          </thead>
          <tbody>
            ${calls.map((row) => `<tr>
              <th>#${row.id}</th>
              <td>${scopeName(row.report)}</td>
              <td>${row.author}</td>
              <td>${row.reviewer}</td>
              <td>${row.round}</td>
              <td class="${dimClass(row.fact, 4)}">${row.fact}</td>
              <td class="${dimClass(row.logic, 4)}">${row.logic}</td>
              <td class="${dimClass(row.structure, 4)}">${row.structure}</td>
              <td class="${dimClass(row.scope, 4)}">${row.scope}</td>
              <td class="${dimClass(row.total, 4)}">${row.total.toFixed(1)}</td>
              <td class="${row.bind >= 80 ? 'score-ok' : 'score-bad'}">${row.bind}%</td>
              <td class="${row.harm === '有' ? 'score-bad' : 'score-ok'}">${row.harm}</td>
              <td class="${row.leak === '抓对' ? 'score-ok' : 'score-bad'}">${row.leak}</td>
              <td class="${resultClass(row.result)}">${row.result}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <h4 class="score-block-title">打分规则</h4>
      <p class="formula">综合分 = 事实×40% + 逻辑×30% + 结构×15% + 范围×15%。生成模型不给自己打分。评审只打分、不改正文。准备失败不进质量分。</p>
      <div class="pass-line">
        <span class="pass-ok">通过：无伤害 · 绑定 ≥ 80% · 主泄漏抓对 · 事实 ≥ 4 · 综合 ≥ 4.0</span>
        <span class="pass-no">不通过：硬指标或分数未达标，回原生成模型修订</span>
        <span class="pass-veto">一票否决：伤害性错误，或主泄漏抓错，或事实 / 范围 ≤ 2</span>
      </div>
      <div class="table-scroll" style="margin:14px 0 0">
        <table class="rules-table">
          <thead><tr><th>维度</th><th>谁算</th><th>卡线</th></tr></thead>
          <tbody>
            <tr><td>事实 / 逻辑 / 结构 / 范围</td><td>评审模型</td><td>事实 ≥ 4 且综合 ≥ 4.0；事实或范围 ≤ 2 否决</td></tr>
            <tr><td>证据绑定</td><td>程序</td><td>≥ 80% 才能过</td></tr>
            <tr><td>伤害性错误</td><td>程序 + 评审</td><td>出现即否决</td></tr>
            <tr><td>主泄漏</td><td>评审模型</td><td>抓错即否决</td></tr>
            <tr><td>建议可执行 / 修订变好 / 牌理</td><td>程序粗判 + 评审</td><td>记分，暂不单独否决</td></tr>
          </tbody>
        </table>
      </div>`;
  }

  function refreshEval() {
    const report = document.getElementById('eval-report-type').value;
    renderOverview(report);
    renderSlots(report);
    renderModels(report);
    renderFails(report);
    renderScores(report);
    renderReports(report);
    renderReportStats(report, evalDuty);
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
    showEvalPane('eval-scores');
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
  document.querySelector('.eval-nav').addEventListener('click', (event) => {
    const tab = event.target.closest('[data-pane]');
    if (!tab) return;
    showEvalPane(tab.dataset.pane);
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
