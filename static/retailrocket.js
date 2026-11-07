/* 真实电商行为：MySQL汇总快照 → 同口径交互图表。 */
(async () => {
  const app = C.el('app');
  try {
    const d = await C.get('/api/retailrocket');
    const o = d.overview;
    const chart = (id, title, desc, cls = '') => C.panel(title, desc, C.chartBox(id, cls));
    app.innerHTML = `
      <section class="page-hero"><div class="eyebrow">RETAILROCKET / 真实电商数据</div><h1>访问之后，购买与回访发生了吗？</h1><p>2015年历史匿名样本 · UTC · MySQL汇总快照 · 非实时数据</p>
      <p><a href="${C.esc(d.provenance.source_url)}" target="_blank" rel="noopener noreferrer">Kaggle 数据来源 ↗</a> · <a href="${C.esc(d.provenance.analysis_url)}" target="_blank" rel="noopener noreferrer">完整 SQL / Python 分析 ↗</a></p></section>
      ${C.kpis([{value:C.fmt(o.events),label:'行为事件',sub:'事件数，非人数'}, {value:C.fmt(o.visitors),label:'全期去重访客标识',sub:'不等于现实独立个人'}, {value:C.fmt(o.purchase_events),label:'购买事件',sub:'不等于订单数'}, {value:C.fmt(o.complete_days),label:'趋势分析天数',sub:'排除首尾不完整日'}])}
      ${C.panel('每日访问与购买', '筛选仅影响此趋势图；其他面板保留各自完整观察样本。7日指标始终按完整样本计算，筛选不重置窗口。', `
        <div class="rr-controls"><label>起始日期 <input id="rrStart" type="date" min="2015-05-04" max="2015-09-17" value="2015-05-04"></label><label>结束日期 <input id="rrEnd" type="date" min="2015-05-04" max="2015-09-17" value="2015-09-17"></label><label>指标 <select id="rrMetric"><option value="active">活跃访客</option><option value="buyers">购买访客</option><option value="rate">购买访客占比</option></select></label><span id="rrFilterNote" role="status" aria-live="polite"></span></div>${C.chartBox('rrTrend')}`)}
      <div class="grid-2">${chart('rrWeekday','星期规律','UTC星期；购买占比按访客日加权，不直接平均每日比例。')}${chart('rrJuly','7月周末：访问与购买占比','访问高不等于转化高；双轴分别标注人数与百分比。')}</div>
      ${chart('rrHourly','相邻两个周末的小时分布','UTC 7月18、19、25、26日。小时去重访客不能相加当每日独立人数。')}
      <div class="grid-2">${chart('rrFunnel','24小时有序漏斗','同访客、同商品，首次浏览后依次加购和购买；单位为访客—商品对。')}${chart('rrWindows','延长观察窗口','共同起点样本统一具备7天观察期，与左侧24小时主漏斗样本不同。')}</div>
      ${chart('rrExact','精确第N日回访','首次观察不等于注册。D7为精确第7日，不是7天内回访。')}
      ${chart('rrCohort','周回访热力图','第1周为首次观察后第7—13天。灰色为观察不足，不是零回访；第0周不展示。','xl')}
      <div class="grid-2">${chart('rrCategory','已知类别购买事件 Top 12','匿名编号，不能推断具体品类；不包含未知历史类别，事件数不是订单数。')}${chart('rrAvailability','事件发生时的可售状态','各柱以各类事件数为分母。这不是状态对购买的转化率或因果效果。')}</div>
      ${C.panel('结论与数据边界', `快照导入时间：${C.esc(d.provenance.snapshot_imported_at)}。导入时间不代表数据采集时间；许可 ${C.esc(d.provenance.license)}。`, C.insights(d.insights.map(C.esc))+C.notes(d.data_notes.map(C.esc)))}
    `;
    const line = (name,data,extra={}) => ({name,type:'line',data,showSymbol:false,...extra});
    const trend = C.chart('rrTrend', {});
    function updateTrend() {
      const start=C.el('rrStart').value, end=C.el('rrEnd').value;
      if (!start || !end || start>end) { C.el('rrFilterNote').textContent='请选择有效的日期范围'; return; }
      const rows=d.daily.filter(r=>r.event_date_utc>=start && r.event_date_utc<=end);
      const metric=C.el('rrMetric').value;
      const config={active:['active_visitors','active_7d','访客数'],buyers:['buying_visitors','buyers_7d','购买访客数'],rate:['daily_buyer_rate_pct','buyer_rate_7d','购买占比（%）']}[metric];
      C.el('rrFilterNote').textContent=`${rows.length} 天（UTC）`;
      trend.setOption({tooltip:{trigger:'axis'},legend:{data:['每日值','7日滚动值']},dataZoom:[{type:'inside'},{type:'slider',bottom:0}],grid:{bottom:65},xAxis:C.catAxis(rows.map(r=>r.event_date_utc)),yAxis:C.valAxis({name:config[2]}),series:[line('每日值',rows.map(r=>r[config[0]]),{lineStyle:{opacity:.4}}),line('7日滚动值',rows.map(r=>r[config[1]]))]},true);
    }
    ['rrStart','rrEnd','rrMetric'].forEach(id=>C.el(id).addEventListener('change',updateTrend)); updateTrend();
    C.chart('rrWeekday',{tooltip:{trigger:'axis'},xAxis:C.catAxis(['周一','周二','周三','周四','周五','周六','周日']),yAxis:C.valAxis({name:'购买占比（%）'}),series:[{name:'购买占比',type:'bar',data:d.weekday.map(r=>({value:r.buyer_rate_pct,itemStyle:{color:r.weekday_number>=6?'#f59e0b':'#22d3ee'}}))}]});
    C.chart('rrJuly',{legend:{data:['活跃访客','购买占比']},xAxis:C.catAxis(d.july.map(r=>r.event_date_utc.slice(5))),yAxis:[C.valAxis({name:'活跃访客'}),C.valAxis({name:'占比（%）',position:'right'})],series:[{name:'活跃访客',type:'bar',data:d.july.map(r=>r.active_visitors)},line('购买占比',d.july.map(r=>r.daily_buyer_rate_pct),{yAxisIndex:1,showSymbol:true})]});
    const days=[...new Set(d.hourly.map(r=>r.event_date_utc))];
    C.chart('rrHourly',{legend:{data:days},xAxis:C.catAxis(Array.from({length:24},(_,i)=>String(i))),yAxis:C.valAxis({name:'小时访客'}),series:days.map(date=>line(date,Array.from({length:24},(_,h)=>d.hourly.find(r=>r.event_date_utc===date&&r.hour_utc===h)?.active_visitors??null)))});
    C.chart('rrFunnel',{tooltip:{trigger:'item',formatter:p=>`${C.esc(p.name)}：${C.fmt(p.value)} 对`},series:[{type:'funnel',left:'10%',top:30,bottom:20,width:'80%',minSize:'10%',maxSize:'100%',label:{position:'inside',formatter:p=>`${p.name}\n${C.fmt(p.value)} 对`},data:d.funnel.map((r,i)=>({name:['首次浏览','随后加购','随后购买'][i],value:r.pair_count}))}],graphic:[{type:'text',bottom:0,left:'center',style:{text:'形状设有最小宽度；准确数量请看标签',fill:'#94a3b8',fontSize:11}}]});
    C.chart('rrWindows',{xAxis:C.catAxis(['24小时','72小时','7天']),yAxis:C.valAxis({name:'浏览→购买（%）',min:0}),series:[line('有序购买占比',d.windows.map(r=>r.view_to_purchase_pct),{showSymbol:true})]});
    C.chart('rrExact',{xAxis:C.catAxis(d.retention.map(r=>'D'+r.day_n)),yAxis:C.valAxis({name:'回访率（%）'}),series:[{name:'回访率',type:'bar',data:d.retention.map(r=>r.retention_rate_pct),label:{show:true,position:'top',formatter:p=>C.pct(p.value,3)}}]});
    const weeks=[...new Set(d.cohorts.map(r=>r.cohort_week))].sort();
    const heat=d.cohorts.map(r=>[r.week_index-1,weeks.indexOf(r.cohort_week),r.retention_rate_pct]);
    const validHeat=heat.filter(r=>r[2]!==null);
    C.chart('rrCohort',{grid:{left:80,right:35,top:15,bottom:65},tooltip:{trigger:'item',formatter:p=>`${C.esc(weeks[p.data[1]])}分群<br>第${p.data[0]+1}周：${C.pct(p.data[2],2)}`},xAxis:C.catAxis(Array.from({length:7},(_,i)=>'第'+(i+1)+'周')),yAxis:C.catAxis(weeks,{inverse:true,splitArea:{show:true,areaStyle:{color:['#25303b','#25303b']}}}),visualMap:{min:0,max:Math.max(...validHeat.map(r=>r[2])),orient:'horizontal',left:'center',bottom:0,textStyle:{color:'#94a3b8'},inRange:{color:['#0b1220','#0e7490','#22d3ee']}},series:[{type:'heatmap',data:validHeat,label:{show:true,fontSize:9,formatter:p=>Number(p.data[2]).toFixed(1)},itemStyle:{borderWidth:1,borderColor:'#17212d'}}]});
    const cats=[...d.categories].reverse();
    C.chart('rrCategory',{grid:{left:60},xAxis:C.valAxis({name:'购买事件'}),yAxis:C.catAxis(cats.map(r=>String(r.category_id))),series:[{type:'bar',data:cats.map(r=>r.purchase_events)}]});
    const eventCols=['view_events','cart_events','purchase_events'];
    C.chart('rrAvailability',{legend:{data:['可售','不可售','未知']},xAxis:C.catAxis(['浏览事件','加购事件','购买事件']),yAxis:C.valAxis({max:100,name:'事件构成（%）'}),series:['可售','不可售','未知'].map((status,i)=>({name:status,type:'bar',stack:'states',itemStyle:{color:['#34d399','#f59e0b','#64748b'][i]},data:eventCols.map(col=>100*(d.availability.find(r=>r.status===status)?.[col]??0)/d.availability.reduce((sum,r)=>sum+r[col],0))}))});
  } catch(e) { C.error(app,e); }
})();
