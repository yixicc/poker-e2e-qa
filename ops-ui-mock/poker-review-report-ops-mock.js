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
    document.getElementById('score-rules').scrollIntoView({ behavior: 'smooth', block: 'start' });
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
  document.getElementById('eval-stage').addEventListener('change', (event) => renderEval(event.target.value));
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
  renderEval('ALL');
  drawTrend();
})();
