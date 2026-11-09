/* 每个模块的业务问题、证据和后续验证，共用统一分析接口。 */
(() => {
  const app=document.getElementById('app');
  if(!app)return;
  const slug=location.pathname.split('/').pop();
  let started=false;
  async function insert(){
    const head=app.querySelector('.page-head,.page-hero');
    if(!head||started)return;
    started=true;
    try {
      const d=await C.get(`/api/brief/${slug}`);
      const node=document.createElement('section');node.className='panel business-brief';
      node.innerHTML=`<div class="panel-head"><div><h2>本模块要解决什么问题？</h2><p>${C.esc(d.question)}</p></div></div>
        ${C.insights([['数据证据',d.evidence],['如何理解',d.interpretation],['建议下一步',d.action],['怎么验证',d.verification]].map(([label,text])=>`<b>${C.esc(label)}</b> · ${C.esc(text)}`))}
        ${d.detail?`<h3>${C.esc(d.detail.title)}</h3>${C.table(d.detail.headers,d.detail.rows.map(row=>row.map(C.esc)))}`:''}
        <p class="hint">${C.esc(d.status)}</p>`;
      head.after(node);
    }catch(e){started=false;console.warn('业务解读暂不可用',e.message);}
  }
  new MutationObserver(insert).observe(app,{childList:true});insert();
})();
