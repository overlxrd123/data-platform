/* 北京租房模块 */
(async function () {
  const app = document.getElementById('app');
  C.loading(app, '正在读取 35,082 条房源并拆分整租/合租口径…');
  try {
    const d = await C.get('/api/rental');
    const o = d.overview;

    const typeRows = d.rent_types.map(x => [
      x.name, C.fmt(x.count), C.pct(x.share_pct), C.money(x.rent_median),
      `${x.area_median}㎡`, `¥${x.unit_median}/㎡`, `${x.area_p25}–${x.area_p75}㎡`
    ]);

    const whole = d.district_by_type['整租'] || [];
    const shared = d.district_by_type['合租'] || [];
    const districtNames = [...whole].sort((a, b) => b.rent_median - a.rent_median).map(x => x.district);
    const wholeMap = Object.fromEntries(whole.map(x => [x.district, x]));
    const sharedMap = Object.fromEntries(shared.map(x => [x.district, x]));

    const districtRows = [...d.districts].sort((a, b) => b.rent_median - a.rent_median).map(x => [
      x.district, C.fmt(x.count), C.money(x.rent_median), `¥${x.unit_median}/㎡`,
      `${x.area_median}㎡`, C.pct(x.whole_pct), C.pct(x.subway_pct)
    ]);

    const amenityRows = d.amenities.map(x => [
      x.label, C.fmt(x.yes_count), C.pct(x.yes_share_pct),
      `¥${x.yes_unit_median}/㎡`, `¥${x.no_unit_median}/㎡`, C.pct(x.diff_pct)
    ]);

    const attrSpread = d.attribute_spread_pct;

    app.innerHTML = `
      <div class="page-head">
        <div class="eyebrow">Module 05 · Beijing Rental</div>
        <h1>北京租房：整租和合租必须分开算</h1>
        <p>35,082 条房源。整租中位租金 ¥5,236、合租 ¥1,400，差了 3.7 倍；但整租面积中位 88.8㎡、合租 17.5㎡，所以真正可比的是单价。更重要的是：同房型内租金与面积几乎不相关（r≈0），「面积越小单价越高」主要是除法效应。</p>
      </div>

      ${C.kpis([
        { value: C.fmt(o.listings), label: '房源总数', sub: `${o.districts} 个区 · ${o.date_start} 至 ${o.date_end}` },
        { value: C.money(o.rent_median), label: '租金中位数', sub: `P25 ${C.money(o.rent_p25)} · P75 ${C.money(o.rent_p75)}` },
        { value: `¥${o.unit_median}`, label: '单价中位数（元/㎡）', sub: `面积中位 ${o.area_median}㎡` },
        { value: C.pct(o.whole_share_pct), label: '整租占比', sub: `合租 ${C.pct(100 - o.whole_share_pct)}` },
        { value: C.pct(o.subway_share_pct), label: '近地铁房源占比', sub: '字段为 0/1 标记，非距离' }
      ])}

      ${C.panel('整租 vs 合租：先统一口径', '两种房型的租金、面积、单价都不同，混在一起算「北京平均租金」没有业务含义。', `
        <div class="grid-2">
          ${C.chartBox('typeRent')}
          ${C.chartBox('typeUnit')}
        </div>
        ${C.table(['房型', '房源数', '占比', '租金中位', '面积中位', '单价中位', '面积 P25–P75'], typeRows, { note: '单价 = 月租金 ÷ 面积；合租单价更高（83.5 vs 61.9 元/㎡）主要来自面积口径——合租房间面积中位仅 17.5㎡，租金并不按面积等比缩放。' })}`)}

      ${C.panel('分房型的区域价格', '同一个区，整租和合租的价格排序并不完全一致；把两种房型混在一起做区域排名，会被房型结构差异污染。', C.chartBox('districtTypeChart', 'lg') + C.table(['区域', '房源数', '租金中位', '单价中位', '面积中位', '整租占比', '近地铁'], districtRows, { note: '区域按租金中位数降序；单价单位为元/㎡/月。' }))}

      <div class="grid-2">
        ${C.panel('面积与单价：除法效应', `面积越大，单价越低——但同房型内租金与面积的相关系数只有 ${d.rent_area_corr['整租']}（整租）和 ${d.rent_area_corr['合租']}（合租）。注意租金中位线在 45–60㎡ 附近跳升，这是房型结构从合租切换到整租造成的，不是面积效应；因此面积效应只看单价。`, C.chartBox('areaChart', 'lg'))}
        ${C.panel('面积—租金散点（抽样 800 条）', '散点按房型着色：整租集中在右上（大面积、高租金），合租集中在左下。两条带几乎水平，进一步说明同房型内面积对租金的解释力很弱。', C.chartBox('scatterChart', 'lg'))}
      </div>

      ${C.panel('配套字段：组间差异接近 0', `近地铁、近学校、近医院、近商场的单价差异都在 1% 以内；朝向的组间差异也只有 ${C.pct(attrSpread['朝向'])}。这份数据的配套字段更像随机生成，不能用来写「地铁房溢价」这类结论。`, C.chartBox('amenityChart') + C.table(['配套', '有该配套', '占比', '有：单价中位', '无：单价中位', '差异'], amenityRows, { note: '差异 =（有 − 无）÷ 无；接近 0 表示该字段与租金几乎无关。' }))}

      <div class="grid-3">
        ${C.panel('装修', `组间差异 ${C.pct(attrSpread['装修'])}`, C.chartBox('decoChart', 'sm'))}
        ${C.panel('楼层', `组间差异 ${C.pct(attrSpread['楼层'])}`, C.chartBox('floorChart', 'sm'))}
        ${C.panel('朝向', `组间差异 ${C.pct(attrSpread['朝向'])}`, C.chartBox('orientChart', 'sm'))}
      </div>

      <div class="grid-2">
        ${C.panel('地铁距离分档', '距离地铁越近，单价并未明显更高；各档单价差异很小，与「近地铁」字段的结论一致。', C.chartBox('subwayChart'))}
        ${C.panel('月度趋势', `24 个月的租金中位数与单价中位数整体平稳，首尾变化约 ${((d.trend[d.trend.length - 1].rent_median / d.trend[0].rent_median - 1) * 100).toFixed(1)}%；这份数据不适合做市场周期判断。`, C.chartBox('trendChart'))}
      </div>

      ${C.panel('结论', '先质疑数据，再解释现象——这是本模块最重要的部分。', C.insights(d.insights) + C.notes(d.data_notes))}
    `;

    // 房型租金
    C.chart('typeRent', {
      grid: { left: 18, right: 20, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>租金中位：<b>¥${C.fmt(p[0].value)}</b><br/>房源：${C.fmt(d.rent_types[p[0].dataIndex].count)}` },
      xAxis: C.catAxis(d.rent_types.map(x => x.name)),
      yAxis: C.valAxis({ name: '元/月' }),
      series: [{
        type: 'bar', data: d.rent_types.map(x => x.rent_median), barWidth: '42%',
        itemStyle: { borderRadius: [6, 6, 0, 0], color: p => p.dataIndex ? '#8b5cf6' : '#22d3ee' },
        label: { show: true, position: 'top', color: '#e2e8f0', fontSize: 12, formatter: p => '¥' + C.fmt(p.value) }
      }]
    });

    // 房型单价
    C.chart('typeUnit', {
      grid: { left: 18, right: 20, top: 30, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>单价中位：<b>¥${p[0].value}/㎡</b><br/>面积中位：${d.rent_types[p[0].dataIndex].area_median}㎡` },
      xAxis: C.catAxis(d.rent_types.map(x => x.name)),
      yAxis: C.valAxis({ name: '元/㎡/月' }),
      series: [{
        type: 'bar', data: d.rent_types.map(x => x.unit_median), barWidth: '42%',
        itemStyle: { borderRadius: [6, 6, 0, 0], color: p => p.dataIndex ? '#8b5cf6' : '#22d3ee' },
        label: { show: true, position: 'top', color: '#e2e8f0', fontSize: 12, formatter: '¥{c}' }
      }]
    });

    // 分房型区域
    C.chart('districtTypeChart', {
      grid: { left: 18, right: 24, top: 40, bottom: 10, containLabel: true },
      legend: { top: 4 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: v => '¥' + C.fmt(v) },
      xAxis: C.catAxis(districtNames, { axisLabel: { color: '#94a3b8', fontSize: 10, interval: 0, rotate: 26 } }),
      yAxis: C.valAxis({ name: '元/月' }),
      series: [
        { name: '整租', type: 'bar', barWidth: '30%', itemStyle: { borderRadius: [4, 4, 0, 0], color: 'rgba(34,211,238,.75)' }, data: districtNames.map(n => wholeMap[n] ? wholeMap[n].rent_median : null) },
        { name: '合租', type: 'bar', barWidth: '30%', itemStyle: { borderRadius: [4, 4, 0, 0], color: 'rgba(139,92,246,.8)' }, data: districtNames.map(n => sharedMap[n] ? sharedMap[n].rent_median : null) }
      ]
    });

    // 面积
    C.chart('areaChart', {
      grid: { left: 18, right: 30, top: 40, bottom: 10, containLabel: true },
      legend: { top: 2 },
      tooltip: { trigger: 'axis' },
      xAxis: C.catAxis(d.area_bands.map(x => x.band), { axisLabel: { color: '#94a3b8', fontSize: 9, interval: 0, rotate: 18 } }),
      yAxis: [
        C.valAxis({ name: '元/㎡', axisLabel: { color: '#94a3b8', fontSize: 11 } }),
        C.valAxis({ name: '元/月', splitLine: { show: false }, axisLabel: { color: '#94a3b8', fontSize: 11 } })
      ],
      series: [
        { name: '单价中位', type: 'bar', barWidth: '46%', itemStyle: { borderRadius: [5, 5, 0, 0], color: C.gradient('#22d3ee') }, data: d.area_bands.map(x => x.unit_median) },
        { name: '租金中位', type: 'line', yAxisIndex: 1, smooth: true, symbolSize: 7, lineStyle: { width: 2.5, color: '#f59e0b' }, itemStyle: { color: '#f59e0b' }, data: d.area_bands.map(x => x.rent_median) }
      ]
    });

    // 散点
    const groups = ['整租', '合租'];
    C.chart('scatterChart', {
      grid: { left: 18, right: 40, top: 40, bottom: 14, containLabel: true },
      legend: { top: 2 },
      tooltip: {
        trigger: 'item',
        formatter: p => `${p.seriesName}<br/>面积：${p.data[0]}㎡<br/>租金：¥${C.fmt(p.data[1])}<br/>单价：¥${p.data[2]}/㎡<br/>${p.data[3]}`
      },
      xAxis: C.valAxis({ name: '面积 ㎡', nameGap: 16, scale: true }),
      yAxis: C.valAxis({ name: '租金 元/月', scale: true }),
      series: groups.map((g, i) => ({
        name: g, type: 'scatter', symbolSize: 5,
        itemStyle: { color: i ? 'rgba(139,92,246,.45)' : 'rgba(34,211,238,.45)' },
        data: d.scatter.filter(x => x.rent_type === g).map(x => [x.area, x.rent, x.unit, x.district])
      }))
    });

    // 配套
    C.chart('amenityChart', {
      grid: { left: 18, right: 30, top: 22, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>单价差异：<b>${p[0].value}%</b>` },
      xAxis: C.catAxis(d.amenities.map(x => x.label)),
      yAxis: C.valAxis({ min: -5, max: 5, axisLabel: { color: '#94a3b8', fontSize: 11, formatter: '{value}%' } }),
      series: [{
        type: 'bar', data: d.amenities.map(x => x.diff_pct), barWidth: '42%',
        itemStyle: { borderRadius: [5, 5, 0, 0], color: p => Number(p.value) >= 0 ? '#34d399' : '#fb7185' },
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10, formatter: '{c}%' }
      }]
    });

    // 属性组
    const attrChart = (id, list, color) => C.chart(id, {
      grid: { left: 8, right: 12, top: 16, bottom: 4, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>单价中位：<b>¥${p[0].value}</b>` },
      xAxis: C.catAxis(list.map(x => x.group), { axisLabel: { color: '#94a3b8', fontSize: 10, interval: 0, rotate: 24 } }),
      yAxis: C.valAxis({ scale: true, axisLabel: { color: '#94a3b8', fontSize: 9 } }),
      series: [{
        type: 'bar', data: list.map(x => x.unit_median), barWidth: '46%',
        itemStyle: { borderRadius: [4, 4, 0, 0], color },
        label: { show: true, position: 'top', color: '#64748b', fontSize: 9 }
      }]
    });
    attrChart('decoChart', d.attributes.decoration, 'rgba(34,211,238,.7)');
    attrChart('floorChart', d.attributes.floor, 'rgba(139,92,246,.7)');
    attrChart('orientChart', d.attributes.orientation, 'rgba(245,158,11,.75)');

    // 地铁
    C.chart('subwayChart', {
      grid: { left: 18, right: 22, top: 28, bottom: 10, containLabel: true },
      tooltip: { formatter: p => `${p[0].axisValue}<br/>单价中位：¥${p[0].value}/㎡<br/>房源：${C.fmt(d.subway_distance[p[0].dataIndex].count)}` },
      xAxis: C.catAxis(d.subway_distance.map(x => x.band)),
      yAxis: C.valAxis({ scale: true, name: '元/㎡' }),
      series: [{
        type: 'bar', data: d.subway_distance.map(x => x.unit_median), barWidth: '48%',
        itemStyle: { borderRadius: [5, 5, 0, 0], color: C.gradient('#34d399') },
        label: { show: true, position: 'top', color: '#94a3b8', fontSize: 10 }
      }]
    });

    // 趋势
    C.chart('trendChart', {
      grid: { left: 18, right: 26, top: 36, bottom: 10, containLabel: true },
      legend: { top: 2 },
      tooltip: { trigger: 'axis' },
      xAxis: C.catAxis(d.trend.map(x => x.month), { axisLabel: { color: '#64748b', fontSize: 9, interval: 2 } }),
      yAxis: [
        C.valAxis({ name: '租金', axisLabel: { color: '#94a3b8', fontSize: 10 } }),
        C.valAxis({ name: '单价', splitLine: { show: false }, axisLabel: { color: '#94a3b8', fontSize: 10 } })
      ],
      series: [
        { name: '租金中位', type: 'line', smooth: true, symbol: 'none', lineStyle: { width: 2.5, color: '#f59e0b' }, itemStyle: { color: '#f59e0b' }, data: d.trend.map(x => x.rent_median) },
        { name: '单价中位', type: 'line', yAxisIndex: 1, smooth: true, symbol: 'none', lineStyle: { width: 2.5, color: '#22d3ee' }, itemStyle: { color: '#22d3ee' }, data: d.trend.map(x => x.unit_median) }
      ]
    });
  } catch (e) {
    C.error(app, e);
  }
})();
