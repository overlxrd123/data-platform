/* 用户留存模块 */
(async function () {
  const app = document.getElementById('app');
  C.loading(app, '正在构建 53 个注册周队列与留存矩阵…');
  try {
    const d = await C.get('/api/retention');
    const o = d.overview;
    const weeks = d.average_curve.map((_, i) => `W${i}`);

    const val = (x, i) => (x.values && x.values[i] != null) ? x.values[i] : null;
    const channelRows = d.channels.map(x => [
      x.name, C.fmt(x.users), C.pct(x.share_pct),
      C.pct(val(x, 1)), C.pct(val(x, 4)), C.pct(val(x, 8))
    ]);
    const deviceRows = d.devices.map(x => [
      x.name, C.fmt(x.users), C.pct(x.share_pct),
      C.pct(val(x, 1)), C.pct(val(x, 4)), C.pct(val(x, 8))
    ]);

    app.innerHTML = `
      <div class="page-head">
        <div class="eyebrow">Module 03 · Retention</div>
        <h1>用户留存：不要看平均值，要看队列</h1>
        <p>20,301 名模拟 App 用户、53 个注册周队列、8 周观察窗口。整体 W1 留存 50.9%、W4 23.9%，首周流失 49.1%——留存曲线在前 7 天最陡，之后的优化空间小得多。</p>
      </div>

      ${C.kpis([
        { value: C.fmt(o.users), label: '注册用户', sub: `${o.cohorts} 个注册周 · ${o.days} 天` },
        { value: C.pct(o.w1_retention), label: 'W1 留存', sub: `首周流失 ${C.pct(o.first_week_churn)}` },
        { value: C.pct(o.w4_retention), label: 'W4 留存', sub: `W8 ${C.pct(o.w8_retention)}` },
        { value: C.pct(o.cohort_w4_early) + ' → ' + C.pct(o.cohort_w4_late), label: 'W4 留存：早期 vs 近期队列', sub: `前 8 / 后 8 个完整队列，+${(o.cohort_w4_late - o.cohort_w4_early).toFixed(1)}pp` },
        { value: C.fmt(o.avg_daily_signups, 1), label: '日均注册', sub: `观测至 ${o.observed_until}` }
      ])}

      <div class="grid-2">
        ${C.panel('整体留存曲线', 'W0 为注册当周（100%），W1 跌到 50.9%，W4 后曲线趋缓。留存分析的核心是前 4 周，而不是第 8 周之后的微小差异。', C.chartBox('avgCurve', 'lg'))}
        ${C.panel('每周条件流失率', 'W1 流失 49.1%，之后单周流失率快速下降；这说明拉新后的首周体验决定了绝大部分留存。', C.chartBox('hazardChart', 'lg'))}
      </div>

      ${C.panel('队列留存矩阵', '每一行是一个注册周队列，每一列是注册后第 N 周仍活跃的比例。颜色越亮留存越高；横向变暗是自然衰减，纵向对比能看出口径变化。', C.chartBox('cohortHeat', 'xl'), 'wide')}

      <div class="grid-2">
        ${C.panel('渠道：规模与质量错位', `自然流量占 ${C.pct(d.channels[0].share_pct)}，W4 留存 ${C.pct(val(d.channels[0], 4))}；广告投放占 ${C.pct(d.channels[2].share_pct)}，W4 只有 ${C.pct(val(d.channels[2], 4))}。`, C.chartBox('channelChart', 'lg') + C.table(['渠道', '用户数', '占比', 'W1', 'W4', 'W8'], channelRows, { note: 'W1/W4/W8 为该渠道所有队列的加权平均留存。' }))}
        ${C.panel('设备：iOS 略高，但差距不大', `iOS W4 留存 ${C.pct(val(d.devices[0], 4))}，Android ${C.pct(val(d.devices[1], 4))}，相差 ${(val(d.devices[0], 4) - val(d.devices[1], 4)).toFixed(1)} 个百分点。`, C.chartBox('deviceChart', 'lg') + C.table(['设备', '用户数', '占比', 'W1', 'W4', 'W8'], deviceRows, { note: '设备差异远小于渠道差异，优先级应放在渠道质量而不是客户端。' }))}
      </div>

      ${C.panel('队列 W4 留存趋势', '把每个队列的 W4 留存单独画出来：早期队列约 21%，近期队列约 25%，说明产品/渠道质量在模拟期内有缓慢改善；但单周波动仍然存在。', C.chartBox('trendChart'), 'wide')}

      ${C.panel('结论', '队列口径能区分「整体变好」和「新用户变好」，这是留存分析最重要的分界线。', C.insights(d.insights) + C.notes(d.data_notes))}
    `;

    // 平均留存曲线
    C.chart('avgCurve', {
      grid: { left: 18, right: 26, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>留存率：<b>${p[0].value}%</b>` },
      xAxis: C.catAxis(weeks, { boundaryGap: false }),
      yAxis: C.valAxis({ min: 0, max: 100, axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: [{
        type: 'line', data: d.average_curve, smooth: true, symbolSize: 8,
        lineStyle: { width: 3, color: '#22d3ee' },
        itemStyle: { color: '#22d3ee' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(34,211,238,.3)' }, { offset: 1, color: 'rgba(34,211,238,0)' }
        ]) },
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: '{c}%' }
      }]
    });

    // 条件流失
    C.chart('hazardChart', {
      grid: { left: 18, right: 20, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `第 ${p[0].axisValue} 周<br/>条件流失率：<b>${p[0].value}%</b>` },
      xAxis: C.catAxis(d.hazard.map(x => `W${x.week}`)),
      yAxis: C.valAxis({ axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: [{
        type: 'bar', data: d.hazard.map(x => x.churn_pct), barWidth: '52%',
        itemStyle: { borderRadius: [5, 5, 0, 0], color: p => p.dataIndex === 0 ? '#fb7185' : C.gradient('#8b5cf6') },
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: '{c}%' }
      }]
    });

    // 队列热力图
    const heat = [];
    d.cohorts.forEach((c, y) => c.values.forEach((v, x) => heat.push([x, y, v])));
    C.chart('cohortHeat', {
      grid: { left: 70, right: 24, top: 10, bottom: 76 },
      tooltip: {
        formatter: p => {
          const c = d.cohorts[p.data[1]];
          return `<b>${c.cohort}</b>（${c.start} 注册，${C.fmt(c.size)} 人）<br/>W${p.data[0]} 留存：<b>${p.data[2]}%</b>`;
        }
      },
      xAxis: C.catAxis(weeks, { splitArea: { show: false } }),
      yAxis: {
        type: 'category', data: d.cohorts.map(c => c.cohort), inverse: true,
        axisLine: { lineStyle: { color: 'rgba(148,163,184,.25)' } },
        axisTick: { show: false },
        axisLabel: { color: '#64748b', fontSize: 9, interval: 3 },
        splitLine: { show: false }
      },
      visualMap: {
        min: 0, max: 60, calculable: false, orient: 'horizontal',
        left: 'center', bottom: 12,
        text: ['高', '低'], textStyle: { color: '#94a3b8', fontSize: 10 },
        inRange: { color: ['#0b1220', '#134e4a', '#0e7490', '#22d3ee', '#a5f3fc'] }
      },
      series: [{
        type: 'heatmap', data: heat,
        itemStyle: { borderColor: 'rgba(6,10,19,.6)', borderWidth: 1 },
        emphasis: { itemStyle: { borderColor: '#f8fafc', borderWidth: 1 } }
      }]
    });

    // 渠道曲线
    C.chart('channelChart', {
      grid: { left: 18, right: 24, top: 38, bottom: 10, containLabel: true },
      tooltip: { trigger: 'axis', valueFormatter: v => v + '%' },
      legend: { top: 2 },
      xAxis: C.catAxis(weeks, { boundaryGap: false }),
      yAxis: C.valAxis({ axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: d.channels.map((x, i) => ({
        name: x.name, type: 'line', smooth: true, symbol: 'none',
        lineStyle: { width: 3, color: C.palette[i] },
        itemStyle: { color: C.palette[i] },
        data: x.values
      }))
    });

    // 设备曲线
    C.chart('deviceChart', {
      grid: { left: 18, right: 24, top: 38, bottom: 10, containLabel: true },
      tooltip: { trigger: 'axis', valueFormatter: v => v + '%' },
      legend: { top: 2 },
      xAxis: C.catAxis(weeks, { boundaryGap: false }),
      yAxis: C.valAxis({ axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: d.devices.map((x, i) => ({
        name: x.name, type: 'line', smooth: true, symbol: 'none',
        lineStyle: { width: 3, color: C.palette[i] },
        itemStyle: { color: C.palette[i] },
        data: x.values
      }))
    });

    // 队列趋势
    C.chart('trendChart', {
      grid: { left: 18, right: 26, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>W4 留存：<b>${p[0].value}%</b>` },
      xAxis: C.catAxis(d.cohort_trend.map(x => x.cohort), { axisLabel: { color: '#64748b', fontSize: 9, interval: 5 } }),
      yAxis: C.valAxis({ min: 0, max: 40, axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: [{
        type: 'line', data: d.cohort_trend.map(x => x.w4), smooth: true, symbolSize: 4,
        lineStyle: { width: 2, color: '#f59e0b' },
        itemStyle: { color: '#f59e0b' },
        areaStyle: { color: 'rgba(245,158,11,.1)' },
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { color: 'rgba(148,163,184,.5)', type: 'dashed' },
          label: { color: '#94a3b8', fontSize: 10, formatter: '整体 W4 23.9%' },
          data: [{ yAxis: o.w4_retention }]
        }
      }]
    });
  } catch (e) {
    C.error(app, e);
  }
})();
