/* 三个公开数据模块共享布局；筛选范围在面板内明确说明。 */
(async () => {
  const slug = location.pathname.split('/').pop();
  const app = C.el('app');
  const panel = (id, title, note) => C.panel(title, note, C.chartBox(id));
  const bar = (id, rows, key, unit = '') => C.chart(id, {
    tooltip: {trigger:'axis'}, grid:{bottom:35},
    xAxis:C.catAxis(rows.map(r=>String(r.name)), {axisLabel:{rotate:30,color:'#94a3b8'}}),
    yAxis:C.valAxis({name:unit}), series:[{name:unit,type:'bar',data:rows.map(r=>r[key])}]
  });
  try {
    const d = await C.get(`/api/${slug}`), o = d.overview;
    const configs = {
      housing:['美国房屋成交价格','AMES HOUSING','从房屋特征理解成交价格，检验预测误差。'],
      movies:['国产电影分析','CHINESE MOVIES','同一份电影样本，观察票房、评分与类型的关系。'],
      survey:['麦当劳消费者调查','CONSUMER SURVEY','从品牌认知、到访频率和好感差异理解消费者。']
    };
    const [title,en,desc]=configs[slug];
    const kpis = slug==='housing' ? [
      {value:C.fmt(o.records),label:'已知售价房屋',sub:`${o.year_start}–${o.year_end}年成交样本`},
      {value:`$${C.fmt(o.median_price_usd)}`,label:'成交售价中位数',sub:'美元/套，不是月租金'},
      {value:C.fmt(o.neighborhoods),label:'社区数量'},
      {value:`$${C.fmt(d.metrics.mae_usd)}`,label:'留出验证MAE',sub:`${d.metrics.validation_count}套验证房屋`}
    ] : slug==='movies' ? [
      {value:C.fmt(o.records),label:'电影样本'},
      {value:C.fmt(o.median_revenue_yi,2),label:'累计票房中位数（亿元）'},
      {value:C.fmt(o.mean_douban,2),label:'豆瓣平均评分（/10）'},
      {value:C.fmt(o.mean_maoyan,2),label:'猫眼平均评分（/10）'}
    ] : [
      {value:C.fmt(o.records),label:'问卷样本'},
      {value:C.pct(o.positive_pct),label:'正向好感占比',sub:'好感分>0'},
      {value:C.fmt(o.mean_like,2),label:'平均好感分',sub:'−5（讨厌）至+5（喜欢）'},
      {value:C.fmt(o.median_age),label:'年龄中位数（岁）'}
    ];
    const sourceLink=d.source_url?` <a href="${C.esc(d.source_url)}" target="_blank" rel="noopener noreferrer">查看数据说明 ↗</a>`:'';
    let body='';
    if(slug==='housing') {
      body=`${C.panel('国内外住房：先区分交易口径','北京展示月租金，美国展示成交售价；分别分析，不进行租金与售价、人民币与美元的直接比较。','<p><a href="/module/rental">查看北京租房 →</a> · 北京：元/月、㎡；美国：美元/套、平方英尺。</p>')}
      <div class="grid-2">${panel('hNeighborhood','各社区成交售价中位数','全部社区；请同时查看下方样本量表，房屋结构与成交年份未控制。')}${panel('hQuality','房屋质量与售价','总体质量1–10档；为观察关联，不是因果效应。')}</div>
      ${C.panel('面积与成交价格','筛选只影响本散点图及样本数；保留全部房屋，不自动剔除离群点。',`<div class="rr-controls"><label>社区 <select id="hFilter"><option value="">全部社区</option>${d.neighborhoods.map(r=>`<option value="${C.esc(r.name)}">${C.esc(r.name)}</option>`).join('')}</select></label><span id="hCount" role="status"></span></div>${C.chartBox('hScatter')}`)}
      ${panel('hValidation','固定留出验证：真实售价与预测售价','美元/套；虚线为预测=真实。模型未使用验证集拟合插补器或编码器。')}
      ${C.panel('模型与基线',d.metrics.method,C.table(['方法','验证样本','MAE（美元）','RMSLE'],[["随机森林",d.metrics.validation_count,C.fmt(d.metrics.mae_usd),C.fmt(d.metrics.rmsle,4)],["训练集售价中位数",d.metrics.validation_count,C.fmt(d.metrics.baseline_mae_usd),C.fmt(d.metrics.baseline_rmsle,4)]]))}
      ${C.panel('社区样本量与售价','完整社区列表；小样本中位数可能不稳定。',C.table(['社区','房屋数','售价中位数（美元）'],d.neighborhoods.map(r=>[C.esc(r.name),C.fmt(r.count),C.fmt(r.median_price)])))}`;
    } else if(slug==='movies') {
      body=`${C.panel('按类型观察票房与评分','筛选只影响下方散点图和电影表；类型为多标签，一部电影可归入多个类型。',`<div class="rr-controls"><label>类型 <select id="mFilter"><option value="">全部类型</option>${d.genres.map(r=>`<option value="${C.esc(r.tag)}">${C.esc(r.tag)}（${r.count}部）</option>`).join('')}</select></label><span id="mCount" role="status"></span></div>${C.chartBox('mScatter')}`)}
      <div class="grid-2">${panel('mGenre','类型样本量','完整计数；多类型电影重复计入，因此各类型数量不能相加当电影总数。')}${panel('mRevenue','样本中累计票房Top 10','按各影片自己的数据截止日期统计，不是实时票房榜。')}</div>
      ${C.panel('评分与票房的相关性','Pearson相关：评分对log(1+累计票房亿元)。不等于因果关系，也不代表评分平台的优劣。',C.table(['评分平台','有效样本','相关系数'],d.correlations.map(r=>[r.name==='douban'?'豆瓣':'猫眼',r.count,C.fmt(r.pearson_log_revenue,3)])))}
      ${C.panel('电影明细','票房单位为亿元；保留各影片截止日期，避免混淆观察时间。','<div id="mTable"></div>')}`;
    } else {
      body=`<div class="grid-2">${panel('sAttributes','品牌属性认同率','每项有效Yes/No回答中，Yes的占比（%）。')}${panel('sSegments','按好感分描述消费者','正向>0，中立=0，负向<0；这是规则分组，不是聚类结果。')}</div>
      <div class="grid-2">${panel('sVisit','到访频率与平均好感','各频率组平均好感分，范围−5至+5；仅反映关联。')}${panel('sAge','不同年龄段平均好感','按年龄分组，不代表中国或全球消费者总体。')}</div>
      ${C.panel('各组品牌认知','选择一个好感组，比较其属性认同率；分组本身使用好感分，不能据此证明属性造成好感。',`<div class="rr-controls"><label>好感组 <select id="sFilter">${d.profiles.map(r=>`<option value="${C.esc(r.name)}">${C.esc(r.name)}（${r.count}人）</option>`).join('')}</select></label></div>${C.chartBox('sProfile')}`)}
      ${C.panel('到访频率样本量','同时查看样本量，避免只看组间均值。',C.table(['到访频率','样本数','平均好感'],d.visits.map(r=>[r.name,C.fmt(r.count),C.fmt(r.mean_like,2)])))}`;
    }
    app.innerHTML=`<section class="page-hero"><div class="eyebrow">${en}</div><h1>${title}</h1><p>${desc}</p><p>${C.esc(d.source)}${sourceLink}</p></section>${C.kpis(kpis)}${body}${C.panel('结论与数据说明','基于当前历史样本计算；不将样本结论外推为整体市场事实。',C.insights(d.insights.map(C.esc))+C.notes(d.data_notes.map(C.esc)))}`;
    if(slug==='housing') {
      bar('hNeighborhood',d.neighborhoods,'median_price','美元/套'); bar('hQuality',d.quality,'median_price','美元/套');
      const chart=C.chart('hScatter',{});
      function update(){const name=C.el('hFilter').value,rows=d.scatter.filter(r=>!name||r.neighborhood===name);C.el('hCount').textContent=`${rows.length} 套房屋`;
        chart.setOption({tooltip:{trigger:'item',formatter:p=>`房屋 ${C.esc(p.data[2])}<br>面积 ${C.fmt(p.data[0])} 平方英尺<br>售价 $${C.fmt(p.data[1])}`},xAxis:C.valAxis({name:'地上居住面积（平方英尺）'}),yAxis:C.valAxis({name:'售价（美元）'}),series:[{type:'scatter',symbolSize:6,data:rows.map(r=>[r.area_sqft,r.price,r.id])}]},true);}
      C.el('hFilter').addEventListener('change',update);update();
      const max=Math.max(...d.validation.flatMap(r=>[r.actual,r.predicted]));
      C.chart('hValidation',{tooltip:{trigger:'item'},xAxis:C.valAxis({name:'真实售价（美元）'}),yAxis:C.valAxis({name:'预测售价（美元）'}),series:[{name:'验证房屋',type:'scatter',symbolSize:6,data:d.validation.map(r=>[r.actual,r.predicted])},{name:'理想预测',type:'line',showSymbol:false,lineStyle:{type:'dashed'},data:[[0,0],[max,max]]}]});
    } else if(slug==='movies') {
      const scatter=C.chart('mScatter',{});
      function update(){const genre=C.el('mFilter').value,rows=d.movies.filter(r=>!genre||r.genre.split(',').map(s=>s.trim()).includes(genre));C.el('mCount').textContent=`${rows.length} 部电影`;
        scatter.setOption({legend:{data:['豆瓣','猫眼']},tooltip:{trigger:'item',formatter:p=>`${C.esc(p.data[2])}<br>${C.esc(p.seriesName)} ${C.fmt(p.data[0],1)}<br>票房 ${C.fmt(p.data[1],2)} 亿元`},xAxis:C.valAxis({name:'评分（0–10）',min:0,max:10}),yAxis:C.valAxis({name:'累计票房（亿元）'}),series:['douban','maoyan'].map((key,i)=>({name:i?'猫眼':'豆瓣',type:'scatter',symbolSize:8,data:rows.filter(r=>r[key]!==null).map(r=>[r[key],r.revenue_yi,r.name])}))},true);
        C.el('mTable').innerHTML=C.table(['片名','类型','票房（亿元）','豆瓣','猫眼','截止日期'],rows.map(r=>[C.esc(r.name),C.esc(r.genre),C.fmt(r.revenue_yi,2),C.fmt(r.douban,1),C.fmt(r.maoyan,1),C.esc(r.snapshot)]));}
      C.el('mFilter').addEventListener('change',update);update();
      bar('mGenre',d.genres.map(r=>({name:r.tag,count:r.count})),'count','电影数');bar('mRevenue',d.movies.slice(0,10),'revenue_yi','亿元');
    } else {
      bar('sAttributes',d.attributes,'yes_pct','认同率（%）');bar('sVisit',d.visits,'mean_like','好感分');bar('sAge',d.ages,'mean_like','好感分');
      C.chart('sSegments',{tooltip:{trigger:'item'},legend:{bottom:0},series:[{type:'pie',radius:['40%','70%'],data:d.segments.map(r=>({name:r.name,value:r.count})),label:{formatter:'{b}\n{c}人（{d}%）'}}]});
      const profile=C.chart('sProfile',{}),keys=['yummy','convenient','spicy','fattening','greasy','fast','cheap','tasty','expensive','healthy','disgusting'];
      function update(){const row=d.profiles.find(r=>r.name===C.el('sFilter').value);profile.setOption({tooltip:{trigger:'axis'},xAxis:C.catAxis(d.attributes.map(r=>r.name)),yAxis:C.valAxis({name:'认同率（%）',min:0,max:100}),series:[{name:row.name,type:'bar',data:keys.map(k=>row[k])}]},true);}
      C.el('sFilter').addEventListener('change',update);update();
    }
  } catch(err){C.error(app,err);}
})();
