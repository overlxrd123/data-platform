(() => {
  const names = ['电商行为', '北京餐饮', '北京租房', '数据岗招聘', '美国房价', '消费者调查', '国产电影'];
  C.chart('datasetChart', {
    grid: {left: 0, right: 60, top: 5, bottom: 0, containLabel: true},
    xAxis: C.valAxis({type:'log', min:100, show:false}),
    yAxis: C.catAxis(names, {inverse: true, axisLine: {show: false}, axisLabel: {color: '#a7b5c5', fontSize: 12}}),
    tooltip: {trigger: 'item', formatter: p => `${C.esc(p.name)}<br>${C.fmt(p.value)} 条原始记录`},
    series: [{type: 'bar', barWidth: 12, showBackground: true, backgroundStyle: {color: '#1c2734', borderRadius: 3},
      data: [2756101, 44512, 35082, 3523, 1460, 1453, 120].map((value, i) => ({value, itemStyle: {color: ['#2dd4bf', '#5ac7a5', '#699ed2', '#8ba9bd', '#d2b87c', '#9a94cb', '#ca92a8'][i], borderRadius: 3}})),
      label: {show: true, position: 'right', color: '#b8c5d1', formatter: p => C.fmt(p.value), fontSize: 11}}]
  });
  const search = document.getElementById('datasetSearch');
  search.addEventListener('input', () => {
    const q = search.value.trim().toLocaleLowerCase();
    let count = 0;
    document.querySelectorAll('.module-card').forEach(card => {
      card.hidden = !card.textContent.toLocaleLowerCase().includes(q);
      if (!card.hidden) count++;
    });
    document.getElementById('searchEmpty').hidden = count !== 0;
    document.getElementById('datasetCount').textContent = q ? `找到 ${count} 个分析场景` : '全部 7 个分析场景';
  });
})();
