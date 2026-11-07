"""全栈数据分析平台 — 七个分析模块 + 多轮工具编排 Agent。

页面只负责渲染，所有业务口径集中在 analysis/ 下；页面、JSON API 与 Agent
共用同一份分析结果，避免同一个指标出现两套算法。
"""
import json
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from agent_runtime import Agent
from fastapi.staticfiles import StaticFiles

from analysis.portfolio import get_movies_analysis, get_survey_analysis, get_housing_analysis
from analysis.food import get_food_analysis, recommend_food
from analysis.rental import get_rental_analysis
from analysis.jobs import get_jobs_analysis
from analysis.retailrocket import get_retailrocket_analysis

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_env_file(path):
    """读取本地 .env（不覆盖已有环境变量），方便本地调试 API Key。"""
    try:
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key.startswith("export "):
                    key = key[7:].strip()
                os.environ.setdefault(key, value.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_env_file(os.path.join(BASE_DIR, ".env"))

app = FastAPI(title="全栈数据分析平台", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY", "")

MODULES = [{'slug': 'food',
  'icon': '🍽️',
  'title': '北京餐饮',
  'en': 'RESTAURANT',
  'count': '44,512',
  'accent': '#22d3ee',
  'desc': '识别人均消费与评分缺失，分析价格带、菜系、区域和评论集中度；保留原始推荐标签的来源限制。',
  'tags': ['缺失值口径', '评论集中度', '价格分层']},
 {'slug': 'survey',
  'icon': '🥤',
  'title': '消费者调查',
  'en': 'CONSUMER SURVEY',
  'count': '1,453',
  'accent': '#8b5cf6',
  'desc': '麦当劳消费者问卷：品牌属性、好感分组、到访频率与年龄差异。',
  'tags': ['品牌认知', '好感分组', '问卷分析']},
 {'slug': 'housing',
  'icon': '🏡',
  'title': '美国房价',
  'en': 'AMES HOUSING',
  'count': '1,460',
  'accent': '#34d399',
  'desc': '美国Ames历史房屋成交售价：房屋特征、社区差异与独立留出验证；与北京月租金分别展示。',
  'tags': ['美元成交价', '房屋特征', '留出验证']},
 {'slug': 'movies',
  'icon': '🎬',
  'title': '国产电影',
  'en': 'CHINESE MOVIES',
  'count': '120',
  'accent': '#f59e0b',
  'desc': '国产电影历史样本：票房、双平台评分、类型筛选与各影片截止日期。',
  'tags': ['类型多标签', '票房分布', '评分关联']},
 {'slug': 'rental',
  'icon': '🏘️',
  'title': '北京租房',
  'en': 'BEIJING RENTAL',
  'count': '35,082',
  'accent': '#60a5fa',
  'desc': '整租与合租必须分开算；面积与单价的关系主要是除法效应，配套字段几乎没有解释力。',
  'tags': ['分房型口径', '除法效应', '字段质量']},
 {'slug': 'jobs',
  'icon': '💼',
  'title': '数据岗招聘',
  'en': 'DATA JOBS',
  'count': '3,523',
  'accent': '#f472b6',
  'desc': '解析混合格式薪资并剔除 49.9% 的伪数据岗；算法 25,000，数据分析 12,500。',
  'tags': ['薪资解析', '岗位去噪', '控制变量']},
 {'slug': 'retailrocket',
  'icon': '🛒',
  'title': '电商行为',
  'en': 'RETAILROCKET',
  'count': '2,756,101',
  'accent': '#2dd4bf',
  'desc': '真实电商行为：MySQL汇总快照，观察访问、购买漏斗与回访，明确属性未知和观察窗口。',
  'tags': ['真实电商', '有序漏斗', '时间属性关联']}]

MODULE_MAP = {m["slug"]: m for m in MODULES}
PORTFOLIO_LOADERS = {"housing": get_housing_analysis, "movies": get_movies_analysis, "survey": get_survey_analysis}


def _nav(active=""):
    links = [("", "◫", "工作台")] + [(m["slug"], str(i + 1).zfill(2), m["title"]) for i, m in enumerate(MODULES)]
    items = []
    for slug, icon, label in links:
        href = "/workspace" if slug == "" else f"/module/{slug}"
        cls = "active" if active == slug else ""
        current = ' aria-current="page"' if active == slug else ''
        items.append(f'<a href="{href}" class="{cls}"{current}><span class="nav-icon">{icon}</span>{label}</a>')
    items.append(f'<a href="/agent" class="agent-link {"active" if active == "agent" else ""}"><span class="nav-icon">✳</span>AI 分析助手<span class="nav-badge">AI</span></a>')
    return f'<nav class="nav" aria-label="主要导航">{"".join(items)}</nav>'


def _head(title, desc=""):
    return f"""<meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{desc or 'FastAPI + Pandas + Scikit-learn + ECharts 数据分析平台'}">
  <title>{title} · 全栈数据分析平台</title>
  <link rel="stylesheet" href="/static/app.css">\n  <script src="/static/shell.js" defer></script>"""


def _topbar(active=""):
    label = MODULE_MAP[active]["title"] if active in MODULE_MAP else ("AI 分析助手" if active == "agent" else "工作台")
    return f"""<a class="skip-link" href="#main-content">跳转到内容</a>
    <aside class="sidebar">
      <a class="brand" href="/"><span class="brand-mark">▥</span><span>DataLab<small>数据分析工作空间</small></span></a>
      <div class="nav-caption">WORKSPACE / 工作空间</div>{_nav(active)}
      <div class="sidebar-bottom"><span class="status-dot"></span>统一分析引擎<small>页面 · API · AI 共享分析口径</small><a href="/api/docs">查看 API 文档 ↗</a></div>
    </aside>
    <header class="topbar" id="main-content"><div class="topbar-inner"><div class="breadcrumb">工作空间 <span>/</span> <b>{label}</b></div><a href="/agent" class="topbar-action">✳ 用 AI 探索数据 <span>↗</span></a></div></header>"""


def _footer():
    return """<footer class="footer"><div class="footer-inner"><span>DataLab · 让每个结论都有据可循</span><span>FastAPI / Pandas / Scikit-learn / ECharts</span></div></footer>"""


@app.get("/", response_class=HTMLResponse)
def cover():
    with open(os.path.join(BASE_DIR, "static", "cover.html"), encoding="utf-8") as page:
        return page.read()


@app.get("/workspace", response_class=HTMLResponse)
def home():
    cards = []
    for i, m in enumerate(MODULES):
        simulated = False
        source = "公开数据集"
        tags = ''.join(f'<span class="tag">{t}</span>' for t in m['tags'])
        cards.append(f"""<a class="module-card" href="/module/{m['slug']}" style="--accent:{m['accent']}">
          <div class="card-top"><span class="module-index">0{i+1} / {m['en']}</span><span class="source-badge {'simulated' if simulated else ''}">{source}</span></div>
          <div class="module-title"><span class="icon">{m['icon']}</span><h3>{m['title']}</h3></div>
          <p>{m['desc']}</p><div class="chips">{tags}</div>
          <div class="card-stats"><div><b>{m['count']}</b><span>条原始记录</span></div><span class="card-open">进入分析 ↗</span></div></a>""")
    return f"""<!DOCTYPE html><html lang="zh-CN"><head>{_head("工作台")}</head><body>
    {_topbar()}
    <main class="container dashboard">
      <section class="workspace-heading"><div><div class="eyebrow">OVERVIEW / 数据概览</div><h1>从数据出发，让洞察发生<span class="heading-dot">.</span></h1><p>七个业务场景，一个分析工作空间。选择数据集，探索指标背后的原因。</p></div><a class="btn" href="#datasets">浏览数据集 ↓</a></section>
      <section class="overview-stats" aria-label="平台数据概览">
        <div><span class="stat-caption">原始数据记录 <i>↗</i></span><strong>2,842,251<small>条</small></strong><span class="stat-foot">各模块主要样本数之和，记录单位不同</span></div>
        <div><span class="stat-caption">业务分析场景 <i>◫</i></span><strong>07<small>个</small></strong><span class="stat-foot">消费 · 电影 · 国内外住房 · 招聘 · 电商</span></div>
        <div><span class="stat-caption">数据来源构成 <i>▤</i></span><strong>07</strong><span class="stat-foot">公开历史样本，来源说明见各模块</span></div>
        <div><span class="stat-caption">分析方式 <i>✳</i></span><strong class="stat-text">可视化 + AI</strong><span class="stat-foot">图表探索与自然语言追问</span></div>
      </section>
      <section class="overview-row">
        <div class="panel distribution-panel"><div class="panel-head"><div><h2>数据集规模分布</h2><p>各模块主要原始记录数 · 对数刻度 · 清洗后样本以模块页为准</p></div><span class="mini-label">7 DATASETS</span></div><div id="datasetChart" class="chart" style="height:245px" role="img" aria-label="七个数据集记录数对比"></div></div>
        <div class="assistant-card"><span class="assistant-symbol">✳</span><div class="eyebrow">YOUR ANALYSIS COPILOT</div><h2>带着问题，<br>发现数据的另一面。</h2><p>从选择分析工具到引用计算结果，<br>让一次提问成为探索的起点。</p><a class="btn primary" href="/agent">开始与数据对话 <span>↗</span></a><span class="assistant-note">支持上下文追问与跨模块对比</span></div>
      </section>
      <section id="datasets"><div class="section-heading"><div><div class="eyebrow">EXPLORE / 开始探索</div><h2>选择你的分析场景</h2></div><label class="dataset-search"><span>⌕</span><input id="datasetSearch" type="search" placeholder="搜索场景、关键词…" aria-label="搜索分析场景"></label></div><div class="module-grid">{''.join(cards)}</div><p id="searchEmpty" class="search-empty" hidden>没有匹配的场景，试试“餐饮”“留存”或“薪资”。</p><div class="dataset-count" id="datasetCount" aria-live="polite">全部 7 个分析场景</div></section>
      <section class="method-strip"><div><span>01</span><b>检查数据质量</b><small>识别缺失值与样本偏差</small></div><div><span>02</span><b>探索业务指标</b><small>用交互图表理解分布与差异</small></div><div><span>03</span><b>形成可追溯结论</b><small>引用统计结果，标明适用边界</small></div></section>
    </main>{_footer()}<script src="/static/echarts.min.js"></script><script src="/static/common.js"></script><script src="/static/workspace.js"></script></body></html>"""


# ===== 模块页 =====
def _module_page(slug: str):
    m = MODULE_MAP[slug]
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
  {_head(m['title'])}
</head><body>
  {_topbar(slug)}
  <main class="container" id="app">
    <div class="loading"><span class="spinner"></span>正在加载 {m['title']} 分析结果…</div>
  </main>
  {_footer()}
  <script src="/static/echarts.min.js"></script>
  <script src="/static/common.js"></script>
  <script src="/static/{'portfolio' if slug in PORTFOLIO_LOADERS else slug}.js"></script>
</body></html>"""


@app.get("/module/food", response_class=HTMLResponse)
def page_food():
    return _module_page("food")








@app.get("/module/rental", response_class=HTMLResponse)
def page_rental():
    return _module_page("rental")


@app.get("/module/jobs", response_class=HTMLResponse)
def page_jobs():
    return _module_page("jobs")


# ===== Agent =====
MODULE_LABELS = {'food': '北京餐饮',
 'survey': '消费者调查',
 'housing': '美国房价',
 'movies': '国产电影',
 'rental': '北京租房',
 'jobs': '数据岗招聘',
 'retailrocket': '电商行为'}

FOCUS_ALIASES = {
    "价格": "price", "人均": "price", "消费": "price", "贵": "price",
    "菜系": "cuisine", "品类": "cuisine",
    "评分": "rating", "评价": "rating",
    "区域": "district", "商圈": "district", "各区": "district", "哪个区": "district",
    "米其林": "michelin", "夜宵": "late_night", "营业": "late_night",
    "推荐": "recommend", "哪家": "recommend", "好吃": "recommend",
    "吃什么": "recommend", "吃哪": "recommend", "餐厅推荐": "recommend",
    "情感": "sentiment", "主题": "themes", "平台": "platforms",
    "关键词": "keywords", "极化": "polarization",
    "渠道": "channels", "设备": "devices", "队列": "cohorts", "流失": "hazard",
    "阈值": "thresholds", "校准": "calibration", "重要性": "importance",
    "分群": "segments", "指标": "metrics", "ks": "metrics",
    "户型": "rent_types", "面积": "area", "配套": "amenities",
    "地铁": "amenities", "装修": "attributes", "楼层": "attributes",
    "城市": "cities", "岗位": "families", "职能": "families",
    "方向": "families", "岗位族": "families",
    "经验": "experience", "学历": "education", "公司": "company",
    "规模": "company", "趋势": "trend", "整租": "rent_types", "合租": "rent_types",
}

MODULE_KEYS = {'retailrocket': ['retailrocket', '电商', '加购', '购物车', '购买', '可售', '漏斗', '留存', '回访', '队列'],
 'food': ['餐饮', '菜系', '餐厅', '美食', '人均消费', '夜宵', '吃饭', '餐馆', '饭馆'],
 'survey': ['麦当劳', '问卷', '品牌', '消费者', '好感'],
 'housing': ['美国', 'ames', '房价', '成交', '售价', '房屋质量', '预测误差'],
 'movies': ['电影', '票房', '豆瓣', '猫眼', '导演', '影片'],
 'rental': ['北京租房', '租房', '租金', '房源', '整租', '合租', '房东'],
 'jobs': ['招聘', '岗位', '薪资', '求职', '就业', '数据岗', '月薪']}
# 模块专属词优先，当前问题先于历史上下文
PRIMARY_KEYS = {'retailrocket': ['retailrocket', '电商', '加购', '购物车', '购买', '可售', '漏斗', '留存', '回访', '队列'],
 'food': ['餐饮', '菜系', '餐厅', '美食', '人均消费', '夜宵', '吃饭', '餐馆', '饭馆'],
 'survey': ['麦当劳', '问卷', '品牌', '消费者', '好感'],
 'housing': ['美国', 'ames', '房价', '成交', '售价', '房屋质量', '预测误差'],
 'movies': ['电影', '票房', '豆瓣', '猫眼', '导演', '影片'],
 'rental': ['北京租房', '租房', '租金', '房源', '整租', '合租', '房东'],
 'jobs': ['招聘', '岗位', '薪资', '求职', '就业', '数据岗', '月薪']}

AGENT_SYSTEM = ('你是数据分析平台的中文分析助手。必须先调用工具，再引用具体计算结果回答。\n'
 '工具module可选：food北京餐饮；survey麦当劳消费者问卷；housing美国Ames成交售价；movies国产电影；rental北京租房；jobs招聘；retailrocket电商行为及真实回访。\n'
 'food '
 'focus=overview/price/cuisine/rating/district/michelin/late_night/recommend；推荐用params传district/cuisine/min_price/max_price，必须返回具体店名与样本口径。\n'
 'survey focus=overview/attributes/segments/visits/ages；housing '
 'focus=overview/neighborhoods/quality/validation；movies focus=overview/genres/ratings/movies。\n'
 'rental focus=overview/districts/area/amenities/rent_types/attributes/trend；jobs '
 'focus=overview/cities/families/experience/education/company。\n'
 'retailrocket focus=overview/trend/funnel/retention/products。首次观察不是注册，精确第N日回访不是N日内回访。\n'
 '美国住房为美元/套成交售价、面积平方英尺，北京住房为人民币/月租金、面积平方米；不得直接比较价格高低。北京月租与美国售价不是同一个指标。\n'
 '消费者问卷不是中国整体市场，电影各影片截止日不同；不将相关性当因果。food原始推荐标签不称官方米其林评级。\n'
 '来源说明简洁表述为：作者从和鲸社区、天池等公开数据社区下载整理。美国房价与Retailrocket注明Kaggle。不要追加下载链接缺失或核实状态的说明，也不要夸大为官方授权或逐条验证。旧贷款、游戏评论、模拟注册留存已撤下。\n'
 '历史对话仅用于理解指代，优先回答当前问题。一次最多规划3个工具。回答中文、简洁，引用来源与适用边界，不编造。\n'
 '只输出JSON：{"action":"call","calls":[{"module":"housing","focus":"validation"}]}；无需取数则{"action":"final","reply":"回复"}。')


def _chat_value(obj):
    """问答使用简洁来源文案，模块数据及完整说明保持原样。"""
    if isinstance(obj, dict):
        return {k: _chat_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_chat_value(v) for v in obj]
    if isinstance(obj, str):
        if "作者从和鲸社区、天池等公开数据社区下载整理" in obj:
            return "数据来源：作者从和鲸社区、天池等公开数据社区下载整理。"
        return (obj.replace("（标签来源未核实）", "")
                   .replace("120部电影的选样规则未保留，", "120部电影是当前分析样本，")
                   .replace("调查时间与抽样细节未在本地文件中保留", "统计仅描述当前调查样本")
                   .replace("发布时间口径及采集节奏未核实，", "当前样本的发布时间分布集中，")
                   .replace("原始推荐标签分层（非已核实官方米其林评级）", "原始推荐标签分层（非官方米其林评级）"))
    return obj


def _json_text(obj, limit=3200):
    s = json.dumps(_chat_value(obj), ensure_ascii=False, default=str, separators=(",", ":"))
    return s if len(s) <= limit else s[:limit] + "...(截断)"


def _normalize_focus(focus):
    if not focus:
        return "overview"
    f = str(focus).strip().lower()
    return FOCUS_ALIASES.get(f, f)


def _agent_tool(module, focus="overview", params=None):
    """返回给 LLM 的紧凑工具结果（字符串）。"""
    module = str(module or "").strip().lower()
    focus = _normalize_focus(focus)

    if module in PORTFOLIO_LOADERS:
        d = PORTFOLIO_LOADERS[module]()
        fields = {"ratings": ["correlations"], "validation": ["metrics", "validation"],
                  "segments": ["segments", "profiles"]}.get(focus, [focus])
        payload = {k: d[k] for k in ("overview", "insights", "data_notes", "source")}
        for key in fields:
            if key in d:
                payload[key] = d[key][:20] if isinstance(d[key], list) else d[key]
        return _json_text(payload, limit=10000)

    if module == "retailrocket":
        d = get_retailrocket_analysis()
        fields = {"trend": ["weekday", "july"], "funnel": ["funnel", "windows"], "retention": ["retention"], "products": ["coverage", "availability"]}
        payload = {"overview": d["overview"], "insights": d["insights"], "data_notes": d["data_notes"], "is_live": False}
        for key in fields.get(focus, []):
            payload[key] = d[key]
        return _json_text(payload, limit=8000)

    if module == "food":
        d = get_food_analysis()
        if focus == "price":
            payload = {"overview": d["overview"], "price_bands": d["price_bands"],
                       "price_distribution": d["price_distribution"],
                       "insights": d["insights"][:4]}
        elif focus == "cuisine":
            payload = {"overview": d["overview"], "cuisine_table": d["cuisine_table"][:12],
                       "insights": d["insights"][:4]}
        elif focus == "rating":
            payload = {"overview": d["overview"], "rating": d["rating"],
                       "review_concentration": d["review_concentration"],
                       "insights": d["insights"][:4]}
        elif focus == "district":
            payload = {"overview": d["overview"], "districts": d["districts"],
                       "business_areas": d["business_areas"][:12],
                       "insights": d["insights"][:4]}
        elif focus == "michelin":
            payload = {"michelin": d["michelin"], "insights": d["insights"][:4]}
        elif focus == "late_night":
            payload = {"late_night": d["late_night"], "insights": d["insights"][:4]}
        elif focus == "recommend":
            p = params if isinstance(params, dict) else {}
            try:
                rec = recommend_food(
                    district=p.get("district"),
                    cuisine=p.get("cuisine"),
                    min_price=p.get("min_price"),
                    max_price=p.get("max_price"),
                    limit=6,
                )
            except (TypeError, ValueError):
                rec = recommend_food(limit=6)
            payload = {"recommendations": rec, "data_notes": d["data_notes"][:2]}
        else:
            payload = {"overview": d["overview"], "insights": d["insights"][:4]}
        return _json_text(payload)

    if module == "rental":
        d = get_rental_analysis()
        if focus == "districts":
            payload = {"overview": d["overview"], "districts": d["districts"],
                       "district_by_type": d["district_by_type"],
                       "insights": d["insights"][:5]}
        elif focus == "area":
            payload = {"area_bands": d["area_bands"], "area_gap": d["area_gap"],
                       "rent_area_corr": d["rent_area_corr"],
                       "insights": d["insights"][:5]}
        elif focus == "amenities":
            payload = {"amenities": d["amenities"], "subway_distance": d["subway_distance"],
                       "insights": d["insights"][:4]}
        elif focus == "rent_types":
            payload = {"rent_types": d["rent_types"], "insights": d["insights"][:4]}
        elif focus == "attributes":
            payload = {"attributes": d["attributes"],
                       "attribute_spread_pct": d["attribute_spread_pct"],
                       "insights": d["insights"][:4]}
        elif focus == "trend":
            payload = {"trend": d["trend"], "insights": d["insights"][:4]}
        else:
            payload = {"overview": d["overview"], "rent_types": d["rent_types"],
                       "insights": d["insights"][:5]}
        return _json_text(payload)

    if module == "jobs":
        d = get_jobs_analysis()
        if focus == "cities":
            payload = {"overview": d["overview"], "cities": d["cities"],
                       "city_controlled": d["city_controlled"],
                       "insights": d["insights"][:6]}
        elif focus == "families":
            payload = {"families": d["families"], "insights": d["insights"][:5]}
        elif focus == "experience":
            payload = {"experience": d["experience"], "insights": d["insights"][:5]}
        elif focus == "education":
            payload = {"education": d["education"], "insights": d["insights"][:4]}
        elif focus == "company":
            payload = {"company_type": d["company_type"],
                       "company_size": d["company_size"],
                       "insights": d["insights"][:4]}
        else:
            payload = {"overview": d["overview"], "families": d["families"],
                       "insights": d["insights"][:5]}
        return _json_text(payload)

    return _json_text({"error": f"未知模块 {module}，可用：{list(MODULE_LABELS)}"})


def _match_modules(text, mapping):
    text = str(text).lower()
    return [m for m, keys in mapping.items()
            if any(str(k).lower() in text for k in keys)]


def _infer_foci(module, text):
    text = str(text).lower()
    foci = []
    for word, focus in FOCUS_ALIASES.items():
        if word.lower() in text and focus not in foci:
            foci.append(focus)
    if module == "retailrocket":
        return [focus for word, focus in [("漏斗", "funnel"), ("加购", "funnel"), ("窗口", "funnel"), ("留存", "retention"), ("回访", "retention"), ("可售", "products"), ("类别", "products"), ("趋势", "trend"), ("周末", "trend")] if word in text]
    if module in PORTFOLIO_LOADERS:
        words = {
            "housing": [("社区", "neighborhoods"), ("区域", "neighborhoods"), ("质量", "quality"), ("误差", "validation"), ("模型", "validation"), ("预测", "validation")],
            "movies": [("类型", "genres"), ("评分", "ratings"), ("票房", "movies")],
            "survey": [("属性", "attributes"), ("认知", "attributes"), ("分组", "segments"), ("好感", "segments"), ("频率", "visits"), ("到访", "visits"), ("年龄", "ages")],
        }[module]
        return [focus for word, focus in words if word in text]
    # 同一别名在不同模块下指向不同的工具名
    if module == "rental" and "district" in foci:
        foci[foci.index("district")] = "districts"
    return foci


def _infer_focus(module, text):
    foci = _infer_foci(module, text)
    return foci[0] if foci else "overview"


def _module_data(module):
    return {
        "retailrocket": get_retailrocket_analysis,
        "food": get_food_analysis,
        **PORTFOLIO_LOADERS,
        "rental": get_rental_analysis,
        "jobs": get_jobs_analysis,
    }[module]()


def _fmt_money(v):
    try:
        return f"¥{float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_pct(v):
    try:
        return f"{float(v):.1f}%"
    except (TypeError, ValueError):
        return str(v)


def _weighted_median(pairs):
    total = sum(c for _, c in pairs)
    if not total:
        return None
    seen = 0
    for value, count in sorted(pairs):
        seen += count
        if seen >= total / 2:
            return value
    return None


def _food_answer(foci):
    d = get_food_analysis()
    o = d["overview"]
    lines, tools = [], []

    if "district" in foci:
        by_count = sorted(d["districts"], key=lambda x: -x["stores"])
        by_price = sorted(d["districts"], key=lambda x: -x["median_price"])
        cheap = sorted(d["districts"], key=lambda x: x["median_price"])
        lines.append("店铺最多的区：" + "、".join(
            f"{x['name']} {x['stores']:,} 家" for x in by_count[:3]))
        lines.append(
            f"人均中位最高 {by_price[0]['name']} {_fmt_money(by_price[0]['median_price'])}，"
            f"最低 {cheap[0]['name']} {_fmt_money(cheap[0]['median_price'])}，"
            f"相差 {by_price[0]['median_price'] / max(cheap[0]['median_price'], 1):.1f} 倍")
        tools.append("food.district")

    if "cuisine" in foci:
        cuisines = [x for x in d["cuisine_table"] if x["name"] not in ("未标注", "其他")]
        by_count = sorted(cuisines, key=lambda x: -x["stores"])
        expensive = sorted([x for x in cuisines if x["stores"] >= 50],
                           key=lambda x: -x["median_price"])
        lines.append("店铺最多的菜系：" + "、".join(
            f"{x['name']} {x['stores']:,} 家" for x in by_count[:3]))
        if expensive:
            lines.append("人均中位最高（限 ≥50 家）：" + "、".join(
                f"{x['name']} {_fmt_money(x['median_price'])}" for x in expensive[:3]))
        tools.append("food.cuisine")

    if "price" in foci:
        lines.append(
            f"价格有效样本 {o['stores_with_price']:,}/{o['stores']:,}"
            f"（覆盖 {_fmt_pct(o['price_coverage_pct'])}），中位 {_fmt_money(o['price_median'])}、"
            f"均值 {_fmt_money(o['price_mean'])}、P90 {_fmt_money(o['price_p90'])}；"
            f"另 {o['stores'] - o['stores_with_price']:,} 家 0 元按缺失处理")
        tools.append("food.price")

    if "rating" in foci:
        rating = d["rating"]
        med = _weighted_median([(x["score"], x["count"]) for x in rating["distribution"]])
        lines.append(
            f"有评分店铺 {rating['rated_stores']:,} 家（覆盖 {_fmt_pct(o['rating_coverage_pct'])}）；"
            f"评分中位 {med}/5，价格与评分的相关系数仅 {rating['price_rating_corr']}")
        tools.append("food.rating")

    if "michelin" in foci:
        lines.append("原始推荐标签分层（非已核实官方米其林评级）：" + "、".join(
            f"{x['tier']} {x['stores']} 家（中位 {_fmt_money(x['median_price'])}）"
            for x in d["michelin"]))
        tools.append("food.michelin")

    if "late_night" in foci:
        late = d["late_night"]
        lines.append(
            f"营业时间可解析 {late['parsed_stores']:,} 家（{_fmt_pct(late['parsed_pct'])}），"
            f"其中夜宵 {late['late_stores']:,} 家（{_fmt_pct(late['late_pct_of_parsed'])}）；"
            "夜宵占比最高：" + "、".join(
                f"{x['name']} {_fmt_pct(x['late_pct'])}" for x in late["top_districts"][:2]))
        tools.append("food.late_night")

    if "recommend" in foci:
        rec = d["recommendations"]
        picks = rec["top_rated"][:3]
        lines.append(
            "推荐候选（有评分且评论数 ≥ 50）：" + "；".join(
                f"{x['name']}（{x['district']}·{x['cuisine']}，"
                f"{_fmt_money(x['price'])}/人，{x['rating']}/5，{x['reviews']} 条评论）"
                for x in picks
            )
        )
        if rec["value"]:
            v = rec["value"][0]
            if v["name"] not in {x["name"] for x in picks}:
                lines.append(
                    f"性价比可选：{v['name']}（{v['district']}，"
                    f"{_fmt_money(v['price'])}/人，{v['rating']}/5，{v['reviews']} 条评论）"
                )
        lines.append(
            f"推荐池 {rec['eligible_stores']:,} 家；评分覆盖仅 39.2%，"
            "这是「有评分且评论足够」的子样本，不是全量店铺排名"
        )
        tools.append("food.recommend")

    return lines, tools








def _rental_answer(foci):
    d = get_rental_analysis()
    lines, tools = [], []

    if "rent_types" in foci:
        lines.append("房型对比：" + "；".join(
            f"{x['name']}中位 {_fmt_money(x['rent_median'])}、面积 {x['area_median']}㎡、"
            f"单价 {_fmt_money(x['unit_median'])}/㎡（{x['count']:,} 套）"
            for x in d["rent_types"]))
        tools.append("rental.rent_types")

    if "districts" in foci:
        ds = sorted(d["districts"], key=lambda x: -x["rent_median"])
        whole = sorted(d["district_by_type"].get("整租", []),
                       key=lambda x: -x["rent_median"])
        shared = sorted(d["district_by_type"].get("合租", []),
                        key=lambda x: -x["rent_median"])
        lines.append("整体租金中位最高：" + "、".join(
            f"{x['district']} {_fmt_money(x['rent_median'])}" for x in ds[:3])
            + f"；最低 {ds[-1]['district']} {_fmt_money(ds[-1]['rent_median'])}")
        if whole and shared:
            lines.append(
                f"但分房型排序不同：整租最贵 {whole[0]['district']} "
                f"{_fmt_money(whole[0]['rent_median'])}，合租最贵 {shared[0]['district']} "
                f"{_fmt_money(shared[0]['rent_median'])}——混算会被房型结构污染")
        tools.append("rental.districts")

    if "area" in foci:
        b, corr = d["area_bands"], d["rent_area_corr"]
        lines.append(
            f"面积 {b[0]['band']} 单价 {_fmt_money(b[0]['unit_median'])}/㎡ → "
            f"{b[-1]['band']} {_fmt_money(b[-1]['unit_median'])}/㎡；"
            f"同房型内租金与面积相关系数仅 {corr['整租']}（整租）/ "
            f"{corr['合租']}（合租），主要是除法效应")
        tools.append("rental.area")

    if "amenities" in foci:
        lines.append("配套与单价的差异：" + "、".join(
            f"{x['label']} {x['diff_pct']:+.1f}%" for x in d["amenities"])
            + "；都在 1% 以内，不能写成「地铁房溢价」")
        tools.append("rental.amenities")

    if "attributes" in foci:
        s = d["attribute_spread_pct"]
        lines.append(
            f"属性组间单价差异：装修 {_fmt_pct(s['装修'])}、楼层 {_fmt_pct(s['楼层'])}、"
            f"朝向 {_fmt_pct(s['朝向'])}，接近随机噪声")
        tools.append("rental.attributes")

    if "trend" in foci:
        t = d["trend"]
        change = (t[-1]["rent_median"] / t[0]["rent_median"] - 1) * 100
        lines.append(
            f"{t[0]['month']} 至 {t[-1]['month']} 租金中位 "
            f"{_fmt_money(t[0]['rent_median'])} → {_fmt_money(t[-1]['rent_median'])}"
            f"（{change:+.1f}%），24 个月整体平稳")
        tools.append("rental.trend")

    if not lines:
        lines, tools = d["insights"][:4], ["rental.overview"]
    return lines, tools


def _jobs_answer(foci):
    d = get_jobs_analysis()
    o = d["overview"]
    lines, tools = [], []

    if "cities" in foci:
        cities = sorted(d["cities"], key=lambda x: -x["count"])[:5]
        lines.append("岗位最多的城市：" + "、".join(
            f"{x['city']} {x['count']:,} 条" for x in cities[:3])
            + f"，TOP3 合计占 {_fmt_pct(o['top3_city_share_pct'])}")
        lines.append("月薪中位：" + "、".join(
            f"{x['city']} {_fmt_money(x['monthly_median'])}" for x in cities[:3])
            + "；城市差异里混有岗位结构，不能直接当同岗薪资差")
        tools.append("jobs.cities")

    if "families" in foci:
        families = [x for x in d["families"] if x["family"] != "非数据/其他"]
        by_pay = sorted(families, key=lambda x: -x["monthly_median"])
        by_count = sorted(families, key=lambda x: -x["count"])
        lines.append("月薪中位最高的岗位族：" + "、".join(
            f"{x['family']} {_fmt_money(x['monthly_median'])}（{x['count']} 条）"
            for x in by_pay[:4]))
        lines.append("岗位数最多的方向：" + "、".join(
            f"{x['family']} {x['count']} 条" for x in by_count[:3]))
        tools.append("jobs.families")

    if "experience" in foci:
        lines.append("经验与月薪中位：" + "、".join(
            f"{x['group']} {_fmt_money(x['monthly_median'])}"
            for x in d["experience"]))
        tools.append("jobs.experience")

    if "education" in foci:
        lines.append("学历与月薪中位：" + "、".join(
            f"{x['group']} {_fmt_money(x['monthly_median'])}（{x['count']} 条）"
            for x in d["education"] if x["group"] in ("大专", "本科", "硕士", "博士")))
        tools.append("jobs.education")

    if "company" in foci:
        ct = sorted(d["company_type"], key=lambda x: -x["monthly_median"])[:3]
        cs = sorted(d["company_size"], key=lambda x: -x["monthly_median"])[:3]
        lines.append("公司类型月薪中位最高：" + "、".join(
            f"{x['group']} {_fmt_money(x['monthly_median'])}" for x in ct))
        lines.append("公司规模月薪中位最高：" + "、".join(
            f"{x['group']} {_fmt_money(x['monthly_median'])}" for x in cs))
        tools.append("jobs.company")

    if not lines:
        lines, tools = d["insights"][:4], ["jobs.overview"]

    lines.append(
        f"采样提醒：{_fmt_pct(o['top_date_share_pct'])} 的岗位集中在 {o['top_date']}，"
        "发布时间口径及采集节奏未核实，不能据此推断真实招聘周期")
    return lines, tools


def _portfolio_answer(module, foci):
    d = PORTFOLIO_LOADERS[module]()
    lines = list(d["insights"])
    if module == "housing" and "neighborhoods" in foci:
        rows = sorted(d["neighborhoods"], key=lambda r: -r["median_price"])[:3]
        lines.append("样本社区售价中位数：" + "；".join(f"{r['name']} ${r['median_price']:,.0f}（{r['count']}套）" for r in rows))
    if module == "movies" and "genres" in foci:
        lines.append("类型样本量：" + "；".join(f"{r['tag']} {r['count']}部" for r in d['genres'][:6]) + "；多标签重复计数。")
    if module == "movies" and "ratings" in foci:
        lines.append("评分与log(1+票房亿元)相关系数：" + "；".join(f"{r['name']} {r['pearson_log_revenue']:.3f}（{r['count']}部）" for r in d['correlations']))
    if module == "survey" and "attributes" in foci:
        lines.append("属性认同率：" + "；".join(f"{r['name']} {r['yes_pct']:.1f}%" for r in d['attributes']))
    if module == "survey" and "visits" in foci:
        lines.append("各到访频率平均好感分：" + "；".join(f"{r['name']} {r['mean_like']:.2f}（{r['count']}人）" for r in d['visits']))
    if module == "survey" and "ages" in foci:
        lines.append("年龄组平均好感分：" + "；".join(f"{r['name']} {r['mean_like']:.2f}（{r['count']}人）" for r in d['ages']))
    return lines + [d["data_notes"][0]], [module + "." + (foci[0] if foci else "overview")]


_FALLBACK_BUILDERS = {
    "food": _food_answer, "rental": _rental_answer, "jobs": _jobs_answer,
    "retailrocket": lambda foci: (get_retailrocket_analysis()["insights"] + ["历史匿名样本，首次观察不是注册。"], ["retailrocket.overview"]),
    **{key: (lambda foci, module=key: _portfolio_answer(module, foci)) for key in PORTFOLIO_LOADERS},
}


def _fallback_agent(msg, history):
    """没有 API Key / LLM 失败时的规则编排：调用同一分析层，按问题字段作答。"""
    msg_text = str(msg).lower()
    modules = _match_modules(msg_text, PRIMARY_KEYS) or _match_modules(msg_text, MODULE_KEYS)
    if "retailrocket" in modules and not any(word in msg_text for word in ("对比", "比较", "模拟")):
        modules = ["retailrocket"]
    context_text = ""
    if not modules:
        # 只有当前问题没提模块时，才继承最近一条带模块的历史问题；
        # 否则前面问过租房/游戏，后面的问题会一直被历史模块污染。
        for prev in reversed([
            h.get("content", "") for h in history if h.get("role") == "user"
        ]):
            prev_text = str(prev).lower()
            prev_modules = (_match_modules(prev_text, PRIMARY_KEYS)
                            or _match_modules(prev_text, MODULE_KEYS))
            if prev_modules:
                modules = prev_modules
                context_text = prev_text
                break
    text = (msg_text + " " + context_text).strip()
    if not modules:
        intro = "可以问我北京餐饮、消费者调查、美国房价、国产电影、北京租房、数据岗招聘和电商行为。真实回访分析位于电商模块；旧游戏评论、模拟留存和贷款模块已撤下。试试：美国房价预测误差多少？电影评分与票房有关吗？"
        if not DEEPSEEK_KEY:
            intro += "\n\n（当前未配置 DEEPSEEK_KEY，由本地规则引擎直接调用分析层。）"
        return {"reply": intro, "tools": []}

    sections, tools = [], []
    for m in modules[:2]:
        # 当前问题优先；追问没有字段词时，再从历史问题里继承上下文
        foci = _infer_foci(m, msg) or _infer_foci(m, text)
        lines, used = _FALLBACK_BUILDERS[m](foci)
        sections.append(
            f"【{MODULE_LABELS[m]}】\n" + "\n".join(f"· {_chat_value(x)}" for x in lines)
        )
        tools.extend(used)

    reply = "\n\n".join(sections)
    if len(modules) > 2:
        reply += f"\n\n（同时提到 {len(modules)} 个模块，这里先回答前 2 个；可以指定模块继续追问。）"
    if not DEEPSEEK_KEY:
        reply += "\n\n（当前未配置 DEEPSEEK_KEY，以上由本地规则引擎直接调用分析层；配置后可启用多轮工具编排。）"
    return {"reply": reply, "tools": tools}


@app.get("/agent", response_class=HTMLResponse)
def agent_page():
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head>
  {_head("AI Agent", "支持多轮工具调用与跨模块对比的数据分析 Agent")}
</head><body>
  {_topbar("agent")}
  <main class="container">
    <div class="chat-shell">
      <div class="page-head">
        <div class="eyebrow">Agent · Tool Orchestration</div>
        <h1>问数据，而不是翻页面</h1>
        <p>用自然语言探索七个分析场景。回答引用分析工具的计算结果，支持连续追问与跨模块对比。</p><div class="agent-mode">{"✳ AI 工具编排模式" if DEEPSEEK_KEY else "◈ 本地规则模式 · 已连接分析工具"}</div>
      </div>

      <div class="chatbox" id="chatbox" role="log" aria-label="分析对话" aria-live="polite">
        <div class="msg agent">👋 你好，我是数据分析 Agent。可以问我北京餐饮的真实人均、具体餐厅推荐、消费者的品牌认知、美国房价预测误差、电影票房与评分、电商回访、租房口径或数据岗薪资。也可以连续追问，比如「数据岗哪个方向薪资最高？再按城市拆一下」。</div>
      </div>

      <div class="suggestions">
        <button data-q="北京餐饮人均消费的真实中位数是多少？为什么不能直接用平均值？">餐饮真实人均</button>
        <button data-q="我想去北京吃饭，帮我推荐一家评分高、评论多的店">餐厅推荐</button>
        <button data-q="电影的评分和票房有什么关系？">电影评分与票房</button>
        <button data-q="电商访客第7日回访率是多少？">电商真实回访</button>
        <button data-q="美国房价模型的验证误差是多少？">美国房价预测</button>
        <button data-q="北京租房整租和合租的单价差异说明什么？">整租 vs 合租</button>
        <button data-q="数据岗里哪个方向薪资最高？再按城市拆一下">岗位族与城市</button>
      </div>

      <div class="input-row" style="margin-top:14px">
        <input aria-label="向数据分析助手提问" id="userInput" placeholder="输入你的问题，例如：数据岗哪个方向薪资最高？" autocomplete="off">
        <button id="sendBtn">发送</button>
      </div>
      <p class="hint" style="color:var(--dim);font-size:11px;margin-top:10px">回答由分析层实时计算；工具调用链会显示在每条回答上方。
        <button id="resetBtn" class="reset-btn" type="button">清空对话</button>
      </p>
    </div>
  </main>
  {_footer()}
  <script src="/static/common.js"></script>
  <script src="/static/agent.js?v=20261103"></script>
</body></html>"""


def _new_agent():
    return Agent(DEEPSEEK_KEY, AGENT_SYSTEM, MODULE_LABELS,
                 _agent_tool, _fallback_agent, _normalize_focus)


@app.post("/api/agent/chat")
async def agent_chat(req: dict):
    """兼容原 JSON 接口；新增 source、耗时及请求编号。"""
    async for event in _new_agent().events(req):
        if event["type"] == "done":
            return {k: v for k, v in event.items() if k != "type"}


@app.post("/api/agent/chat/stream")
async def agent_chat_stream(req: dict):
    """逐行 JSON：状态、增量正文、最终结果；客户端断开时取消模型请求。"""
    async def stream():
        async for event in _new_agent().events(req):
            yield json.dumps(event, ensure_ascii=False) + "\n"
    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ===== JSON API =====
@app.get("/api/food")
def api_food():
    """北京餐饮完整分析结果，供页面 / Agent 复用。"""
    return JSONResponse(get_food_analysis())








@app.get("/api/rental")
def api_rental():
    """北京租房：分房型的区域价格、面积效应与配套字段质量。"""
    return JSONResponse(get_rental_analysis())


@app.get("/api/jobs")
def api_jobs():
    """数据岗招聘：薪资解析、城市/经验/学历/岗位族结构。"""
    return JSONResponse(get_jobs_analysis())


@app.get("/health")
def health():
    return {"status": "ok", "modules": list(MODULE_MAP)}




@app.get("/module/retailrocket", response_class=HTMLResponse)
def page_retailrocket():
    return _module_page("retailrocket")


@app.get("/api/retailrocket")
def api_retailrocket():
    return JSONResponse(get_retailrocket_analysis())




@app.get("/module/{slug}", response_class=HTMLResponse)
def page_portfolio(slug: str):
    if slug in {"game": "survey", "loan": "movies", "retention": "retailrocket"}:
        return RedirectResponse("/module/" + {"game": "survey", "loan": "movies", "retention": "retailrocket"}[slug], status_code=307)
    if slug in MODULE_MAP:
        return _module_page(slug)
    return HTMLResponse("未找到分析模块", status_code=404)

@app.get("/api/{slug}")
def api_portfolio(slug: str):
    if slug in ("game", "loan", "retention"):
        return JSONResponse({"error": "该模块已撤下", "replacement": {"game": "survey", "loan": "movies", "retention": "retailrocket"}[slug]}, status_code=410)
    loaders = {**PORTFOLIO_LOADERS, "retailrocket": get_retailrocket_analysis,
               "food": get_food_analysis, "rental": get_rental_analysis, "jobs": get_jobs_analysis}
    if slug not in loaders:
        return JSONResponse({"error": "未知模块"}, status_code=404)
    return JSONResponse(loaders[slug]())


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
