/* 数据岗招聘模块 */
(async function () {
  const app = document.getElementById('app');
  C.loading(app, '正在解析 3,523 条薪资字符串并分类岗位族…');
  try {
    const d = await C.get('/api/jobs');
    const o = d.overview;

    const cityRows = d.city_controlled.map(x => [
      x.city, C.fmt(x.all_n), C.money(x.all_median) + '/月',
      C.money(x.da_median) + '/月',
      x.da_mid_median == null ? '样本不足' : C.money(x.da_mid_median) + '/月',
      C.fmt(x.da_mid_n)
    ]);

    const expRows = d.experience.map(x => [
      x.group, C.fmt(x.count), C.money(x.monthly_median),
      `${C.money(x.monthly_p25)}–${C.money(x.monthly_p75)}`, C.money(x.annual_median)
    ]);

    const eduRows = d.education.map(x => [
      x.group, C.fmt(x.count), C.money(x.monthly_median),
      `${C.money(x.monthly_p25)}–${C.money(x.monthly_p75)}`
    ]);

    const sizeRows = d.company_size.map(x => [
      x.group, C.fmt(x.count), C.money(x.monthly_median), C.money(x.annual_median)
    ]);

    const typeRows = d.company_type.map(x => [
      x.group, C.fmt(x.count), C.money(x.monthly_median)
    ]);

    const familyRows = d.families.map(x => [
      x.family, C.fmt(x.count), C.pct(x.share_pct), C.money(x.monthly_median),
      `${C.money(x.monthly_p25)}–${C.money(x.monthly_p75)}`
    ]);

    const famChart = [...d.families].filter(x => x.family !== '非数据/其他')
      .sort((a, b) => a.monthly_median - b.monthly_median);

    app.innerHTML = `
      <div class="page-head">
        <div class="eyebrow">Module 06 · Data Jobs</div>
        <h1>数据岗招聘：先把薪资字符串和「伪数据岗」拆干净</h1>
        <p>3,523 条岗位，薪资字段是「1.2-1.8万·14薪」「20-35万/年」这类混合格式，解析成功 98.9%。按岗位名称分类后只有 50.1% 真正与数据相关——另外一半是销售、质量、结构工程师等关键词噪声。清洗前后，薪资结论完全不同。</p>
      </div>

      ${C.kpis([
        { value: C.fmt(o.postings), label: '岗位数', sub: `${C.fmt(o.companies)} 家公司 · ${o.cities} 个城市` },
        { value: C.pct(o.salary_parsed_pct), label: '薪资解析成功率', sub: `${C.fmt(o.salary_parsed)} / ${C.fmt(o.postings)} 条` },
        { value: C.money(o.monthly_median), label: '月薪中位数', sub: `P25 ${C.money(o.monthly_p25)} · P75 ${C.money(o.monthly_p75)}` },
        { value: C.money(o.annual_median), label: '年包中位数', sub: `${C.pct(o.multi_month_share_pct)} 岗位标注 13 薪+` },
        { value: C.pct(o.data_job_share_pct), label: '真实数据岗占比', sub: `TOP3 城市占 ${C.pct(o.top3_city_share_pct)}` }
      ])}

      ${C.panel('城市：控制岗位与经验后再比较', '北京全样本中位 19,500 元，看起来明显高于其他城市；但城市之间岗位结构不同。限定「数据分析」岗、再限定 2–4 年经验后，北京仍然最高，且与上海的差距从 30% 扩大到 33%——说明北京的高薪不只是高薪岗位占比高。', C.chartBox('cityChart', 'lg') + C.table(['城市', '全部岗位', '全样本中位', '数据分析岗中位', '数据分析 2–4 年', '样本数'], cityRows, { note: '「数据分析 2–4 年」样本少于 10 条的显示为样本不足；分组比较必须同时控制岗位族与经验，否则会混入结构效应。' }))}

      <div class="grid-2">
        ${C.panel('经验与月薪', '1 年 11,000 → 3–4 年 16,000 → 5–7 年 20,000 → 8–9 年 30,000。3–4 年是招聘量最大的经验段，也是早期最明显的一次跃迁。', C.chartBox('expChart', 'lg') + C.table(['经验', '岗位数', '月薪中位', 'P25–P75', '年包中位'], expRows, { note: '「无需经验」中位 12,000 反而高于 1 年的 11,000——不是经验倒挂，而是无经验岗位中混入了算法/开发等高薪校招岗。' }))}
        ${C.panel('学历与月薪', '大专 11,000、本科 15,000、硕士 19,500；本科到硕士溢价约 30%，但硕士岗位数量只有本科的 3%。', C.chartBox('eduChart', 'lg') + C.table(['学历', '岗位数', '月薪中位', 'P25–P75'], eduRows))}
      </div>

      ${C.panel('岗位族：数量最多的，薪资最低', '算法 25,000 > BI/商业分析 20,000 > 数据开发 19,000 > 数据分析 12,500。数据分析岗数量最多，供给最饱和；往「分析 + 工程」或「分析 + 算法」走才有溢价。', C.chartBox('familyChart', 'lg') + C.table(['岗位族', '岗位数', '占比', '月薪中位', 'P25–P75'], familyRows, { note: '岗位族按岗位名称关键词分类；没有 JD 文本，无法分析技能词频与技能溢价。' }))}

      <div class="grid-2">
        ${C.panel('公司规模与月薪', '10000 人以上 20,000 元，少于 50 人 11,000 元，相差 82%；大公司溢价稳定存在。', C.chartBox('sizeChart') + C.table(['公司规模', '岗位数', '月薪中位', '年包中位'], sizeRows))}
        ${C.panel('公司性质与月薪', '不同性质公司的薪资差异小于规模差异；民营/上市公司样本最多。', C.chartBox('typeChart') + C.table(['公司性质', '岗位数', '月薪中位'], typeRows))}
      </div>

      <div class="grid-2">
        ${C.panel('发薪月数', `${C.pct(o.multi_month_share_pct)} 的岗位写了 13 薪及以上；「月薪 × 12」会系统性低估年包。`, C.chartBox('monthChart'))}
        ${C.panel('发布时间：抓取伪影，不做趋势', `${C.pct(o.top_date_share_pct)} 的岗位发布时间都是 ${o.top_date}——这是抓取时间，不是真实发布时间。下面这张图用来说明「为什么这个时间字段不可用」。`, C.chartBox('dailyChart'))}
      </div>

      ${C.panel('结论', '每一条都经过薪资口径统一与岗位去噪。', C.insights(d.insights) + C.notes(d.data_notes))}
    `;

    // 城市
    const controlled = d.city_controlled.filter(x => x.da_mid_median != null);
    C.chart('cityChart', {
      grid: { left: 18, right: 24, top: 40, bottom: 10, containLabel: true },
      legend: { top: 4 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: v => v == null ? '—' : '¥' + C.fmt(v) },
      xAxis: C.catAxis(controlled.map(x => x.city)),
      yAxis: C.valAxis({ name: '元/月' }),
      series: [
        { name: '全样本', type: 'bar', barWidth: '24%', itemStyle: { borderRadius: [4, 4, 0, 0], color: 'rgba(100,116,139,.75)' }, data: controlled.map(x => x.all_median) },
        { name: '数据分析岗', type: 'bar', barWidth: '24%', itemStyle: { borderRadius: [4, 4, 0, 0], color: 'rgba(34,211,238,.75)' }, data: controlled.map(x => x.da_median) },
        { name: '数据分析 2–4 年', type: 'bar', barWidth: '24%', itemStyle: { borderRadius: [4, 4, 0, 0], color: 'rgba(139,92,246,.85)' }, data: controlled.map(x => x.da_mid_median) }
      ]
    });

    // 经验
    C.chart('expChart', {
      grid: { left: 18, right: 28, top: 38, bottom: 10, containLabel: true },
      legend: { top: 2 },
      tooltip: { trigger: 'axis' },
      xAxis: C.catAxis(d.experience.map(x => x.group)),
      yAxis: [
        C.valAxis({ name: '元/月' }),
        C.valAxis({ name: '岗位数', splitLine: { show: false }, axisLabel: { color: '#94a3b8', fontSize: 10 } })
      ],
      series: [
        { name: '月薪中位', type: 'bar', barWidth: '44%', itemStyle: { borderRadius: [5, 5, 0, 0], color: C.gradient('#22d3ee') }, data: d.experience.map(x => x.monthly_median), label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: p => C.fmt(p.value) } },
        { name: '岗位数', type: 'line', yAxisIndex: 1, symbolSize: 6, lineStyle: { width: 2.5, color: '#f59e0b' }, itemStyle: { color: '#f59e0b' }, data: d.experience.map(x => x.count) }
      ]
    });

    // 学历
    C.chart('eduChart', {
      grid: { left: 18, right: 24, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>月薪中位：<b>¥${C.fmt(p[0].value)}</b><br/>岗位：${C.fmt(d.education[p[0].dataIndex].count)}` },
      xAxis: C.catAxis(d.education.map(x => x.group)),
      yAxis: C.valAxis({ name: '元/月' }),
      series: [{
        type: 'bar', data: d.education.map(x => x.monthly_median), barWidth: '46%',
        itemStyle: { borderRadius: [5, 5, 0, 0], color: C.gradient('#8b5cf6') },
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: p => C.fmt(p.value) }
      }]
    });

    // 岗位族
    C.chart('familyChart', {
      grid: { left: 8, right: 60, top: 12, bottom: 8, containLabel: true },
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: p => {
          const x = famChart[p[0].dataIndex];
          return `<b>${x.family}</b><br/>月薪中位：¥${C.fmt(x.monthly_median)}<br/>岗位数：${C.fmt(x.count)}（${x.share_pct}%）<br/>P25–P75：¥${C.fmt(x.monthly_p25)}–${C.fmt(x.monthly_p75)}`;
        }
      },
      xAxis: C.valAxis({ name: '元/月' }),
      yAxis: C.catAxis(famChart.map(x => x.family), { axisLabel: { color: '#cbd5e1', fontSize: 11 } }),
      series: [{
        type: 'bar', data: famChart.map(x => x.monthly_median), barWidth: '60%',
        itemStyle: { borderRadius: [0, 6, 6, 0], color: p => p.dataIndex >= famChart.length - 2 ? '#f59e0b' : C.gradient('#8b5cf6', false) },
        label: { show: true, position: 'right', color: '#94a3b8', fontSize: 10, formatter: p => '¥' + C.fmt(p.value) }
      }]
    });

    // 公司规模
    C.chart('sizeChart', {
      grid: { left: 18, right: 20, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>月薪中位：<b>¥${C.fmt(p[0].value)}</b><br/>岗位：${C.fmt(d.company_size[p[0].dataIndex].count)}` },
      xAxis: C.catAxis(d.company_size.map(x => x.group), { axisLabel: { color: '#94a3b8', fontSize: 9, interval: 0, rotate: 24 } }),
      yAxis: C.valAxis({ name: '元/月' }),
      series: [{
        type: 'bar', data: d.company_size.map(x => x.monthly_median), barWidth: '48%',
        itemStyle: { borderRadius: [5, 5, 0, 0], color: C.gradient('#22d3ee') },
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 9, formatter: p => C.fmt(p.value) }
      }]
    });

    // 公司性质
    const types = [...d.company_type].sort((a, b) => a.monthly_median - b.monthly_median);
    C.chart('typeChart', {
      grid: { left: 8, right: 54, top: 12, bottom: 8, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>月薪中位：<b>¥${C.fmt(p[0].value)}</b><br/>岗位：${C.fmt(types[p[0].dataIndex].count)}` },
      xAxis: C.valAxis({ name: '元/月' }),
      yAxis: C.catAxis(types.map(x => x.group), { axisLabel: { color: '#cbd5e1', fontSize: 10 } }),
      series: [{
        type: 'bar', data: types.map(x => x.monthly_median), barWidth: '56%',
        itemStyle: { borderRadius: [0, 5, 5, 0], color: C.gradient('#34d399', false) },
        label: { show: true, position: 'right', color: '#94a3b8', fontSize: 10, formatter: p => '¥' + C.fmt(p.value) }
      }]
    });

    // 发薪月数
    C.chart('monthChart', {
      grid: { left: 18, right: 20, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => { const x = d.month_distribution[p[0].dataIndex]; return `${x.label}<br/>岗位数：${C.fmt(x.count)}（${x.share_pct}%）<br/>月薪中位：¥${C.fmt(x.monthly_median)}`; } },
      xAxis: C.catAxis(d.month_distribution.map(x => x.label)),
      yAxis: C.valAxis({ axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: [{
        type: 'bar', data: d.month_distribution.map(x => x.share_pct), barWidth: '44%',
        itemStyle: { borderRadius: [5, 5, 0, 0], color: C.gradient('#f59e0b') },
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: '{c}%' }
      }]
    });

    // 发布时间
    C.chart('dailyChart', {
      grid: { left: 18, right: 24, top: 22, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>岗位数：<b>${C.fmt(p[0].value)}</b>` },
      xAxis: C.catAxis(d.daily.map(x => x.date), { axisLabel: { color: '#64748b', fontSize: 9, interval: Math.max(0, Math.floor(d.daily.length / 8)) } }),
      yAxis: C.valAxis(),
      series: [{
        type: 'bar', data: d.daily.map(x => x.count), barWidth: '70%',
        itemStyle: { color: p => p.dataIndex === d.daily.map(x => x.count).indexOf(Math.max(...d.daily.map(x => x.count))) ? '#fb7185' : 'rgba(100,116,139,.55)' }
      }]
    });
  } catch (e) {
    C.error(app, e);
  }
})();
