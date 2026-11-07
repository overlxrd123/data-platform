/* 北京餐饮模块 */
(async function () {
  const app = document.getElementById('app');
  C.loading(app, '正在读取 44,512 家店铺并计算价格口径…');
  try {
    const d = await C.get('/api/food');
    const o = d.overview;

    const priceRows = d.price_bands.map(b => [
      b.band, C.fmt(b.stores), C.pct(b.share_pct), C.money(b.median_price),
      b.avg_rating == null ? '—' : Number(b.avg_rating).toFixed(2),
      b.top_cuisines.slice(0, 2).map(x => x.name).join(' / ')
    ]);

    const cuisinesAll = d.cuisine_table.filter(x => !['未标注', '其他'].includes(x.name));
    const cuisineTop = [...cuisinesAll].sort((a, b) => b.stores - a.stores).slice(0, 12);
    const cuisineRows = cuisinesAll.slice(0, 12).map(x => [
      x.name, C.fmt(x.stores), C.money(x.median_price), C.money(x.mean_price),
      Number(x.avg_rating).toFixed(2), C.fmt(x.median_reviews)
    ]);

    const districts = [...d.districts].sort((a, b) => b.median_price - a.median_price);
    const districtRows = districts.map(x => [
      x.name, C.fmt(x.stores), C.money(x.median_price), C.money(x.p90_price), Number(x.avg_rating).toFixed(2)
    ]);

    const michelinRows = d.michelin.map(x => [
      x.tier, C.fmt(x.stores), C.money(x.median_price), C.money(x.mean_price), Number(x.avg_rating).toFixed(2)
    ]);

    const late = [...d.late_night.top_districts].sort((a, b) => b.late_pct - a.late_pct);

    app.innerHTML = `
      <div class="page-head">
        <div class="eyebrow">Module 01 · Restaurant</div>
        <h1>北京餐饮：先把「0 元」剔掉，再谈人均</h1>
        <p>44,512 家店铺中有 13,309 家人均消费记为 0——这是未采集，不是免费。有效样本 31,203 家，人均中位数 ¥67。本模块同时检查评分覆盖、评论集中度与原始推荐标签分层。</p>
      </div>

      ${C.kpis([
        { value: C.fmt(o.stores), label: '店铺总数', sub: `${o.districts} 个区 · ${o.cuisines} 种菜系` },
        { value: C.money(o.price_median), label: '有效样本人均中位数', sub: `均值 ${C.money(o.price_mean)} · P90 ${C.money(o.price_p90)}` },
        { value: C.pct(o.price_coverage_pct), label: '价格字段覆盖率', sub: `${C.fmt(o.stores_with_price)} / ${C.fmt(o.stores)}` },
        { value: C.pct(o.rating_coverage_of_valid_pct), label: '有效样本评分覆盖', sub: `${C.fmt(d.rating.rated_stores)} 家有评分` },
        { value: C.fmt(o.reviews_total), label: '评论总数', sub: `39.4% 店铺零评论` }
      ])}

      ${C.panel('人均消费分布', '有效样本 31,203 家；中位 ¥67，P75 ¥103，P90 ¥145。价格长尾很厚，300 元以上仍有 752 家。', C.chartBox('priceDist', 'lg') + C.table(['价格带', '店铺数', '占比', '中位人均', '平均评分', '代表菜系'], priceRows, { note: '价格带按有效人均消费划分；评分仅统计有评分店铺，因此平均评分不等于全量。' }))}

      <div class="grid-2">
        ${C.panel('菜系：谁开得最多，谁卖得最贵', '按店铺数取 TOP12，柱长为该菜系的人均中位数；店铺数放在提示框里。', C.chartBox('cuisineChart', 'lg'))}
        ${C.panel('菜系明细', '按中位人均从高到低排列；样本量 ≥30 家的菜系才进入统计，「未标注 / 其他」不参与菜系对比。', C.table(['菜系', '店铺数', '中位人均', '均值', '评分', '评论中位'], cuisineRows, { note: '均值明显高于中位数，说明每个菜系内部都有高价长尾。另有 1,865 家「未标注」与 119 家「其他」，未纳入菜系对比。' }))}
      </div>

      ${C.panel('区域价格分层', '朝阳区中位人均 ¥122，石景山区 ¥44，相差 2.8 倍；海淀店铺数接近朝阳，但中位价只有 ¥79。', C.chartBox('districtChart', 'lg') + C.table(['区域', '店铺数', '中位人均', 'P90 人均', '平均评分'], districtRows, { note: '区域按中位人均降序；P90 用于观察高价尾部，受少数高端店影响较大。' }))}

      <div class="grid-2">
        ${C.panel('评分分布', `有评分店铺 ${C.fmt(d.rating.rated_stores)} 家；评分 4.0 以上占绝大多数，1–2 分是极少数。`, C.chartBox('ratingDist'))}
        ${C.panel('价格越高，评分越高？', `Spearman 相关系数 ${d.rating.price_rating_corr}，只是弱正相关：贵不等于好吃。`, C.chartBox('ratingBand'))}
      </div>

      ${C.panel('评论集中度', '评论极度集中在少数店铺：TOP1% 店铺拿走 26.1% 的评论，TOP10% 拿走 81.3%。用「平均评分」比较区域时，要意识到大量店铺几乎没有评论。', `
        <div class="chips">
          <span class="chip">TOP 1% 店铺 <b>${C.pct(d.review_concentration.top1_pct_share)}</b> 评论</span>
          <span class="chip">TOP 5% 店铺 <b>${C.pct(d.review_concentration.top5_pct_share)}</b> 评论</span>
          <span class="chip">TOP 10% 店铺 <b>${C.pct(d.review_concentration.top10_pct_share)}</b> 评论</span>
          <span class="chip">评论总数 <b>${C.fmt(d.review_concentration.total_reviews)}</b></span>
        </div>`)}

      <div class="grid-2">
        ${C.panel('原始推荐标签分层', '标签来源未核实，不代表官方米其林评级；铂金/钻石/黑钻合计仅 23 家，中位人均超过 ¥1,000。', C.chartBox('michelinChart') + C.table(['层级', '店铺数', '中位人均', '均值', '评分'], michelinRows))}
        ${C.panel('夜宵营业', `营业时间可解析的 ${C.fmt(d.late_night.parsed_stores)} 家店中，${C.pct(d.late_night.late_pct_of_parsed)} 在 23:00 后仍营业；夜宵店中位人均 ¥${d.late_night.late_median_price}。`, C.chartBox('lateChart'))}
      </div>

      ${C.panel('结论', '每一条都引用上面的统计口径，而不是「看起来」。', C.insights(d.insights) + C.notes(d.data_notes))}
    `;

    // 价格分布
    const dist = d.price_distribution;
    C.chart('priceDist', {
      grid: { left: 18, right: 24, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue} 元<br/>店铺数：<b>${C.fmt(p[0].value)}</b>` },
      xAxis: C.catAxis(dist.map(b => b.end >= 310 ? '300+' : `${b.start}-${b.end}`), { axisLabel: { color: '#94a3b8', fontSize: 10, interval: 2 } }),
      yAxis: C.valAxis(),
      series: [{
        type: 'bar',
        data: dist.map(b => b.count),
        barWidth: '82%',
        itemStyle: {
          borderRadius: [3, 3, 0, 0],
          color: p => p.dataIndex > 26 ? '#f59e0b' : C.gradient('#22d3ee')
        }
      }]
    });

    // 菜系
    const cuisines = [...cuisineTop].sort((a, b) => a.median_price - b.median_price);
    C.chart('cuisineChart', {
      grid: { left: 8, right: 58, top: 12, bottom: 8, containLabel: true },
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: p => {
          const x = cuisines[p[0].dataIndex];
          return `<b>${x.name}</b><br/>中位人均：¥${C.fmt(x.median_price)}<br/>店铺数：${C.fmt(x.stores)}<br/>平均评分：${x.avg_rating}`;
        }
      },
      xAxis: C.valAxis({ name: '元', nameTextStyle: { color: '#64748b' } }),
      yAxis: C.catAxis(cuisines.map(x => x.name), { axisLabel: { color: '#cbd5e1', fontSize: 11 } }),
      series: [{
        type: 'bar',
        data: cuisines.map(x => x.median_price),
        barWidth: '62%',
        itemStyle: { borderRadius: [0, 6, 6, 0], color: C.gradient('#8b5cf6', false) },
        label: { show: true, position: 'right', color: '#94a3b8', fontSize: 10, formatter: p => `¥${p.value}` }
      }]
    });

    // 区域
    const dsort = [...districts].reverse();
    C.chart('districtChart', {
      grid: { left: 8, right: 54, top: 12, bottom: 8, containLabel: true },
      tooltip: {
        trigger: 'axis', axisPointer: { type: 'shadow' },
        formatter: p => {
          const x = dsort[p[0].dataIndex];
          return `<b>${x.name}</b><br/>中位人均：¥${C.fmt(x.median_price)}<br/>P90：¥${C.fmt(x.p90_price)}<br/>店铺数：${C.fmt(x.stores)}`;
        }
      },
      xAxis: C.valAxis({ name: '元', nameTextStyle: { color: '#64748b' } }),
      yAxis: C.catAxis(dsort.map(x => x.name), { axisLabel: { color: '#cbd5e1', fontSize: 11 } }),
      series: [{
        type: 'bar',
        data: dsort.map(x => x.median_price),
        barWidth: '58%',
        itemStyle: { borderRadius: [0, 6, 6, 0], color: C.gradient('#22d3ee', false) },
        label: { show: true, position: 'right', color: '#94a3b8', fontSize: 10, formatter: '¥{c}' }
      }]
    });

    // 评分分布
    C.chart('ratingDist', {
      grid: { left: 18, right: 20, top: 20, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `评分 ${p[0].axisValue}<br/>店铺数：<b>${C.fmt(p[0].value)}</b>` },
      xAxis: C.catAxis(d.rating.distribution.map(x => Number(x.score).toFixed(1)), { axisLabel: { color: '#94a3b8', fontSize: 10, interval: 3 } }),
      yAxis: C.valAxis(),
      series: [{
        type: 'bar', data: d.rating.distribution.map(x => x.count), barWidth: '78%',
        itemStyle: { borderRadius: [2, 2, 0, 0], color: p => Number(p.name) >= 4 ? '#34d399' : '#fb7185' }
      }]
    });

    // 价格带 vs 评分
    const bands = d.rating.by_price_band;
    C.chart('ratingBand', {
      grid: { left: 18, right: 20, top: 28, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>平均评分：<b>${p[0].value}</b><br/>样本：${C.fmt(bands[p[0].dataIndex].rated_stores)} 家` },
      xAxis: C.catAxis(bands.map(x => x.band)),
      yAxis: C.valAxis({ min: 4, max: 4.8 }),
      series: [{
        type: 'line', data: bands.map(x => x.avg_rating), smooth: true, symbolSize: 8,
        lineStyle: { width: 3, color: '#f59e0b' },
        itemStyle: { color: '#f59e0b' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(245,158,11,.28)' }, { offset: 1, color: 'rgba(245,158,11,0)' }
        ]) }
      }]
    });

    // 米其林
    C.chart('michelinChart', {
      grid: { left: 18, right: 20, top: 28, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>中位人均：<b>¥${C.fmt(p[0].value)}</b><br/>店铺数：${C.fmt(d.michelin[p[0].dataIndex].stores)}` },
      xAxis: C.catAxis(d.michelin.map(x => x.tier)),
      yAxis: C.valAxis({ name: '元' }),
      series: [{
        type: 'bar', data: d.michelin.map(x => x.median_price), barWidth: '48%',
        itemStyle: { borderRadius: [6, 6, 0, 0], color: C.gradient('#f59e0b') }
      }]
    });

    // 夜宵
    C.chart('lateChart', {
      grid: { left: 8, right: 46, top: 12, bottom: 8, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>23:00 后营业占比：<b>${p[0].value}%</b><br/>可解析店铺：${C.fmt(late[p[0].dataIndex].parsed_stores)}` },
      xAxis: C.valAxis({ max: 50, axisLabel: { formatter: '{value}%' } }),
      yAxis: C.catAxis(late.map(x => x.name)),
      series: [{
        type: 'bar', data: late.map(x => x.late_pct), barWidth: '55%',
        itemStyle: { borderRadius: [0, 6, 6, 0], color: C.gradient('#34d399', false) },
        label: { show: true, position: 'right', color: '#94a3b8', fontSize: 10, formatter: '{c}%' }
      }]
    });
  } catch (e) {
    C.error(app, e);
  }
})();
