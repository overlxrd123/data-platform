/* 游戏评论模块 */
(async function () {
  const app = document.getElementById('app');
  C.loading(app, '正在清洗 2,531 条评论并运行 VADER 情感分析…');
  try {
    const d = await C.get('/api/game');
    const o = d.overview;

    const platformRows = d.platforms.map(x => [
      x.name, C.fmt(x.reviews), C.pct(x.share_pct), Number(x.avg_rating).toFixed(2),
      C.pct(x.positive_pct), C.pct(x.negative_pct), C.pct(x.polarization_pct),
      C.pct(x.agreement_pct)
    ]);

    const themeRows = d.themes.map(x => [
      x.label, C.fmt(x.mentions), C.pct(x.mention_pct),
      Number(x.avg_rating).toFixed(2), C.pct(x.negative_pct)
    ]);

    const matrixRows = d.sentiment_vs_rating.matrix.map(x => {
      const c = x.counts;
      return [
        x.rating_sent === 'negative' ? '低评分（0–3）' : x.rating_sent === 'neutral' ? '中评分（4–6）' : '高评分（7–10）',
        C.fmt(c.negative), C.fmt(c.neutral), C.fmt(c.positive)
      ];
    });

    const examples = d.sentiment_vs_rating.examples.map(x => `
      <div class="example-card">
        <div class="example-head">
          <span class="tag ${x.case.includes('负面') ? 'rose' : 'amber'}">${x.case}</span>
          <span class="chip">评分 <b>${x.rating}</b></span>
          <span class="chip">${C.esc(x.platform)}</span>
          <span class="chip">compound <b>${x.compound}</b></span>
        </div>
        <p>${C.esc(x.text)}</p>
      </div>`).join('');

    const kw = (list, cls) => list.map(x =>
      `<span class="chip kw ${cls}" title="TF-IDF 权重 ${x.score}">${C.esc(x.term)}</span>`).join('');

    app.innerHTML = `
      <div class="page-head">
        <div class="eyebrow">Module 02 · Game Reviews</div>
        <h1>游戏评论：玩家嘴上夸，手上却打低分</h1>
        <p>原始 2,531 条评论，去重并剔除过短文本后保留 2,362 条。VADER 文本情感与用户评分的一致率只有 61.1%——文本正面但评分偏低的有 343 条，这才是这份数据最有意思的地方。</p>
      </div>

      ${C.kpis([
        { value: C.fmt(o.analyzed_reviews), label: '有效评论', sub: `原始 ${C.fmt(o.raw_reviews)} → 去重 ${C.fmt(o.dedup_reviews)}` },
        { value: C.pct(o.positive_pct), label: '文本正面占比', sub: `负面 ${C.pct(o.negative_pct)} · 中性 ${C.pct(o.neutral_pct)}` },
        { value: C.pct(o.agreement_pct), label: '文本与评分一致率', sub: `相关系数 ${o.text_rating_corr}` },
        { value: Number(o.median_rating).toFixed(1), label: '评分中位数', sub: `均值 ${Number(o.avg_rating).toFixed(2)} / 10` },
        { value: C.fmt(o.avg_words), label: '平均评论词数', sub: `${o.platforms} 个平台` }
      ])}

      <div class="grid-2">
        ${C.panel('评分分布：两极分化', `极端评分（0–3 或 8–10）占 ${C.pct(d.polarization.extreme_pct)}，中间分段只占 ${C.pct(d.polarization.middle_pct)}。`, C.chartBox('ratingDist'))}
        ${C.panel('文本情感构成', `VADER 判定正面 ${C.pct(o.positive_pct)}、负面 ${C.pct(o.negative_pct)}、中性 ${C.pct(o.neutral_pct)}。`, C.chartBox('sentimentPie'))}
      </div>

      ${C.panel('文本情感 × 用户评分', `不一致率 ${C.pct(d.sentiment_vs_rating.disagree_pct)}：其中「文字负面但评分高」${C.fmt(d.sentiment_vs_rating.high_rating_negative_text)} 条，「文字正面但评分低」${C.fmt(d.sentiment_vs_rating.low_rating_positive_text)} 条。`, C.chartBox('matrixChart') + C.table(['用户评分情感', '文本负面', '文本中性', '文本正面'], matrixRows, { note: '行为评分情感按 0–3 / 4–6 / 7–10 划分；文本情感来自 VADER compound 分数。' }))}

      ${C.panel('错位样本长什么样', '下面是从两个不一致类别中各抽取的原文——读起来确实能理解为什么情感模型和评分会打架。', `<div class="example-grid">${examples}</div>`)}

      <div class="grid-2">
        ${C.panel('平台差异', 'XBOX 360 的文本正面率最高（70.7%）；PS5 的负面率最高（35.2%）且极化程度最高（72.7%）。平台之间的评论长度差异也很明显：XBOX 平均 126 词，PS5 只有 68 词。', C.chartBox('platformChart', 'lg') + C.table(['平台', '评论数', '占比', '均分', '正面', '负面', '极化', '一致率'], platformRows))}
        <div>
          ${C.panel('评论长度与评分', '长评论反而更容易给出负面评价——愿意写长文的玩家，通常有明确的不满或期待。', C.chartBox('lengthChart'))}
          ${C.panel('关键词：正负评论各在说什么', 'TF-IDF 提取的高权重词，已去掉停用词与游戏名。', `
            <div class="kw-group"><div class="kw-label">正面评论</div><div class="chips">${kw(d.keywords.positive, 'pos')}</div></div>
            <div class="kw-group"><div class="kw-label">负面评论</div><div class="chips">${kw(d.keywords.negative, 'neg')}</div></div>
            <div class="table-note">同一词可能同时出现在两侧（如 story），说明它在两类评论中都是高频话题，只是情绪方向不同。</div>`)}
        </div>
      </div>

      ${C.panel('主题词典：玩家最在意什么', '剧情与角色被提及最多（48.3%）；但负面率最高的是 Bug 与性能（45.3%），其次是价格与内购（39.6%）。', C.chartBox('themeChart', 'lg') + C.table(['主题', '提及次数', '提及率', '平均评分', '负面率'], themeRows, { note: '主题按关键词词典匹配，一条评论可命中多个主题，因此提及率之和大于 100%。' }))}

      ${C.panel('结论', '情感分析与评分是两种不同的信号，不能互相替代。', C.insights(d.insights) + C.notes(d.data_notes))}
    `;

    // 评分分布
    C.chart('ratingDist', {
      grid: { left: 18, right: 20, top: 24, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `评分 ${p[0].axisValue}<br/>评论数：<b>${C.fmt(p[0].value)}</b>` },
      xAxis: C.catAxis(d.rating_distribution.map(x => x.rating)),
      yAxis: C.valAxis(),
      series: [{
        type: 'bar', data: d.rating_distribution.map(x => x.count), barWidth: '66%',
        itemStyle: {
          borderRadius: [4, 4, 0, 0],
          color: p => Number(p.name) <= 3 ? '#fb7185' : Number(p.name) <= 6 ? '#f59e0b' : '#34d399'
        },
        label: { show: true, position: 'top', color: '#64748b', fontSize: 9 }
      }]
    });

    // 情感饼图
    C.chart('sentimentPie', {
      tooltip: { trigger: 'item', formatter: p => `${p.name}：<b>${p.value}%</b> 的评论` },
      legend: { bottom: 4, top: 'auto' },
      title: {
        text: C.fmt(o.analyzed_reviews), subtext: '有效评论',
        left: 'center', top: '36%', textAlign: 'center',
        textStyle: { color: '#f8fafc', fontSize: 20, fontWeight: 750 },
        subtextStyle: { color: '#94a3b8', fontSize: 11 }
      },
      series: [{
        type: 'pie', radius: ['52%', '74%'], center: ['50%', '44%'],
        itemStyle: { borderColor: '#0b1220', borderWidth: 3, borderRadius: 4 },
        label: { position: 'inside', color: '#04121a', fontSize: 11, fontWeight: 700, formatter: p => p.percent >= 8 ? p.percent + '%' : '' },
        labelLine: { show: false },
        data: [
          { name: '正面', value: o.positive_pct, itemStyle: { color: '#34d399' } },
          { name: '负面', value: o.negative_pct, itemStyle: { color: '#fb7185' } },
          { name: '中性', value: o.neutral_pct, itemStyle: { color: '#64748b' } }
        ]
      }]
    });

    // 情感 × 评分
    const order = ['negative', 'neutral', 'positive'];
    const ratingLabels = { negative: '低评分 0–3', neutral: '中评分 4–6', positive: '高评分 7–10' };
    const textLabels = { negative: '文本负面', neutral: '文本中性', positive: '文本正面' };
    C.chart('matrixChart', {
      grid: { left: 18, right: 24, top: 40, bottom: 10, containLabel: true },
      legend: { top: 4 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: C.catAxis(d.sentiment_vs_rating.matrix.map(x => ratingLabels[x.rating_sent])),
      yAxis: C.valAxis(),
      series: order.map((k, i) => ({
        name: textLabels[k],
        type: 'bar',
        stack: 'total',
        barWidth: '46%',
        itemStyle: { color: ['#fb7185', '#64748b', '#34d399'][i], borderRadius: i === 2 ? [4, 4, 0, 0] : 0 },
        data: d.sentiment_vs_rating.matrix.map(x => x.counts[k]),
        label: { show: true, color: '#e2e8f0', fontSize: 10, formatter: p => p.value >= 30 ? p.value : '' }
      }))
    });

    // 平台
    C.chart('platformChart', {
      grid: { left: 18, right: 20, top: 40, bottom: 10, containLabel: true },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: v => v + '%' },
      legend: { top: 4 },
      xAxis: C.catAxis(d.platforms.map(x => x.name)),
      yAxis: C.valAxis({ axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: [
        { name: '文本正面率', type: 'bar', barWidth: '30%', itemStyle: { borderRadius: [4, 4, 0, 0], color: '#34d399' }, data: d.platforms.map(x => x.positive_pct) },
        { name: '文本负面率', type: 'bar', barWidth: '30%', itemStyle: { borderRadius: [4, 4, 0, 0], color: '#fb7185' }, data: d.platforms.map(x => x.negative_pct) }
      ]
    });

    // 长度
    C.chart('lengthChart', {
      grid: { left: 18, right: 18, top: 34, bottom: 10, containLabel: true },
      tooltip: { trigger: 'axis' },
      legend: { top: 2 },
      xAxis: C.catAxis(d.length_analysis.map(x => x.bucket)),
      yAxis: [
        C.valAxis({ min: 0, max: 10, name: '评分', nameTextStyle: { color: '#64748b' } }),
        C.valAxis({ min: 0, max: 60, name: '负面率%', nameTextStyle: { color: '#64748b' }, splitLine: { show: false }, axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } })
      ],
      series: [
        { name: '平均评分', type: 'line', smooth: true, symbolSize: 8, yAxisIndex: 0, lineStyle: { width: 3, color: '#22d3ee' }, itemStyle: { color: '#22d3ee' }, data: d.length_analysis.map(x => x.avg_rating) },
        { name: '负面率', type: 'bar', yAxisIndex: 1, barWidth: '40%', itemStyle: { borderRadius: [4, 4, 0, 0], color: 'rgba(251,113,133,.55)' }, data: d.length_analysis.map(x => x.negative_pct) }
      ]
    });

    // 主题
    C.chart('themeChart', {
      grid: { left: 18, right: 24, top: 40, bottom: 10, containLabel: true },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { top: 4 },
      xAxis: C.catAxis(d.themes.map(x => x.label), { axisLabel: { color: '#94a3b8', fontSize: 10, interval: 0, rotate: 22 } }),
      yAxis: C.valAxis({ axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: [
        { name: '提及率', type: 'bar', barWidth: '32%', itemStyle: { borderRadius: [4, 4, 0, 0], color: C.gradient('#22d3ee') }, data: d.themes.map(x => x.mention_pct) },
        { name: '负面率', type: 'bar', barWidth: '32%', itemStyle: { borderRadius: [4, 4, 0, 0], color: 'rgba(251,113,133,.7)' }, data: d.themes.map(x => x.negative_pct) }
      ]
    });
  } catch (e) {
    C.error(app, e);
  }
})();
