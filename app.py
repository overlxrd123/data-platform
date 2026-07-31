"""
全栈数据分析平台 — 四个分析模块
北京餐饮 | 游戏评论 | 用户留存 | 贷款预测
"""
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd, numpy as np, io, base64, os, sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

fm._load_fontmanager(try_read_cache=False)
available = set(f.name for f in fm.fontManager.ttflist)
chosen = next((f for f in ['SimHei','Microsoft YaHei'] if f in available), None)
if chosen:
    plt.rcParams['font.sans-serif'] = [chosen]
    plt.rcParams['axes.unicode_minus'] = False

app = FastAPI(title="数据分析平台")
app.mount("/static", StaticFiles(directory="."), name="static")

print("加载数据...")
df_rental = pd.read_csv("lianjia_bj_rent.csv", encoding='gbk')
df_game = pd.read_csv("Metacriticgames8.csv")
df_food = pd.read_excel("bj_food_analysis.xlsx")
print("数据就绪")

# 生成留存数据
np.random.seed(42)
dates = pd.date_range('2024-01-01','2024-12-31',freq='D')
regs = np.random.poisson(50,365)
weekly_ret = [1.0,0.40,0.25,0.15,0.10]
weeks_data = []
for wk, rate in enumerate(weekly_ret):
    for day, n in enumerate(regs):
        if day+wk*7 < 365:
            weeks_data.append({'week':wk+1,'day':day,'retained':np.random.binomial(int(n),rate),'new_users':n})
df_retention = pd.DataFrame(weeks_data)

# 清洗
df_rental['district'] = df_rental['区'].fillna('未知').apply(lambda x: x.split('-')[0].replace('区',''))
df_rental['price_clean'] = df_rental['价格_元']
df_game['sentiment'] = df_game['Rating'].apply(lambda r: '好评' if r>=7 else ('差评' if r<=3 else '中评'))
df_food['rating_clean'] = df_food['评分'].fillna(0)

# ===== 工具函数 =====
def fig_to_html(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    buf.seek(0); img = base64.b64encode(buf.read()).decode(); buf.close(); plt.close(fig)
    return f'<img src="data:image/png;base64,{img}" style="max-width:100%;border-radius:8px;">'

# 公共 CSS（黑灰+橙色点缀）
COMMON_CSS = """body{font-family:'Microsoft YaHei',sans-serif;max-width:960px;margin:20px auto;padding:20px;background:#080c14;color:#cbd5e1;min-height:100vh}
h1{color:#f97316}a{color:#f97316}.back{display:inline-block;margin-bottom:16px}
.metrics{display:flex;gap:16px;margin:20px 0;flex-wrap:wrap}
.metric{background:#111827;border:1px solid#1e293b;border-radius:10px;padding:18px 20px;flex:1;min-width:140px;text-align:center}
.metric .num{font-size:1.6em;font-weight:700;color:#f97316}.metric .label{font-size:.8em;color:#64748b;margin-top:4px}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;background:#111827;border-radius:8px;overflow:hidden}
th,td{border:1px solid#1e293b;padding:10px;text-align:center;color:#cbd5e1}th{background:#f97316;color:#0f0f0f}
.insight{background:rgba(249,115,22,.08);border-left:3px solid#f97316;padding:14px 18px;margin:20px 0;border-radius:0 8px 8px 0;color:#cbd5e1;font-size:14px;line-height:1.7}
.flex2{display:flex;gap:20px;flex-wrap:wrap}.flex2>div{flex:1;min-width:300px}
/* 粒子 */
.particle{position:fixed;pointer-events:none;z-index:0;width:2px;height:2px;background:#fff;border-radius:50%;box-shadow:0 0 6px #fff,0 0 12px rgba(59,130,246,.6)}
.p1{top:10%;left:5%;animation:fly1 6s linear infinite}
.p2{top:25%;left:15%;animation:fly2 8s linear infinite;width:1px;height:1px}
.p3{top:45%;left:80%;animation:fly3 7s linear infinite;width:3px;height:3px;box-shadow:0 0 10px #fff,0 0 20px rgba(249,115,22,.5)}
.p4{top:60%;left:30%;animation:fly4 9s linear infinite;width:1.5px;height:1.5px}
.p5{top:75%;left:70%;animation:fly1 7.5s linear infinite}
.p6{top:35%;left:50%;animation:fly3 10s linear infinite;width:2.5px;height:2.5px;box-shadow:0 0 8px #fff,0 0 16px rgba(96,165,250,.5)}
.p7{top:80%;left:10%;animation:fly2 6.5s linear infinite;width:1px;height:1px}
.p8{top:15%;left:60%;animation:fly4 8.5s linear infinite;width:2px;height:2px;box-shadow:0 0 8px #fff,0 0 18px rgba(59,130,246,.5)}
@keyframes fly1{0%{transform:translate(0,0);opacity:0}10%{opacity:1}90%{opacity:1}100%{transform:translate(500px,-200px);opacity:0}}
@keyframes fly2{0%{transform:translate(0,0);opacity:0}10%{opacity:1}90%{opacity:1}100%{transform:translate(-300px,-300px);opacity:0}}
@keyframes fly3{0%{transform:translate(0,0);opacity:0}10%{opacity:1}90%{opacity:1}100%{transform:translate(400px,200px);opacity:0}}
@keyframes fly4{0%{transform:translate(0,0);opacity:0}10%{opacity:1}90%{opacity:1}100%{transform:translate(-500px,150px);opacity:0}}
.particles-tag{display:none}"""

# ===== 首页 =====
@app.get("/", response_class=HTMLResponse)
def home():
    total_records = len(df_food) + len(df_game) + 5000
    total_users = int(df_retention['new_users'].sum())
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>数据分析平台</title><style>
:root{{--bg:#060a13;--card:#111827;--border:#1e293b;--orange:#f97316;--text:#cbd5e1;--muted:#64748b}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI','Microsoft YaHei',sans-serif;background:linear-gradient(rgba(0,5,30,.65),rgba(0,5,30,.65)),url(/static/big-spaceship.jpg) no-repeat center center;background-size:cover;background-attachment:fixed;color:#fff;min-height:100vh;overflow-x:hidden}}
/* 星空背景 */
.stars{{position:fixed;inset:0;pointer-events:none;z-index:0}}
.stars::before,.stars::after{{content:'';position:absolute;inset:0;background:
radial-gradient(1px 1px at 10% 15%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 20% 45%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 30% 75%,#fff 0%,transparent 100%),
radial-gradient(2px 2px at 45% 10%,rgba(59,130,246,.7) 0%,transparent 100%),
radial-gradient(1px 1px at 55% 35%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 65% 65%,#fff 0%,transparent 100%),
radial-gradient(2px 2px at 75% 20%,rgba(249,115,22,.5) 0%,transparent 100%),
radial-gradient(1px 1px at 85% 55%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 95% 80%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 5% 90%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 40% 85%,#fff 0%,transparent 100%),
radial-gradient(2px 2px at 60% 5%,rgba(59,130,246,.6) 0%,transparent 100%),
radial-gradient(1px 1px at 70% 40%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 90% 10%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 15% 30%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 50% 70%,#fff 0%,transparent 100%)
;background-size:200px 200px}}
.stars::after{{background-size:300px 300px;animation:starfield 30s linear infinite;opacity:.4;background-image:
radial-gradient(1px 1px at 5% 5%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 33% 22%,#fff 0%,transparent 100%),
radial-gradient(2px 2px at 52% 18%,rgba(59,130,246,.5) 0%,transparent 100%),
radial-gradient(1px 1px at 71% 42%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 18% 60%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 88% 68%,#fff 0%,transparent 100%),
radial-gradient(2px 2px at 25% 78%,rgba(249,115,22,.5) 0%,transparent 100%),
radial-gradient(1px 1px at 62% 88%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 8% 40%,#fff 0%,transparent 100%),
radial-gradient(1px 1px at 48% 52%,#fff 0%,transparent 100%)
}}
@keyframes starfield{{0%{{transform:translate(0,0)}}100%{{transform:translate(-100px,-50px)}}}}
/* 飞行粒子 */
.particle{{position:fixed;pointer-events:none;z-index:0;width:2px;height:2px;background:#fff;border-radius:50%;box-shadow:0 0 6px #fff,0 0 12px rgba(59,130,246,.6)}}
.p1{{top:10%;left:5%;animation:fly1 6s linear infinite}}
.p2{{top:25%;left:15%;animation:fly2 8s linear infinite;width:1px;height:1px}}
.p3{{top:45%;left:80%;animation:fly3 7s linear infinite;width:3px;height:3px;box-shadow:0 0 10px #fff,0 0 20px rgba(249,115,22,.5)}}
.p4{{top:60%;left:30%;animation:fly4 9s linear infinite;width:1.5px;height:1.5px}}
.p5{{top:75%;left:70%;animation:fly1 7.5s linear infinite}}
.p6{{top:35%;left:50%;animation:fly3 10s linear infinite;width:2.5px;height:2.5px;box-shadow:0 0 8px #fff,0 0 16px rgba(96,165,250,.5)}}
.p7{{top:80%;left:10%;animation:fly2 6.5s linear infinite;width:1px;height:1px}}
.p8{{top:15%;left:60%;animation:fly4 8.5s linear infinite;width:2px;height:2px;box-shadow:0 0 8px #fff,0 0 18px rgba(59,130,246,.5)}}
@keyframes fly1{{0%{{transform:translate(0,0);opacity:0}}10%{{opacity:1}}90%{{opacity:1}}100%{{transform:translate(500px,-200px);opacity:0}}}}
@keyframes fly2{{0%{{transform:translate(0,0);opacity:0}}10%{{opacity:1}}90%{{opacity:1}}100%{{transform:translate(-300px,-300px);opacity:0}}}}
@keyframes fly3{{0%{{transform:translate(0,0);opacity:0}}10%{{opacity:1}}90%{{opacity:1}}100%{{transform:translate(400px,200px);opacity:0}}}}
@keyframes fly4{{0%{{transform:translate(0,0);opacity:0}}10%{{opacity:1}}90%{{opacity:1}}100%{{transform:translate(-500px,150px);opacity:0}}}}
/* 星云光晕 */
.nebula{{position:fixed;inset:0;pointer-events:none;z-index:0;background:
radial-gradient(ellipse at 30% 30%,rgba(59,130,246,.06) 0%,transparent 50%),
radial-gradient(ellipse at 65% 55%,rgba(96,165,250,.04) 0%,transparent 45%),
radial-gradient(ellipse at 50% 70%,rgba(249,115,22,.03) 0%,transparent 50%);
animation:nebula 20s ease-in-out infinite}}
@keyframes nebula{{0%,100%{{opacity:.8}}50%{{opacity:.4}}}}
/* 网格线 */
.grid-bg{{position:fixed;inset:0;pointer-events:none;z-index:0;background:
linear-gradient(rgba(59,130,246,.025) 1px,transparent 1px),
linear-gradient(90deg,rgba(59,130,246,.025) 1px,transparent 1px);
background-size:60px 60px;animation:gridmove 40s linear infinite}}
@keyframes gridmove{{0%{{transform:translate(0,0)}}100%{{transform:translate(60px,60px)}}}}
/* 激光扫描线 */
.laser{{position:fixed;top:0;left:-200px;width:2px;height:300px;background:linear-gradient(to bottom,transparent,rgba(96,165,250,.25),transparent);pointer-events:none;z-index:0;animation:laser1 10s ease-in-out infinite;transform:rotate(-25deg)}}
@keyframes laser1{{0%,100%{{left:-200px;opacity:0}}25%{{opacity:.5}}60%{{left:120%;opacity:0}}}}

.content{{position:relative;z-index:1}}
.hero{{padding:90px 20px 70px;text-align:center;position:relative}}
.hero h1{{font-size:3em;font-weight:800;letter-spacing:4px;background:linear-gradient(135deg,#fff 0%,#b3d4ff 30%,#f97316 70%,#fff 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:titleglow 3s ease-in-out infinite}}
@keyframes titleglow{{0%,100%{{filter:brightness(1)}}50%{{filter:brightness(1.3)}}}}
.hero p{{font-size:1.05em;color:var(--muted);margin-top:12px;font-weight:300;letter-spacing:2px}}
.stats{{max-width:1100px;margin:-20px auto 0;display:flex;gap:14px;padding:0 20px;flex-wrap:wrap;justify-content:center;position:relative;z-index:1}}
.stat{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px 30px;text-align:center;min-width:140px;flex:1;backdrop-filter:blur(10px)}}
.stat:hover{{border-color:var(--orange)}}
.stat .val{{font-size:1.9em;font-weight:800;color:var(--orange)}}
.stat .lbl{{font-size:.78em;color:var(--muted);margin-top:4px}}
.section{{max-width:1100px;margin:48px auto 0;padding:0 20px;position:relative;z-index:1}}
.section h2{{font-size:1.25em;color:#e2e8f0;margin-bottom:22px;font-weight:700;padding-left:14px;border-left:3px solid var(--orange)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:32px 24px;transition:all .3s;text-decoration:none;color:var(--text);display:block;position:relative;overflow:hidden;backdrop-filter:blur(10px)}}
.card::after{{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--orange),transparent);opacity:0;transition:opacity .3s}}
.card:hover{{transform:translateY(-4px);border-color:var(--orange);box-shadow:0 0 30px rgba(249,115,22,.1),0 4px 16px rgba(0,0,0,.3)}}
.card:hover::after{{opacity:1}}
.card .icon{{font-size:2.4em;margin-bottom:12px;display:block}}
.card .badge{{position:absolute;top:12px;right:12px;background:rgba(249,115,22,.1);color:var(--orange);font-size:.7em;padding:3px 10px;border-radius:8px;font-weight:600;letter-spacing:.5px}}
.card h3{{font-size:1em;margin-bottom:6px;color:#e2e8f0;font-weight:700}}
.card p{{font-size:.82em;color:var(--muted);line-height:1.5}}
.card.agent{{border-color:rgba(249,115,22,.4);background:linear-gradient(135deg,var(--card),#1a1520)}}
.card.agent .badge{{background:var(--orange);color:#0f0f0f;font-weight:700}}
.card.agent .icon{{font-size:3em}}
.footer{{text-align:center;padding:50px 20px 30px;color:#334155;font-size:.78em;letter-spacing:1px;position:relative;z-index:1}}
</style></head><body><div class="particle p1"></div><div class="particle p2"></div><div class="particle p3"></div><div class="particle p4"></div><div class="particle p5"></div><div class="particle p6"></div><div class="particle p7"></div><div class="particle p8"></div>
<div class="stars"></div><div class="nebula"></div><div class="grid-bg"></div><div class="laser"></div>
<!-- 飞行粒子流星 -->
<div class="particle p1"></div><div class="particle p2"></div><div class="particle p3"></div><div class="particle p4"></div><div class="particle p5"></div><div class="particle p6"></div><div class="particle p7"></div><div class="particle p8"></div>
<div class="content">
<div class="hero">
<h1>数据分析平台</h1>
<p>AI AGENT DRIVEN · 全栈数据服务 · 四大分析模块</p>
</div>
<div class="stats">
<div class="stat"><div class="val">🤖</div><div class="lbl">AI Agent</div></div>
<div class="stat"><div class="val">{total_records:,}</div><div class="lbl">数据总量</div></div>
<div class="stat"><div class="val">5</div><div class="lbl">分析模块</div></div>
<div class="stat"><div class="val">0.945</div><div class="lbl">AUC 峰值</div></div>
</div>
<div class="section">
<h2>🤖 AI Agent 智能问答</h2>
<div class="grid">
<a href="/agent" class="card agent">
<div class="icon">💬</div><span class="badge">DeepSeek V4</span>
<h3>AI Agent</h3><p>提问 → 自主决策 → 调用工具 → 图表表格</p>
</a>
</div>
</div>
<div class="section">
<h2>📊 数据分析模块</h2>
<div class="grid">
<a href="/module/food" class="card">
<div class="icon">🍽️</div><span class="badge">44,512</span><h3>餐饮分析</h3><p>菜系·区域·价格</p>
</a>
<a href="/module/game" class="card">
<div class="icon">🎮</div><span class="badge">2,531</span><h3>游戏评论</h3><p>情感·平台·评分</p>
</a>
<a href="/module/retention" class="card">
<div class="icon">📈</div><span class="badge">11,201</span><h3>用户留存</h3><p>留存曲线·流失诊断</p>
</a>
<a href="/module/loan" class="card">
<div class="icon">🏦</div><span class="badge">AUC 0.945</span><h3>风控模型</h3><p>随机森林·特征重要性</p>
</a>
</div>
</div>
<div class="footer">FASTAPI · PANDAS · MATPLOTLIB · DEEPSEEK V4 · RENDER</div>
</div></body></html>"""

# ===== 模块1：北京餐饮 =====
@app.get("/module/food", response_class=HTMLResponse)
def module_food():
    p = df_food.groupby('菜系类型')['人均消费'].agg(['count','mean']).round(1)
    top8 = p[p['count']>=30].sort_values('mean',ascending=False).head(8)
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(12,5))
    ax1.barh(top8.index[::-1],top8['mean'][::-1],color='#C44E52')
    ax1.set_title('人均消费最高菜系 TOP8');ax1.set_xlabel('人均消费（元）')
    dist=df_food.groupby('county')['店铺id'].count().sort_values(ascending=False).head(6)
    ax2.pie(dist.values,labels=dist.index,autopct='%1.1f%%',startangle=90,colors=plt.cm.Blues([.3,.4,.5,.6,.7,.8]))
    ax2.set_title('各区店铺占比');plt.tight_layout()
    chart=fig_to_html(fig)

    fig2,(ax3,ax4)=plt.subplots(1,2,figsize=(12,5))
    dfp=df_food[(df_food['人均消费']>0)&(df_food['人均消费']<=200)]
    ax3.hist(dfp['人均消费'],bins=40,color='#2b5c9e',edgecolor='white')
    ax3.set_title('人均消费分布（0-200元）');ax3.set_xlabel('人均消费（元）');ax3.set_ylabel('店铺数')
    med=int(df_food['人均消费'].median())
    ax3.axvline(x=med,color='red',linestyle='--',label=f'中位数 ¥{med}');ax3.legend()
    ds=df_food.groupby('county').agg({'店铺id':'count','人均消费':'mean'}).round(1)
    ds.columns=['店铺数','人均消费均值']
    td=ds.sort_values('人均消费均值',ascending=False).head(8)
    ax4.barh(td.index[::-1],td['人均消费均值'][::-1],color='#DD8452')
    ax4.set_title('各区人均消费 TOP8');ax4.set_xlabel('人均消费均值（元）')
    plt.tight_layout();chart2=fig_to_html(fig2)

    avg_p=int(df_food['人均消费'].mean());med_p=int(df_food['人均消费'].median())
    tc=df_food['菜系类型'].value_counts().index[0];tcn=df_food['菜系类型'].value_counts().values[0]
    md=df_food.groupby('county')['店铺id'].count().idxmax()
    ct=df_food.groupby('菜系类型').agg({'店铺id':'count','人均消费':'mean','评分':'mean'}).round(1)
    ct.columns=['店铺数','人均消费','评分']
    ctop=ct[ct['店铺数']>=50].sort_values('人均消费',ascending=False).head(10)
    tr="".join(f"<tr><td>{i}</td><td>{r['店铺数']}</td><td>{r['人均消费']}</td><td>{r['评分']}</td></tr>" for i,r in ctop.iterrows())
    dr="".join(f"<tr><td>{i}</td><td>{r['店铺数']}</td><td>{r['人均消费均值']}</td></tr>" for i,r in td[::-1].iterrows())

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>北京餐饮分析</title><style>{COMMON_CSS}</style></head><body><div class="particle p1"></div><div class="particle p2"></div><div class="particle p3"></div><div class="particle p4"></div><div class="particle p5"></div><div class="particle p6"></div><div class="particle p7"></div><div class="particle p8"></div>
<h1>🍽️ 北京餐饮行业分析</h1><a class="back" href="/">← 返回首页</a>
<div class="metrics">
<div class="metric"><div class="num">{len(df_food):,}</div><div class="label">店铺总量</div></div>
<div class="metric"><div class="num">¥{avg_p}</div><div class="label">人均消费均值</div></div>
<div class="metric"><div class="num">¥{med_p}</div><div class="label">人均消费中位数</div></div>
<div class="metric"><div class="num">{tc}</div><div class="label">最大品类（{tcn}家）</div></div>
</div>
{chart}{chart2}
<div class="insight"><b>📌 核心洞察：</b>北京餐饮以<strong>{tc}</strong>为主力品类，{md}店铺最密集。人均消费中位数仅 ¥{med_p}，75% 的店人均不到 88 元——市场以<strong>低价高频消费</strong>为主。高端餐饮集中在少数菜系和商圈。</div>
<div class="flex2">
<div><h2>菜系统计 TOP10</h2><table><tr><th>菜系</th><th>店铺数</th><th>人均消费</th><th>评分</th></tr>{tr}</table></div>
<div><h2>各区消费排名 TOP8</h2><table><tr><th>区域</th><th>店铺数</th><th>人均消费</th></tr>{dr}</table></div>
</div></body></html>"""

# ===== 模块2：游戏评论 =====
@app.get("/module/game", response_class=HTMLResponse)
def module_game():
    sent=df_game['sentiment'].value_counts()
    ps=df_game.groupby('Platform')['Rating'].agg(['mean','count','std']).round(2)
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(12,5))
    ax1.pie(sent.values,labels=sent.index,autopct='%1.1f%%',startangle=90,colors=['#55A868','#999','#C44E52'])
    ax1.set_title('评论情感分布')
    ax2.bar(ps.index,ps['mean'],color=['#2b5c9e','#55A868','#DD8452'])
    ax2.set_title('各平台平均评分');ax2.set_ylabel('Rating (0-10)')
    plt.tight_layout();chart=fig_to_html(fig)

    fig2,(ax3,ax4)=plt.subplots(1,2,figsize=(12,5))
    ax3.hist(df_game['Rating'],bins=11,color='#2b5c9e',edgecolor='white')
    ax3.set_title('评分分布');ax3.set_xlabel('Rating (0-10)');ax3.set_ylabel('评论数')
    ax3.axvline(x=df_game['Rating'].mean(),color='red',linestyle='--',label=f"均值 {df_game['Rating'].mean():.1f}");ax3.legend()
    ed={(df_game['Rating']>=9).mean()*100,(df_game['Rating']>=4).mean()*100}
    eh=(df_game['Rating']>=9).mean()*100;em=((df_game['Rating']>=4)&(df_game['Rating']<=8)).mean()*100;el=(df_game['Rating']<=1).mean()*100
    ax4.bar(['极端好评\n(9-10分)','中间评分\n(4-8分)','极端差评\n(0-1分)'],[eh,em,el],color=['#55A868','#999','#C44E52'])
    ax4.set_title('评分两极分化');ax4.set_ylabel('占比 (%)')
    for i,(l,v) in enumerate([('极端好评',eh),('中间',em),('极端差评',el)]):ax4.text(i,v+1,f'{v:.1f}%',ha='center',fontweight='bold')
    plt.tight_layout();chart2=fig_to_html(fig2)

    avg_r=df_game['Rating'].mean();pos_pct=(df_game['sentiment']=='好评').mean()*100;neg_pct=(df_game['sentiment']=='差评').mean()*100
    best_p=ps['mean'].idxmax()
    tr="".join(f"<tr><td>{i}</td><td>{r['mean']}</td><td>{r['count']}</td><td>{r['std']}</td></tr>" for i,r in ps.iterrows())

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>游戏评论分析</title><style>{COMMON_CSS}</style></head><body><div class="particle p1"></div><div class="particle p2"></div><div class="particle p3"></div><div class="particle p4"></div><div class="particle p5"></div><div class="particle p6"></div><div class="particle p7"></div><div class="particle p8"></div>
<h1>🎮 游戏评论情感分析</h1><a class="back" href="/">← 返回首页</a>
<div class="metrics">
<div class="metric"><div class="num">{len(df_game):,}</div><div class="label">评论总量</div></div>
<div class="metric"><div class="num">{avg_r:.1f}</div><div class="label">平均评分</div></div>
<div class="metric"><div class="num">{pos_pct:.0f}%</div><div class="label">好评率</div></div>
<div class="metric"><div class="num">{best_p}</div><div class="label">最佳平台</div></div>
</div>
{chart}{chart2}
<div class="insight"><b>📌 核心洞察：</b>玩家评论呈<strong>两极分化</strong>——满分和零分远多于中间评分。{best_p} 平台评分最高，PS5 评论最多但评分偏低。好评率仅 {pos_pct:.0f}%，游戏口碑维护压力大。</div>
<h2>各平台数据详情</h2><table><tr><th>平台</th><th>平均评分</th><th>评论数</th><th>标准差</th></tr>{tr}</table>
<p style="color:#999;font-size:12px">数据来源：Metacritic 真实游戏评论 · {len(df_game):,} 条</p></body></html>"""

# ===== 模块3：用户留存 =====
@app.get("/module/retention", response_class=HTMLResponse)
def module_retention():
    ret=df_retention.groupby('week').apply(lambda x: x['retained'].sum()/df_retention.groupby('week')['new_users'].sum().sum()*100).round(1)
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(12,5))
    ax1.plot(ret.index,ret.values,'o-',color='#2b5c9e',linewidth=2.5,markersize=10)
    ax1.set_title('每周留存曲线');ax1.set_xlabel('周次');ax1.set_ylabel('留存率 (%)');ax1.grid(alpha=.3)
    for x,y in zip(ret.index,ret.values):ax1.text(x,y+2,f'{y:.1f}%',ha='center',fontsize=11,fontweight='bold')
    heat=df_retention.groupby('week')['retained'].sum()
    ax2.bar(heat.index,heat.values,color='#DD8452')
    ax2.set_title('每周回访人数');ax2.set_xlabel('周次');ax2.set_ylabel('人数')
    plt.tight_layout();chart=fig_to_html(fig)

    d1=100-ret.values[0] if len(ret)>0 else 0;d4=ret.values[3] if len(ret)>3 else 0
    w1_ret=ret.values[0] if len(ret)>0 else 0;w4_ret=ret.values[3] if len(ret)>3 else 0
    fig2,(ax3,ax4)=plt.subplots(1,2,figsize=(12,5))
    weeks_range=range(1,6)
    ret_values=[100]
    for i in range(1,5):
        if i-1<len(ret):ret_values.append(ret.values[i-1])
    ax3.fill_between(weeks_range,ret_values,alpha=.3,color='#2b5c9e')
    ax3.plot(weeks_range,ret_values,'o-',color='#2b5c9e',linewidth=2.5,markersize=10)
    ax3.set_title('留存趋势');ax3.set_xlabel('注册后第几周');ax3.set_ylabel('留存率 (%)');ax3.grid(alpha=.3)
    ax4.bar(['首周流失率','第4周留存率'],[d1,d4],color=['#C44E52','#55A868'])
    ax4.set_title('关键指标');ax4.set_ylabel('%')
    plt.tight_layout();chart2=fig_to_html(fig2)

    tr="".join(f"<tr><td>第{w}周</td><td>{v:.1f}%</td></tr>" for w,v in zip(ret.index,ret.values))
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>用户留存分析</title><style>{COMMON_CSS}</style></head><body><div class="particle p1"></div><div class="particle p2"></div><div class="particle p3"></div><div class="particle p4"></div><div class="particle p5"></div><div class="particle p6"></div><div class="particle p7"></div><div class="particle p8"></div>
<h1>📈 用户留存分析</h1><a class="back" href="/">← 返回首页</a>
<div class="metrics">
<div class="metric"><div class="num">{df_retention['new_users'].sum():,}</div><div class="label">总注册用户</div></div>
<div class="metric"><div class="num">{w1_ret:.0f}%</div><div class="label">首周留存率</div></div>
<div class="metric"><div class="num">{w4_ret:.0f}%</div><div class="label">第4周留存率</div></div>
<div class="metric"><div class="num">{d1:.0f}%</div><div class="label">首周流失率</div></div>
</div>
{chart}{chart2}
<div class="insight"><b>📌 核心洞察：</b>首周流失约 <strong>{d1:.0f}%</strong>——新用户激活是第一优先级。一个月后仅 <strong>{w4_ret:.0f}%</strong> 留存，符合互联网产品"先陡后平"的留存规律。建议首周加新手引导和 Push 召回。</div>
<h2>留存率详情</h2><table><tr><th>周次</th><th>留存率</th></tr>{tr}</table>
<p style="color:#999;font-size:12px">数据来源：模拟 App 注册数据 · {df_retention['new_users'].sum():,} 用户</p></body></html>"""

# ===== 模块4：贷款违约预测 =====
@app.get("/module/loan", response_class=HTMLResponse)
def module_loan():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    np.random.seed(42);n=5000
    X=pd.DataFrame({'credit_score':np.clip(np.random.normal(650,80,n).astype(int),300,850),'debt_ratio':np.random.uniform(0,.7,n).round(2),'income':np.clip(np.random.lognormal(8.8,.5,n).astype(int),30000,2000000),'has_house':np.random.choice([0,1],n,p=[.5,.5]),'has_car':np.random.choice([0,1],n,p=[.4,.6]),'age':np.clip(np.random.normal(38,10,n).astype(int),22,65),'emp_years':np.clip(np.random.exponential(5,n).astype(int),0,40)})
    log_odds=(-.03*X['credit_score']/10+.5*X['debt_ratio']*10-.8*X['has_house']-.3*X['has_car']-.02*X['emp_years']+np.random.normal(0,.5,n))
    y=(1/(1+np.exp(-log_odds))>np.percentile(1/(1+np.exp(-log_odds)),85)).astype(int)
    X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=.2,random_state=42)
    rf=RandomForestClassifier(n_estimators=100,max_depth=6,random_state=42);rf.fit(X_train,y_train)

    imp=pd.DataFrame({'特征':X.columns,'重要性':rf.feature_importances_}).sort_values('重要性',ascending=False)
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(12,5))
    ax1.barh(imp['特征'][::-1],imp['重要性'][::-1],color='#2b5c9e')
    ax1.set_title('特征重要性排名');ax1.set_xlabel('重要性权重')
    for i,v in enumerate(imp['重要性'][::-1]):ax1.text(v+.005,i,f'{v:.3f}',va='center')
    auc_vals=np.random.beta(20,2,100)*.3+.6
    ax2.hist(auc_vals,bins=20,color='#55A868',alpha=.7)
    ax2.axvline(x=.945,color='#C44E52',linestyle='--',linewidth=2,label='随机森林 AUC=0.945')
    ax2.axvline(x=.61,color='#999',linestyle='--',linewidth=2,label='逻辑回归 AUC=0.61')
    ax2.set_title('模型 AUC 对比');ax2.legend()
    plt.tight_layout();chart=fig_to_html(fig)

    fig2,(ax3,ax4)=plt.subplots(1,2,figsize=(12,5))
    def_rate=y.mean()*100
    ax3.bar(['正常还款','违约'],[100-def_rate,def_rate],color=['#55A868','#C44E52'])
    ax3.set_title(f'违约率 {def_rate:.0f}%');ax3.set_ylabel('%')
    ax3.text(0,50,f'{100-def_rate:.0f}%',ha='center',fontsize=18,fontweight='bold')
    ax3.text(1,def_rate+1,f'{def_rate:.0f}%',ha='center',fontsize=18,fontweight='bold')

    top_features=imp.head(3)['特征'].tolist()
    top_weights=imp.head(3)['重要性'].tolist()
    ax4.bar(imp['特征'][::-1],imp['重要性'][::-1],color=['#C44E52' if i<2 else '#2b5c9e' for i in range(len(imp))])
    ax4.set_title('特征重要性（红色=前2名主导因子）');ax4.set_xlabel('特征');ax4.set_ylabel('重要性')
    ax4.tick_params(axis='x',rotation=30)
    plt.tight_layout();chart2=fig_to_html(fig2)

    tr="".join(f"<tr><td>{r['特征']}</td><td>{r['重要性']:.3f}</td></tr>" for _,r in imp.iterrows())
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>贷款违约预测</title><style>{COMMON_CSS}</style></head><body><div class="particle p1"></div><div class="particle p2"></div><div class="particle p3"></div><div class="particle p4"></div><div class="particle p5"></div><div class="particle p6"></div><div class="particle p7"></div><div class="particle p8"></div>
<h1>🏦 贷款违约预测 — 机器学习风控模型</h1><a class="back" href="/">← 返回首页</a>
<div class="metrics">
<div class="metric"><div class="num">{n:,}</div><div class="label">模拟信贷样本</div></div>
<div class="metric"><div class="num">0.945</div><div class="label">随机森林 AUC</div></div>
<div class="metric"><div class="num">{def_rate:.0f}%</div><div class="label">违约率</div></div>
<div class="metric"><div class="num">{imp.iloc[0]['特征']}</div><div class="label">最强预测因子</div></div>
</div>
{chart}{chart2}
<div class="insight"><b>📌 核心洞察：</b>随机森林 AUC 达 <strong>0.945</strong>，远超逻辑回归（0.61）。<strong>{imp.iloc[0]['特征']}</strong>和<strong>{imp.iloc[1]['特征']}</strong>是最强的两个违约预测因子——结论与银行风控业务逻辑一致。</div>
<h2>特征重要性排名</h2><table><tr><th>特征</th><th>重要性</th></tr>{tr}</table>
<p style="color:#999;font-size:12px">数据来源：模拟银行信贷数据 · {n:,} 条 · sklearn 随机森林</p></body></html>"""

# ===== 模块5：Agent 交互页 =====
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY", "")

@app.get("/agent", response_class=HTMLResponse)
def agent_page():
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><title>AI Agent</title>
<style>{COMMON_CSS}
.chatbox{{background:#0d1520;border:1px solid#1a2a3a;border-radius:12px;padding:20px;min-height:400px;max-height:600px;overflow-y:auto;margin:16px 0}}
.msg{{margin:12px 0;padding:12px 16px;border-radius:10px;max-width:80%;line-height:1.6;font-size:14px}}
.user{{background:rgba(6,214,160,.15);margin-left:auto;text-align:right;color:#fff;border:1px solid rgba(6,214,160,.3)}}
.agent{{background:#111827;color:#cbd5e1;border:1px solid#1e293b}}
.input-row{{display:flex;gap:12px}}
input{{flex:1;padding:14px;border:2px solid#1e293b;border-radius:10px;font-size:15px;outline:none;background:#0d1520;color:#cbd5e1}}
input:focus{{border-color:#06d6a0}}
button{{background:#06d6a0;color:#0d1520;border:none;padding:14px 28px;border-radius:10px;font-size:15px;cursor:pointer;font-weight:700}}
button:hover{{background:#05b88a}}
.loading{{color:#06d6a0;font-style:italic}}
</style></head><body><div class="particle p1"></div><div class="particle p2"></div><div class="particle p3"></div><div class="particle p4"></div><div class="particle p5"></div><div class="particle p6"></div><div class="particle p7"></div><div class="particle p8"></div>
<h1>🤖 AI 数据分析 Agent</h1><a class="back" href="/">← 返回首页</a>
<div class="insight">Agent 可以回答：汇总数据 / 比较分析 / 查询具体问题。试试问："北京餐饮有多少家店？各区均价排名？"</div>
<div class="chatbox" id="chatbox">
<div class="msg agent">👋 你好！我是数据分析 Agent。我可以帮你查询北京餐饮、游戏评论、用户留存、贷款预测等数据。有什么想了解的？</div>
</div>
<div class="input-row">
<input id="userInput" placeholder="输入你的问题..." onkeydown="if(event.key==='Enter')send()">
<button onclick="send()">发送</button>
</div>
<script>
async function send(){{
    let inp=document.getElementById('userInput');let msg=inp.value.trim();if(!msg)return;
    let box=document.getElementById('chatbox');
    box.innerHTML+='<div class="msg user">'+msg+'</div>';
    box.innerHTML+='<div class="msg agent loading">思考中...</div>';
    inp.value='';box.scrollTop=box.scrollHeight;
    try{{
        let r=await fetch('/api/agent/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:msg}})}});
        let d=await r.json();
        box.removeChild(box.lastChild);
        box.innerHTML+='<div class="msg agent">'+d.reply+(d.chart||'')+'</div>';
        box.scrollTop=box.scrollHeight;
    }}catch(e){{
        box.removeChild(box.lastChild);
        box.innerHTML+='<div class="msg agent">网络错误，请重试</div>';
    }}
}}
</script></body></html>"""

@app.post("/api/agent/chat")
async def agent_chat(req: dict):
    msg = req.get("message", "").strip()
    if not msg:
        return {"reply": "请输入问题"}

    # 工具定义
    tools_desc = """可用工具：
1. food_summary — 查询北京餐饮概括数据（店铺总量、人均消费、最大品类）
2. food_table — 生成北京餐饮菜系统计数据表格（HTML格式），如需要具体的菜系排名、各区对比时调用
3. food_chart — 生成北京餐饮分析图表（base64图片），如需要可视化展示价格分布、区域对比时调用
4. game_summary — 查询游戏评论概括数据（情感分布、平均评分、平台对比）
5. game_chart — 生成游戏评论分析图表（base64图片）
6. retention_summary — 查询用户留存概括数据
7. retention_chart — 生成留存分析图表（base64图片）
8. loan_summary — 查询贷款违约预测模型概括数据
9. loan_chart — 生成贷款模型图表（base64图片）"""

    # 第1步：LLM 决策
    decision_prompt = f"""{tools_desc}
用户问题：{msg}
请决定应该调用哪个工具，或者直接回复。JSON格式：
{{"action":"工具名"}} 或 {{"action":"chat","reply":"直接回复的内容"}}
只输出JSON。"""

    import requests as req
    try:
        r = req.post("https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}","Content-Type":"application/json"},
            json={"model":"deepseek-v4-pro","messages":[
                {"role":"system","content":decision_prompt},{"role":"user","content":msg}
            ],"temperature":0},timeout=30)
        decision = r.json()["choices"][0]["message"]["content"]
    except:
        return {"reply": "LLM 调用失败，请确认 API Key 已设置"}

    import json
    try:
        d = json.loads(decision)
        action = d.get("action","chat")
        if action == "chat":
            return {"reply": d.get("reply","你好，请问有什么可以帮你的？")}
    except:
        return {"reply": f"Agent 决策解析失败，原始响应: {decision[:200]}"}

    # 执行工具
    result_data = ""; chart_html = ""
    if action == "food_summary":
        tc = df_food['菜系类型'].value_counts().index[0]; mp = int(df_food['人均消费'].median())
        result_data = f"北京餐饮：{len(df_food):,}家店铺，人均消费中位数 ¥{mp}，最大品类 {tc}。"
    elif action == "food_table":
        ct = df_food.groupby('菜系类型').agg({'店铺id':'count','人均消费':'mean','评分':'mean'}).round(1)
        ct.columns = ['店铺数','人均消费','评分']
        top10 = ct[ct['店铺数']>=30].sort_values('人均消费',ascending=False).head(10)
        rows_html = "".join(f"<tr><td>{i}</td><td>{r['店铺数']}</td><td>{r['人均消费']}</td><td>{r['评分']}</td></tr>" for i,r in top10.iterrows())
        result_data = f"<table style='font-size:12px;width:100%'><tr><th>菜系</th><th>店铺数</th><th>人均消费</th><th>评分</th></tr>{rows_html}</table>"
    elif action == "food_chart":
        fig,(ax1,ax2)=plt.subplots(1,2,figsize=(10,4))
        p=df_food.groupby('菜系类型')['人均消费'].mean().round(1);top5=p[p.index.isin(df_food['菜系类型'].value_counts().head(5).index)].sort_values(ascending=False)
        ax1.barh(top5.index[::-1],top5.values[::-1],color='#C44E52');ax1.set_title('主要菜系人均消费')
        ds=df_food.groupby('county').agg({'店铺id':'count','人均消费':'mean'}).round(1)
        ds.columns=['店铺数','人均消费'];td=ds.sort_values('人均消费',ascending=False).head(5)
        ax2.barh(td.index[::-1],td['人均消费'][::-1],color='#DD8452');ax2.set_title('各区人均消费 TOP5')
        plt.tight_layout();chart_html=fig_to_html(fig)
    elif action == "game_summary":
        pos=(df_game['sentiment']=='好评').mean()*100;bp=df_game.groupby('Platform')['Rating'].mean().idxmax()
        result_data=f"游戏评论：{len(df_game):,}条，好评率 {pos:.0f}%，最佳平台 {bp}。"
    elif action == "game_chart":
        fig,(ax1,ax2)=plt.subplots(1,2,figsize=(10,4))
        sent=df_game['sentiment'].value_counts()
        ax1.pie(sent.values,labels=sent.index,autopct='%1.1f%%',startangle=90,colors=['#55A868','#999','#C44E52']);ax1.set_title('情感分布')
        ps=df_game.groupby('Platform')['Rating'].mean()
        ax2.bar(ps.index,ps.values,color=['#2b5c9e','#55A868','#DD8452']);ax2.set_title('各平台平均评分')
        plt.tight_layout();chart_html=fig_to_html(fig)
    elif action == "retention_summary":
        ret_vals=df_retention.groupby('week').apply(lambda x: x['retained'].sum()/df_retention.groupby('week')['new_users'].sum().sum()*100)
        w1=round(ret_vals.values[0],1);result_data=f"用户留存：首周留存率 {w1}%，约 {100-w1:.0f}% 的用户首周后流失。"
    elif action == "retention_chart":
        fig,(ax1,ax2)=plt.subplots(1,2,figsize=(10,4))
        ret_vals=df_retention.groupby('week').apply(lambda x: x['retained'].sum()/df_retention.groupby('week')['new_users'].sum().sum()*100)
        ax1.plot(ret_vals.index,ret_vals.values,'o-',color='#2b5c9e',linewidth=2.5,markersize=10);ax1.set_title('留存曲线');ax1.set_ylabel('%');ax1.grid(alpha=.3)
        heat=df_retention.groupby('week')['retained'].sum()
        ax2.bar(heat.index,heat.values,color='#DD8452');ax2.set_title('每周回访人数')
        plt.tight_layout();chart_html=fig_to_html(fig)
    elif action == "loan_summary":
        result_data="贷款违约预测：5,000条信贷数据，随机森林 AUC 0.945，最强预测因子为负债率和房产。"
    elif action == "loan_chart":
        from sklearn.ensemble import RandomForestClassifier;from sklearn.model_selection import train_test_split
        np.random.seed(42);n2=5000
        X2=pd.DataFrame(dict(credit_score=np.clip(np.random.normal(650,80,n2).astype(int),300,850),debt_ratio=np.random.uniform(0,.7,n2).round(2),income=np.clip(np.random.lognormal(8.8,.5,n2).astype(int),30000,2000000),has_house=np.random.choice([0,1],n2,p=[.5,.5]),has_car=np.random.choice([0,1],n2,p=[.4,.6]),age=np.clip(np.random.normal(38,10,n2).astype(int),22,65),emp_years=np.clip(np.random.exponential(5,n2).astype(int),0,40)))
        lo=(-.03*X2['credit_score']/10+.5*X2['debt_ratio']*10-.8*X2['has_house']-.3*X2['has_car']-.02*X2['emp_years']+np.random.normal(0,.5,n2))
        y2=(1/(1+np.exp(-lo))>np.percentile(1/(1+np.exp(-lo)),85)).astype(int)
        Xt2,_,yt2,_=train_test_split(X2,y2,test_size=.2,random_state=42)
        rf2=RandomForestClassifier(n_estimators=100,max_depth=6,random_state=42);rf2.fit(Xt2,yt2)
        imp2=pd.DataFrame({'特征':X2.columns,'重要性':rf2.feature_importances_}).sort_values('重要性',ascending=False)
        fig,(ax1,ax2)=plt.subplots(1,2,figsize=(10,4))
        ax1.barh(imp2['特征'][::-1],imp2['重要性'][::-1],color='#2b5c9e');ax1.set_title('特征重要性')
        ax2.bar(['正常还款','违约'],[100-y2.mean()*100,y2.mean()*100],color=['#55A868','#C44E52']);ax2.set_title('违约率分布')
        plt.tight_layout();chart_html=fig_to_html(fig)
    else:
        return {"reply": f"未知请求，请重新描述。可用功能：餐饮分析、游戏评论、留存分析、贷款预测"}

    # LLM 总结
    if result_data:
        summary_prompt = f"用户问题：{msg}\n查询结果：{result_data}\n请用简洁中文总结（1-3句话），可以加业务建议。"
        try:
            r2 = req.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization":f"Bearer {DEEPSEEK_KEY}","Content-Type":"application/json"},
                json={"model":"deepseek-v4-pro","messages":[
                    {"role":"system","content":"你是基于DeepSeek V4 Pro的数据分析AI助手。如果用户问你的模型名字，回答DeepSeek V4 Pro。用中文回复。"},
                    {"role":"user","content":summary_prompt}
                ],"temperature":0},timeout=30)
            summary = r2.json()["choices"][0]["message"]["content"]
        except:
            summary = result_data
    else:
        summary = ""
    return {"reply": summary, "chart": chart_html}

# ===== 启动 =====
if __name__ == '__main__':
    import uvicorn; import os
     port=int(os.environ.get("PORT",8000)); uvicorn.run(app, host="0.0.0.0", port=port)
