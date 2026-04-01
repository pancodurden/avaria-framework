/* ── API endpoints ── */
const API = {
  models:     '/api/models',
  genExperts: '/api/generate-experts',
  startDebate:'/api/start-debate',
  stream: id =>`/api/debate-stream/${id}`
};

/* ── Step config ── */
const STEP_CONFIG = [
  { color: 'blue',   agent: 'UZMAN I',       title: 'Acilis Tezi'   },
  { color: 'purple', agent: 'UZMAN II',       title: 'Karsi Arguman' },
  { color: 'blue',   agent: 'UZMAN I',        title: 'Savunma'       },
  { color: 'purple', agent: 'UZMAN III',      title: 'Hakem Analizi' },
  { color: 'green',  agent: 'SENTEZLEYICI',   title: 'Sentez'        },
  { color: 'amber',  agent: 'YUK. MAHKEME',   title: 'Nihai Karar'   },
];

const TOTAL_STEPS = 6;

const BTN_LAUNCH_HTML   = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg> Sistemi Baslat`;
const BTN_GENERATE_HTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> Uzman Komitesini Olustur`;

const PERSONALITY_LABELS = {
  akademik:  'Akademik',
  sinik:     'Sinik',
  iyimser:   'Iyimser',
  sert:      'Sert',
  pragmatik: 'Pragmatik',
};

/* ── State ── */
let models         = [];
let experts        = [];
let stepElements   = {};
let completedSteps = 0;
let es             = null;
let debateRoles    = [];

/* ── DOM helper ── */
const $ = id => document.getElementById(id);

/* ── Escape HTML ── */
function esc(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Panel list ── */
const ALL_PANELS = ['panelSetup','panelExperts','panelDebate','panelVerdict'];
const PANEL_STEP = { panelSetup:1, panelExperts:2, panelDebate:3, panelVerdict:4 };

/* ── Step nav highlight ── */
function setStep(num) {
  document.querySelectorAll('.step').forEach(el => {
    const s    = parseInt(el.dataset.s, 10);
    const nEl  = el.querySelector('.step-n');
    el.classList.toggle('active', s === num);
    el.classList.toggle('done',   s < num);
    if (nEl) {
      if (s < num) {
        nEl.innerHTML = `<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5"><polyline points="20 6 9 17 4 12"/></svg>`;
      } else {
        nEl.textContent = s;
      }
    }
  });
}

/* ── Status dot ── */
function setStatus(state, text) {
  $('statusDot').className    = 'status-dot ' + state;
  $('statusText').textContent = text;
}

/* ── Show panel ── */
function showPanel(id) {
  ALL_PANELS.forEach(pid => {
    const el = $(pid);
    if (el) el.classList.toggle('hidden', pid !== id);
  });
  /* Sidebar active */
  document.querySelectorAll('.sidebar-item').forEach(item => {
    item.classList.toggle('active', item.dataset.panel === id);
  });
  setStep(PANEL_STEP[id] || 1);
  setTimeout(() => {
    const el = $(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 80);
}

/* ── Fill select ── */
function fillSelect(id, list) {
  const el = $(id);
  if (!el) return;
  el.innerHTML = list.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('');
}

/* ── Toast ── */
function toast(msg, type = '') {
  const box = document.createElement('div');
  box.className = 'toast ' + type;
  box.textContent = msg;
  $('toastContainer').appendChild(box);
  setTimeout(() => box.remove(), 4500);
}

/* ── Sidebar navigation ── */
document.querySelectorAll('.sidebar-item[data-panel]').forEach(item => {
  item.addEventListener('click', () => {
    const target = item.dataset.panel;
    /* Only allow navigating to already-visited panels */
    if (!$(target).classList.contains('hidden') || target === 'panelSetup') {
      showPanel(target);
    }
  });
});

/* ── Init: fetch models ── */
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const res  = await fetch(API.models);
    if (!res.ok) throw new Error();
    const data = await res.json();
    models     = data.models;

    fillSelect('archModel',      models);
    fillSelect('presidentModel', models);
    fillSelect('courtModel',     models);

    $('sidebarModel').textContent = models[0] || '—';
    setStatus('online', `${models.length} model hazir`);
  } catch {
    setStatus('error', 'Ollama baglantisi yok');
    toast('Ollama servisine ulasilamadi. localhost:11434 calisiyor mu?', 'error');
  }
});

/* ── Generate experts ── */
$('btnGenerate').addEventListener('click', async () => {
  const model = $('archModel').value;
  const topic = $('topicInput').value.trim();
  if (!topic) { toast('Lutfen bir arastirma konusu girin.', 'error'); return; }

  const btn = $('btnGenerate');
  btn.disabled = true;
  btn.innerHTML = '<div class="spin"></div> Olusturuluyor…';

  try {
    const res  = await fetch(API.genExperts, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model, topic })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Sunucu hatasi');
    const data = await res.json();
    experts    = data.experts;

    $('sidebarModel').textContent = model;
    $('sidebarTopic').textContent = topic.length > 22 ? topic.slice(0, 22) + '…' : topic;

    renderExperts(experts);
    showPanel('panelExperts');
    toast('Uzman komitesi olusturuldu!', 'success');
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = BTN_GENERATE_HTML;
  }
});

/* ── Render expert cards ── */
function renderExperts(list) {
  const grid = $('expertsGrid');
  grid.innerHTML = list.map((ex, i) => `
    <div class="expert-card">
      <div class="expert-num">UZMAN ${i + 1}</div>
      <div class="expert-role">${esc(ex.role || 'Uzman ' + (i+1))}</div>
      <div class="expert-goal">${esc(ex.goal || '')}</div>
      <div class="field" style="margin-top:.875rem">
        <label class="label">Model</label>
        <div class="select-wrap">
          <select id="eModel${i}" class="select">
            ${models.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('')}
          </select>
          <svg class="select-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
      </div>
      <div class="field" style="margin-top:.625rem">
        <label class="label">Kisilik</label>
        <div class="select-wrap">
          <select id="ePersonality${i}" class="select" onchange="updatePersonalityBadge(${i})">
            <option value="akademik">Akademik</option>
            <option value="sinik">Sinik</option>
            <option value="iyimser">Iyimser</option>
            <option value="sert">Sert</option>
            <option value="pragmatik">Pragmatik</option>
          </select>
          <svg class="select-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
        <span class="p-badge akademik" id="pBadge${i}">Akademik</span>
      </div>
    </div>
  `).join('');
}

/* ── Update personality badge on change ── */
function updatePersonalityBadge(i) {
  const sel   = $(`ePersonality${i}`);
  const badge = $(`pBadge${i}`);
  if (!sel || !badge) return;
  const val = sel.value;
  badge.className   = `p-badge ${val}`;
  badge.textContent = PERSONALITY_LABELS[val] || val;
}

/* ── Back button ── */
$('btnBack').addEventListener('click', () => {
  showPanel('panelSetup');
});

/* ── Launch debate ── */
$('btnLaunch').addEventListener('click', async () => {
  const topic = $('topicInput').value.trim();
  if (!topic) { toast('Arastirma konusu bos olamaz.', 'error'); return; }
  if (experts.length < 3) { toast('3 uzman gerekli. Lutfen tekrar olusturun.', 'error'); return; }

  const expertConfigs = experts.map((ex, i) => ({
    model:       $(`eModel${i}`).value,
    personality: $(`ePersonality${i}`)?.value || 'akademik',
    data:        ex
  }));

  debateRoles = expertConfigs.map((c, i) => c.data.role || `Uzman ${i+1}`);

  const devilAdvocate = $('devilAdvocate')?.checked || false;

  const btn = $('btnLaunch');
  btn.disabled = true;
  btn.innerHTML = '<div class="spin"></div> Baslatiliyor…';

  try {
    const res = await fetch(API.startDebate, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic,
        expert_configs:  expertConfigs,
        president_model: $('presidentModel').value,
        court_model:     $('courtModel').value,
        devil_advocate:  devilAdvocate
      })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Sunucu hatasi');
    const { session_id } = await res.json();

    completedSteps = 0;
    $('progressFill').style.width   = '0%';
    $('progressLabel').textContent  = `0 / ${TOTAL_STEPS}`;
    resetHeatBar();

    showPanel('panelDebate');
    setStatus('running', 'Tartisma aktif…');
    streamDebate(session_id);
  } catch (err) {
    toast(err.message, 'error');
    btn.disabled = false;
    btn.innerHTML = BTN_LAUNCH_HTML;
  }
});

/* ── Heat bar helpers ── */
function resetHeatBar() {
  const fill   = $('heatFill');
  const marker = $('heatMarker');
  if (fill)   { fill.style.width = '25%'; fill.style.background = 'var(--green)'; }
  if (marker) { marker.style.left = '25%'; marker.style.borderColor = 'var(--green)'; }
}

function updateHeatBar(pct) {
  const fill   = $('heatFill');
  const marker = $('heatMarker');
  if (!fill) return;

  fill.style.width = pct + '%';

  let color;
  if (pct < 40)      color = 'var(--green)';
  else if (pct < 65) color = 'var(--amber)';
  else               color = 'var(--red)';

  fill.style.background = color;

  if (marker) {
    marker.style.left        = pct + '%';
    marker.style.borderColor = color;
  }
}

/* ── SSE Stream ── */
function streamDebate(sessionId) {
  if (es) es.close();
  stepElements = {};
  $('timeline').innerHTML = '';

  es = new EventSource(API.stream(sessionId));

  es.onmessage = evt => {
    try { handleEvent(JSON.parse(evt.data)); }
    catch (e) { console.error('Parse error:', e); }
  };

  es.onerror = () => {
    es.close();
    setStatus('error', 'Baglanti kesildi');
    toast('SSE baglantisi kesildi.', 'error');
  };
}

/* ── Event handler ── */
function handleEvent(ev) {
  const tl = $('timeline');

  if (ev.type === 'step_start') {
    const el = makeTimelineItem(ev.step, ev.title);
    tl.appendChild(el);
    stepElements[ev.step] = el;
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    return;
  }

  if (ev.type === 'step_complete') {
    const el = stepElements[ev.step];
    if (!el) return;

    completedSteps++;
    const pct = (completedSteps / TOTAL_STEPS) * 100;
    $('progressFill').style.width  = pct + '%';
    $('progressLabel').textContent = `${completedSteps} / ${TOTAL_STEPS}`;

    if (ev.heat !== undefined) updateHeatBar(ev.heat);

    /* Dot: active -> done */
    const dot = el.querySelector('.tl-dot');
    if (dot) {
      dot.classList.remove('active');
      dot.classList.add('done');
      dot.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`;
    }

    /* Remove loading bar */
    el.querySelector('.tl-loader')?.remove();

    /* Append content */
    const content = document.createElement('div');
    content.className   = 'tl-content';
    content.textContent = ev.content;
    el.querySelector('.tl-body').appendChild(content);
    return;
  }

  if (ev.type === 'final_verdict') {
    es.close();
    setStatus('online', 'Tamamlandi');
    showPanel('panelVerdict');

    $('synthesisText').textContent = ev.synthesis;
    typeOut('verdictText', ev.content);
    drawArgMap();
    toast('Karar muhürlendi!', 'success');
    return;
  }

  if (ev.type === 'error') {
    es.close();
    setStatus('error', 'Hata olustu');
    const err = document.createElement('div');
    err.className   = 'error-banner';
    err.textContent = 'Hata: ' + ev.message;
    tl.appendChild(err);
    toast(ev.message, 'error');

    const btn = $('btnLaunch');
    btn.disabled = false;
    btn.innerHTML = BTN_LAUNCH_HTML;
    return;
  }

  if (ev.type === 'done') {
    es.close();
  }
}

/* ── Build timeline item ── */
function makeTimelineItem(step, title) {
  const cfg   = STEP_CONFIG[step - 1] || { color: 'blue', agent: 'AGENT', title: 'Adim' };
  const color = cfg.color;
  const label = title || cfg.title;

  const el = document.createElement('div');
  el.className = 'tl-item';

  el.innerHTML = `
    <div class="tl-left">
      <div class="tl-dot active"></div>
      <div class="tl-line"></div>
    </div>
    <div class="tl-body">
      <div class="tl-header">
        <span class="tl-tag t-${color}">${esc(cfg.agent)}</span>
        <span class="tl-title">${esc(label)}</span>
        <div class="tl-loader"><span></span><span></span><span></span></div>
      </div>
    </div>
  `;
  return el;
}

/* ── Typewriter ── */
function typeOut(id, text, speed = 10) {
  const el = $(id);
  el.textContent = '';
  let i = 0;
  (function tick() {
    if (i < text.length) {
      el.textContent += text[i++];
      setTimeout(tick, speed);
    }
  })();
}

/* ── Argument Map ── */
function drawArgMap() {
  const svg = $('argMap');
  if (!svg) return;

  const W = svg.clientWidth || 680;
  const H = 260;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = '';

  const ns = 'http://www.w3.org/2000/svg';

  const r1 = debateRoles[0] || 'Uzman I';
  const r2 = debateRoles[1] || 'Uzman II';
  const r3 = debateRoles[2] || 'Uzman III';

  const nodes = [
    { id: 'e1',    cx: W * 0.14, cy: H * 0.55, color: '#7a4f2e', label: truncate(r1, 13) },
    { id: 'e2',    cx: W * 0.52, cy: H * 0.55, color: '#7a3a5e', label: truncate(r2, 13) },
    { id: 'e3',    cx: W * 0.33, cy: H * 0.88, color: '#a0602e', label: truncate(r3, 13) },
    { id: 'pres',  cx: W * 0.70, cy: H * 0.24, color: '#4a6741', label: 'Sentezleyici'   },
    { id: 'court', cx: W * 0.90, cy: H * 0.55, color: '#b8782a', label: 'Yuk. Mahkeme'   },
  ];

  const edges = [
    { from: 'e1',   to: 'e2',    label: 'itiraz'   },
    { from: 'e2',   to: 'e1',    label: 'curutme'  },
    { from: 'e1',   to: 'e3',    label: 'savunma'  },
    { from: 'e3',   to: 'pres',  label: 'hakem'    },
    { from: 'pres', to: 'court', label: 'sentez'   },
  ];

  const nodeMap = {};
  nodes.forEach(n => { nodeMap[n.id] = n; });

  /* Defs (arrowheads) */
  const defs = document.createElementNS(ns, 'defs');
  nodes.forEach(n => {
    const marker = document.createElementNS(ns, 'marker');
    marker.setAttribute('id',          `arr-${n.id}`);
    marker.setAttribute('markerWidth',  '7');
    marker.setAttribute('markerHeight', '7');
    marker.setAttribute('refX',         '6');
    marker.setAttribute('refY',         '3');
    marker.setAttribute('orient',       'auto');
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d',       'M0,0 L0,6 L7,3 z');
    path.setAttribute('fill',    n.color);
    path.setAttribute('opacity', '0.6');
    marker.appendChild(path);
    defs.appendChild(marker);
  });
  svg.appendChild(defs);

  /* Draw edges */
  const nodeR = 22;
  edges.forEach(edge => {
    const src = nodeMap[edge.from];
    const dst = nodeMap[edge.to];
    if (!src || !dst) return;

    const dx = dst.cx - src.cx;
    const dy = dst.cy - src.cy;
    const dist = Math.sqrt(dx*dx + dy*dy);
    const nx = dx / dist;
    const ny = dy / dist;

    const x1 = src.cx + nx * nodeR;
    const y1 = src.cy + ny * nodeR;
    const x2 = dst.cx - nx * (nodeR + 4);
    const y2 = dst.cy - ny * (nodeR + 4);

    const mx = (x1 + x2) / 2 - ny * 18;
    const my = (y1 + y2) / 2 + nx * 18;

    const line = document.createElementNS(ns, 'path');
    line.setAttribute('d',               `M ${x1},${y1} Q ${mx},${my} ${x2},${y2}`);
    line.setAttribute('stroke',          src.color);
    line.setAttribute('stroke-opacity',  '0.4');
    line.setAttribute('stroke-width',    '1.5');
    line.setAttribute('fill',            'none');
    line.setAttribute('marker-end',      `url(#arr-${src.id})`);
    svg.appendChild(line);

    const lx  = (x1 + x2) / 2 - ny * 18;
    const ly  = (y1 + y2) / 2 + nx * 18 - 5;
    const lbl = document.createElementNS(ns, 'text');
    lbl.setAttribute('x',           lx);
    lbl.setAttribute('y',           ly);
    lbl.setAttribute('text-anchor', 'middle');
    lbl.setAttribute('font-size',   '8');
    lbl.setAttribute('font-family', 'JetBrains Mono, monospace');
    lbl.setAttribute('fill',        src.color);
    lbl.setAttribute('opacity',     '0.55');
    lbl.textContent = edge.label;
    svg.appendChild(lbl);
  });

  /* Draw nodes */
  nodes.forEach(n => {
    const g = document.createElementNS(ns, 'g');
    g.setAttribute('transform', `translate(${n.cx},${n.cy})`);

    const circle = document.createElementNS(ns, 'circle');
    circle.setAttribute('r',              nodeR.toString());
    circle.setAttribute('fill',           '#faf6ef');
    circle.setAttribute('stroke',         n.color);
    circle.setAttribute('stroke-width',   '1.5');
    g.appendChild(circle);

    const lbl = document.createElementNS(ns, 'text');
    lbl.setAttribute('text-anchor', 'middle');
    lbl.setAttribute('y',           (nodeR + 12).toString());
    lbl.setAttribute('font-size',   '8.5');
    lbl.setAttribute('font-family', 'Inter, sans-serif');
    lbl.setAttribute('font-weight', '600');
    lbl.setAttribute('fill',        n.color);
    lbl.textContent = n.label;
    g.appendChild(lbl);

    svg.appendChild(g);
  });
}

function truncate(str, max) {
  return str.length > max ? str.slice(0, max - 1) + '…' : str;
}

/* ── Generate Markdown ── */
function generateMarkdown() {
  let md = `# AVARIA — Arastirma Raporu\n\n`;
  md += `**Konu:** ${$('topicInput').value}\n`;
  md += `**Tarih:** ${new Date().toLocaleDateString('tr-TR')}\n\n---\n\n`;

  document.querySelectorAll('.tl-item').forEach(item => {
    const title   = item.querySelector('.tl-title')?.textContent   || '';
    const content = item.querySelector('.tl-content')?.textContent || '';
    if (content) md += `## ${title}\n\n${content}\n\n---\n\n`;
  });

  const verdict = $('verdictText')?.textContent;
  if (verdict) md += `## Nihai Karar\n\n${verdict}\n`;

  return md;
}

/* ── Export button ── */
$('btnExportMd').addEventListener('click', () => {
  const md   = generateMarkdown();
  const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  const topic = ($('topicInput').value || 'avaria').replace(/\s+/g, '_').slice(0, 40);
  a.href     = url;
  a.download = `avaria_${topic}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast('Markdown dosyasi indirildi.', 'success');
});

/* ── Copy button ── */
$('btnCopy').addEventListener('click', async () => {
  const md = generateMarkdown();
  try {
    await navigator.clipboard.writeText(md);
    toast('Panoya kopyalandi!', 'success');
  } catch {
    toast('Kopyalama basarisiz.', 'error');
  }
});

/* ── Reset ── */
$('btnReset').addEventListener('click', () => {
  if (es) es.close();
  experts        = [];
  stepElements   = {};
  completedSteps = 0;
  debateRoles    = [];

  $('topicInput').value          = '';
  $('timeline').innerHTML        = '';
  $('synthesisText').textContent = '';
  $('verdictText').textContent   = '';
  $('progressFill').style.width  = '0%';
  $('progressLabel').textContent = `0 / ${TOTAL_STEPS}`;
  $('sidebarTopic').textContent  = '—';

  const argMap = $('argMap');
  if (argMap) argMap.innerHTML = '';

  resetHeatBar();
  showPanel('panelSetup');
  setStatus('online', `${models.length} model hazir`);
  window.scrollTo({ top: 0, behavior: 'smooth' });
  toast('Yeni arastirma hazir.', 'success');

  const btn = $('btnLaunch');
  btn.disabled = false;
  btn.innerHTML = BTN_LAUNCH_HTML;
});
