/* 全栈数据分析平台 · 前端公共库 */
const C = (() => {
  const palette = ['#22d3ee', '#8b5cf6', '#f59e0b', '#34d399', '#fb7185', '#60a5fa', '#a3e635', '#f472b6'];
  const charts = [];

  const fmt = (n, d = 0) => {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
    return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d });
  };
  const pct = (n, d = 1) => (n === null || n === undefined || Number.isNaN(Number(n))) ? '—' : `${Number(n).toFixed(d)}%`;
  const money = (n) => (n === null || n === undefined) ? '—' : `¥${fmt(n)}`;
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  async function get(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url} 请求失败（HTTP ${r.status}）`);
    return r.json();
  }

  const el = (id) => document.getElementById(id);

  function kpis(items) {
    return `<div class="kpi-grid">${items.map(x => `
      <div class="kpi">
        <div class="value">${x.value}</div>
        <div class="label">${x.label}</div>
        ${x.sub ? `<div class="sub">${x.sub}</div>` : ''}
      </div>`).join('')}</div>`;
  }

  function panel(title, desc, body, cls = '') {
    return `<section class="panel ${cls}">
      <div class="panel-head"><div><h2>${title}</h2>${desc ? `<p>${desc}</p>` : ''}</div></div>
      ${body}
    </section>`;
  }

  const chartBox = (id, cls = '') => `<div id="${id}" class="chart ${cls}"></div>`;

  function table(headers, rows, opts = {}) {
    const head = headers.map((h, i) => `<th class="${i > 0 ? 'num' : ''}">${h}</th>`).join('');
    const body = rows.map(r => `<tr>${r.map((c, i) => `<td class="${i > 0 ? 'num' : ''}">${c}</td>`).join('')}</tr>`).join('');
    return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>
      ${opts.note ? `<div class="table-note">${opts.note}</div>` : ''}`;
  }

  function chart(id, option) {
    const node = el(id);
    if (!node || typeof echarts === 'undefined') return null;
    const c = echarts.init(node);
    const base = {
      color: palette,
      animationDuration: 650,
      animationEasing: 'cubicOut',
      textStyle: { fontFamily: 'Inter, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif', color: '#cbd5e1' },
      legend: { textStyle: { color: '#94a3b8', fontSize: 11 }, top: 4, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
      grid: { left: 18, right: 26, top: 46, bottom: 10, containLabel: true },
      tooltip: {
        backgroundColor: 'rgba(10,16,30,.96)',
        borderColor: 'rgba(148,163,184,.25)',
        borderWidth: 1,
        textStyle: { color: '#e2e8f0', fontSize: 12 },
        extraCssText: 'backdrop-filter: blur(8px); border-radius: 8px;'
      }
    };
    const merged = Object.assign({}, base, option);
    merged.tooltip = Object.assign({ trigger: 'axis' }, base.tooltip, option.tooltip || {});
    merged.grid = Object.assign({}, base.grid, option.grid || {});
    c.setOption(merged);
    charts.push(c);
    if (window.ResizeObserver) {
      const ro = new ResizeObserver(() => c.resize());
      ro.observe(node);
    }
    return c;
  }

  const axis = (extra = {}) => Object.assign({
    axisLine: { lineStyle: { color: 'rgba(148,163,184,.25)' } },
    axisTick: { show: false },
    axisLabel: { color: '#94a3b8', fontSize: 11 },
    splitLine: { lineStyle: { color: 'rgba(148,163,184,.08)', type: 'dashed' } }
  }, extra);

  const catAxis = (data, extra = {}) => Object.assign({
    type: 'category',
    data,
    axisLine: { lineStyle: { color: 'rgba(148,163,184,.25)' } },
    axisTick: { show: false },
    axisLabel: { color: '#94a3b8', fontSize: 11 },
    splitLine: { show: false }
  }, extra);

  const valAxis = (extra = {}) => Object.assign({
    type: 'value',
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#94a3b8', fontSize: 11 },
    splitLine: { lineStyle: { color: 'rgba(148,163,184,.08)', type: 'dashed' } }
  }, extra);

  function insights(list) {
    return `<div class="insights">${list.map((x, i) => `
      <div class="insight-item"><span class="num">${String(i + 1).padStart(2, '0')}</span><p>${x}</p></div>
    `).join('')}</div>`;
  }

  function notes(list) {
    return `<details class="notes"><summary>数据口径与已知限制</summary>
      <ul>${list.map(x => `<li>${x}</li>`).join('')}</ul>
    </details>`;
  }

  function error(node, err) {
    if (!node) return;
    node.innerHTML = `<div class="error-box"><b>加载失败。</b> ${esc(err && err.message ? err.message : err)}<br>
      请确认后端已启动：<code>python app.py</code>，并检查该模块的数据文件是否存在。</div>`;
  }

  function loading(node, text = '正在计算分析结果…') {
    if (node) node.innerHTML = `<div class="loading"><span class="spinner"></span>${text}</div>`;
  }

  function tag(text, cls = '') { return `<span class="tag ${cls}">${text}</span>`; }

  function gradient(color, vertical = true) {
    return new echarts.graphic.LinearGradient(0, 0, vertical ? 0 : 1, vertical ? 1 : 0, [
      { offset: 0, color: color + 'ee' },
      { offset: 1, color: color + '55' }
    ]);
  }

  window.addEventListener('resize', () => charts.forEach(c => { try { c.resize(); } catch (e) {} }));

  return { palette, fmt, pct, money, esc, get, el, kpis, panel, chartBox, table, chart,
           axis, catAxis, valAxis, insights, notes, error, loading, tag, gradient, charts };
})();
