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
    { model: 'gemini-3.7-flash', stage: 'REVIEW', stageName: '结果评审', n: 2721, score: '4.1', pass: '—', timeout: '4.2%', cost: '¥0.18', effective: '¥0.19', reco: 'keep', recoText: '保留主审' },
    { model: 'gpt-5.6-luna', stage: 'REVIEW', stageName: '结果评审', n: 27, score: '4.3', pass: '—', timeout: '0%', cost: '¥0.31', effective: '¥0.31', reco: 'thin', recoText: '样本不足' },
    { model: 'deepseek-v4-flash', stage: 'AUTHOR', stageName: '报告生成', n: 707, score: '3.1', pass: '26.31%', timeout: '1.8%', cost: '¥0.11', effective: '¥0.13', reco: 'keep', recoText: '保留基线' },
    { model: 'doubao-seed-2-1-pro-260628', stage: 'AUTHOR', stageName: '报告生成', n: 37, score: '2.9', pass: '27.03%', timeout: '6.1%', cost: '¥0.24', effective: '¥0.37', reco: 'wait', recoText: '停混跑，待对照' },
    { model: 'gemini-3.7-flash', stage: 'AUTHOR', stageName: '报告生成', n: 323, score: '2.6', pass: '—', timeout: '12.4%', cost: '¥0.29', effective: '¥0.41', reco: 'stop', recoText: '停用生成' },
    { model: 'gemini-3.7-flash', stage: 'FALLBACK', stageName: '兜底', n: 105, score: '3.4', pass: '—', timeout: '8.6%', cost: '¥0.33', effective: '¥0.33', reco: 'stop', recoText: '测试期关闭' },
    { model: 'gpt-5.6-luna', stage: 'AUTHOR', stageName: '报告生成', n: 16, score: '—', pass: '—', timeout: '0%', cost: '¥0.52', effective: '—', reco: 'thin', recoText: '样本不足' },
    { model: '—', stage: 'PREPARE', stageName: '数据准备', n: 29, score: '—', pass: '—', timeout: '—', cost: '¥0.00', effective: '¥0.00', reco: 'thin', recoText: '非模型问题' },
  ];

  const details = {
    7122: {
      title: '场次报告 #7122',
      state: '当前已生成的报告快照。7 次调用里有写、评、改、再评、兜底，这是混跑对照被污染的典型样本。',
      meta: [
        ['任务行 ID', '7122'],
        ['状态', 'SUCCESS'],
        ['末次模型', 'gemini-3.7-flash'],
        ['调用次数', '7'],
        ['生成耗时', '4 分 49.1 秒'],
        ['估算成本', '¥1.86（示意）'],
        ['首轮通过', '否'],
        ['兜底', '是 · 第 6 步改由 Gemini 重写'],
      ],
      attempts: [
        ['1', '生成', '1', 'doubao-seed-2-1-pro', '1 分 0.8 秒', '82.1k / 1.2k', '¥0.22', '成功', ''],
        ['2', '生成', '1', 'doubao-seed-2-1-pro', '31.2 秒', '83.4k / 1.2k', '¥0.22', '成功', '结构化输出重试'],
        ['3', '评审', '1', 'gemini-3.7-flash', '25.0 秒', '81.8k / 0.5k', '¥0.31', '未通过 3/5', '逻辑不自洽'],
        ['4', '修订', '2', 'doubao-seed-2-1-pro', '39.4 秒', '84.0k / 1.2k', '¥0.23', '成功', ''],
        ['5', '评审', '2', 'gemini-3.7-flash', '1 分 19.1 秒', '81.9k / 0.6k', '¥0.34', '未通过 2/5', '事实错误'],
        ['6', '兜底', '3', 'gemini-3.7-flash', '36.8 秒', '81.6k / 0.9k', '¥0.33', '成功', '换模重写'],
        ['7', '评审', '3', 'gemini-3.7-flash', '16.7 秒', '82.0k / 0.4k', '¥0.21', '通过 4/5', ''],
      ],
    },
    6074: {
      title: '场次报告 #6074',
      state: '钉死策略下的理想路径：一次生成、一次评审通过。',
      meta: [
        ['任务行 ID', '6074'],
        ['状态', 'SUCCESS'],
        ['末次模型', 'gemini-3.7-flash'],
        ['调用次数', '2'],
        ['生成耗时', '1 分 16.7 秒'],
        ['估算成本', '¥0.29（示意）'],
        ['首轮通过', '是'],
        ['兜底', '否'],
      ],
      attempts: [
        ['1', '生成', '1', 'deepseek-v4-flash', '53.1 秒', '56.4k / 1.1k', '¥0.08', '成功', ''],
        ['2', '评审', '1', 'gemini-3.7-flash', '23.5 秒', '57.1k / 0.5k', '¥0.21', '通过 4/5', ''],
      ],
    },
    5960: {
      title: '对手报告 #5960',
      state: '尚未生成报告快照。失败发生在数据准备，没有模型调用。',
      meta: [
        ['任务行 ID', '5960'],
        ['状态', 'FAILED'],
        ['节点', '数据准备'],
        ['失败代码', 'DATA_PLATFORM_NOT_READY'],
        ['调用次数', '0'],
        ['估算成本', '¥0.00'],
      ],
      attempts: [],
      message: '报告事实数据尚未就绪。这类失败计入准备节点就绪率，不计入模型质量分。',
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
      tr.innerHTML = `<td>${row.model}</td><td>${row.stageName}</td><td><span class="reco ${recoClass(row.reco)}">${row.recoText}</span></td><td class="score">${row.score}</td><td>${row.pass}</td><td>${row.effective}</td><td>${row.n}</td><td>${row.timeout}</td><td>${row.cost}</td>`;
      body.append(tr);
    }
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
    title.textContent = '本次执行 · 按节点的模型调用';
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
      for (const text of ['序号', '节点', '轮次', '模型', '结果', '成本', '耗时', 'token 入/出']) {
        const th = document.createElement('th');
        th.textContent = text;
        head.append(th);
      }
      const body = table.createTBody();
      data.attempts.forEach((item) => {
        const tr = body.insertRow();
        const result = item[7];
        if (result.includes('未通过') || result.includes('失败')) tr.className = 'attempt-fail';
        if (result.includes('通过') && !result.includes('未通过')) tr.className = 'attempt-pass';
        cell(tr, item[0]);
        cell(tr, item[1]);
        cell(tr, item[2]);
        cell(tr, item[3]);
        cell(tr, result, item[8] || '');
        cell(tr, item[6]);
        cell(tr, item[4]);
        cell(tr, item[5]);
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
