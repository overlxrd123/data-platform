"""全栈数据分析平台 — 六个分析模块 + 多轮工具编排 Agent。

页面只负责渲染，所有业务口径集中在 analysis/ 下；页面、JSON API 与 Agent
共用同一份分析结果，避免同一个指标出现两套算法。
"""
import json
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from analysis.food import get_food_analysis, recommend_food
from analysis.game import get_game_analysis
from analysis.retention import get_retention_analysis
from analysis.loan import get_loan_analysis
from analysis.rental import get_rental_analysis
from analysis.jobs import get_jobs_analysis

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

MODULES = [
    {
        "slug": "food", "icon": "🍽️", "title": "北京餐饮",
        "en": "RESTAURANT", "count": "44,512", "accent": "#22d3ee",
        "desc": "把 0 元人均识别为缺失值后，重新计算价格带、菜系、区域与评分；顺带检查评论集中度和米其林分层。",
        "tags": ["缺失值口径", "评论集中度", "价格分层"],
    },
    {
        "slug": "game", "icon": "🎮", "title": "游戏评论",
        "en": "GAME REVIEWS", "count": "2,531", "accent": "#8b5cf6",
        "desc": "VADER 文本情感与用户评分的对照：一致率只有 61.1%，玩家嘴上夸、手上打低分的情况真实存在。",
        "tags": ["VADER", "TF-IDF", "主题词典"],
    },
    {
        "slug": "retention", "icon": "📈", "title": "用户留存",
        "en": "RETENTION", "count": "20,301", "accent": "#34d399",
        "desc": "53 个注册周队列、8 周留存矩阵；首周流失 49.1%，渠道质量差异远大于设备差异。",
        "tags": ["队列分析", "条件流失", "渠道质量"],
    },
    {
        "slug": "loan", "icon": "🏦", "title": "贷款违约",
        "en": "CREDIT RISK", "count": "5,000", "accent": "#f59e0b",
        "desc": "随机森林 AUC 0.939、KS 0.735；按业务成本推导最优阈值 0.25，而不是默认的 0.5。",
        "tags": ["ROC / PR", "阈值收益", "概率校准"],
    },
    {
        "slug": "rental", "icon": "🏘️", "title": "北京租房",
        "en": "BEIJING RENTAL", "count": "35,082", "accent": "#60a5fa",
        "desc": "整租与合租必须分开算；面积与单价的关系主要是除法效应，配套字段几乎没有解释力。",
        "tags": ["分房型口径", "除法效应", "字段质量"],
    },
    {
        "slug": "jobs", "icon": "💼", "title": "数据岗招聘",
        "en": "DATA JOBS", "count": "3,523", "accent": "#f472b6",
        "desc": "解析混合格式薪资并剔除 49.9% 的伪数据岗；算法 25,000，数据分析 12,500。",
        "tags": ["薪资解析", "岗位去噪", "控制变量"],
    },
]

MODULE_MAP = {m["slug"]: m for m in MODULES}


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
        simulated = m['slug'] in ('retention', 'loan')
        source = '模拟数据' if simulated else '数据集分析'
        tags = ''.join(f'<span class="tag">{t}</span>' for t in m['tags'])
        cards.append(f"""<a class="module-card" href="/module/{m['slug']}" style="--accent:{m['accent']}">
          <div class="card-top"><span class="module-index">0{i+1} / {m['en']}</span><span class="source-badge {'simulated' if simulated else ''}">{source}</span></div>
          <div class="module-title"><span class="icon">{m['icon']}</span><h3>{m['title']}</h3></div>
          <p>{m['desc']}</p><div class="chips">{tags}</div>
          <div class="card-stats"><div><b>{m['count']}</b><span>条原始记录</span></div><span class="card-open">进入分析 ↗</span></div></a>""")
    return f"""<!DOCTYPE html><html lang="zh-CN"><head>{_head("工作台")}</head><body>
    {_topbar()}
    <main class="container dashboard">
      <section class="workspace-heading"><div><div class="eyebrow">OVERVIEW / 数据概览</div><h1>从数据出发，让洞察发生<span class="heading-dot">.</span></h1><p>六个业务场景，一个分析工作空间。选择数据集，探索指标背后的原因。</p></div><a class="btn" href="#datasets">浏览数据集 ↓</a></section>
      <section class="overview-stats" aria-label="平台数据概览">
        <div><span class="stat-caption">原始数据记录 <i>↗</i></span><strong>110,949<small>条</small></strong><span class="stat-foot">涵盖公开数据集与模拟样本</span></div>
        <div><span class="stat-caption">业务分析场景 <i>◫</i></span><strong>06<small>个</small></strong><span class="stat-foot">消费 · 文本 · 增长 · 风控 · 租房 · 招聘</span></div>
        <div><span class="stat-caption">数据来源构成 <i>▤</i></span><strong>4 <em>+</em> 2</strong><span class="stat-foot">4 个数据集 / 2 个模拟业务场景</span></div>
        <div><span class="stat-caption">分析方式 <i>✳</i></span><strong class="stat-text">可视化 + AI</strong><span class="stat-foot">图表探索与自然语言追问</span></div>
      </section>
      <section class="overview-row">
        <div class="panel distribution-panel"><div class="panel-head"><div><h2>数据集规模分布</h2><p>各模块原始记录数 · 清洗后样本以模块页为准</p></div><span class="mini-label">6 DATASETS</span></div><div id="datasetChart" class="chart" style="height:245px" role="img" aria-label="六个数据集记录数对比"></div></div>
        <div class="assistant-card"><span class="assistant-symbol">✳</span><div class="eyebrow">YOUR ANALYSIS COPILOT</div><h2>带着问题，<br>发现数据的另一面。</h2><p>从选择分析工具到引用计算结果，<br>让一次提问成为探索的起点。</p><a class="btn primary" href="/agent">开始与数据对话 <span>↗</span></a><span class="assistant-note">支持上下文追问与跨模块对比</span></div>
      </section>
      <section id="datasets"><div class="section-heading"><div><div class="eyebrow">EXPLORE / 开始探索</div><h2>选择你的分析场景</h2></div><label class="dataset-search"><span>⌕</span><input id="datasetSearch" type="search" placeholder="搜索场景、关键词…" aria-label="搜索分析场景"></label></div><div class="module-grid">{''.join(cards)}</div><p id="searchEmpty" class="search-empty" hidden>没有匹配的场景，试试“餐饮”“留存”或“薪资”。</p><div class="dataset-count" id="datasetCount" aria-live="polite">全部 6 个分析场景</div></section>
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
  <script src="/static/{slug}.js"></script>
</body></html>"""


@app.get("/module/food", response_class=HTMLResponse)
def page_food():
    return _module_page("food")


@app.get("/module/game", response_class=HTMLResponse)
def page_game():
    return _module_page("game")


@app.get("/module/retention", response_class=HTMLResponse)
def page_retention():
    return _module_page("retention")


@app.get("/module/loan", response_class=HTMLResponse)
def page_loan():
    return _module_page("loan")


@app.get("/module/rental", response_class=HTMLResponse)
def page_rental():
    return _module_page("rental")


@app.get("/module/jobs", response_class=HTMLResponse)
def page_jobs():
    return _module_page("jobs")


# ===== Agent =====
MODULE_LABELS = {
    "food": "北京餐饮",
    "game": "游戏评论",
    "retention": "用户留存",
    "loan": "贷款违约",
    "rental": "北京租房",
    "jobs": "数据岗招聘",
}

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

MODULE_KEYS = {
    "food": ["餐饮", "菜系", "餐厅", "美食", "人均消费", "米其林", "夜宵", "吃饭", "餐馆", "饭馆"],
    "game": ["游戏", "评论", "情感", "metacritic", "评分"],
    "retention": ["留存", "流失", "队列", "注册用户", "渠道", "拉新"],
    "loan": ["贷款", "违约", "风控", "信贷", "坏账", "auc", "ks"],
    "rental": ["租房", "租金", "房源", "整租", "合租", "房东"],
    "jobs": ["招聘", "岗位", "薪资", "求职", "就业", "数据岗", "月薪"],
}
# 模块专属词优先，避免「餐饮评分」同时命中 game 的「评分」
PRIMARY_KEYS = {
    "food": ["餐饮", "餐厅", "菜系", "美食", "米其林", "夜宵", "吃饭", "餐馆", "饭馆"],
    "game": ["游戏", "metacritic"],
    "retention": ["留存", "流失", "队列", "注册用户", "拉新"],
    "loan": ["贷款", "违约", "风控", "信贷", "坏账", "auc", "ks"],
    "rental": ["租房", "租金", "房源", "整租", "合租", "房东"],
    "jobs": ["招聘", "求职", "就业", "数据岗", "月薪", "薪资"],
}

AGENT_SYSTEM = """你是「全栈数据分析平台」的分析 Agent，服务对象是求职者和业务同学。
你可以调用 6 个分析模块的工具，每次调用返回该模块的完整统计结果。

工具列表（module + focus）：
- food：北京餐饮。focus = overview / price / cuisine / rating / district / michelin / late_night / recommend
  recommend 支持可选参数：district（如「丰台区」）、cuisine（如「火锅」）、min_price、max_price（元）
- game：游戏评论。focus = overview / sentiment / themes / platforms / keywords / polarization
- retention：用户留存。focus = overview / channels / devices / cohorts / hazard
- loan：贷款违约。focus = overview / metrics / thresholds / calibration / importance / segments
- rental：北京租房。focus = overview / districts / area / amenities / rent_types / attributes / trend
- jobs：数据岗招聘。focus = overview / cities / families / experience / education / company

规则：
1. 一次只调用一个工具。问题涉及多个模块或多个维度时，分多次调用。
2. 最多调用 3 次；信息足够后立即给最终回答。
3. 回答必须引用工具返回的具体数字，不要编造。
4. 如果用户在做比较，先分别取数，再给结论。
5. 用户问「推荐一家 / 吃什么 / 哪家好吃」时，必须调用 food + recommend，
   给出至少 3 家具体店名，并带区域、菜系、人均、评分、评论数；
   不要只回答「北京餐饮」或模块概览。
6. 调用 food + recommend 时，把用户提到的区域、菜系、预算放进 params，
   例如「丰台区 100 以内」→ {"district":"丰台区","max_price":100}。
   工具返回什么店就推荐什么店，不要自己编造店名。
7. 只回答当前问题。历史对话只用于理解「它 / 这个 / 再按城市拆一下」这类指代；
   不要把历史里问过的其他模块带进本轮回答，也不要无故调用其他模块的工具。
8. 用中文回答，简洁，先结论后依据。

只输出 JSON，格式示例：
{"action":"call","module":"food","focus":"price"}
{"action":"call","module":"food","focus":"recommend","params":{"district":"丰台区","max_price":100}}
{"action":"final","reply":"最终回答"}
"""


def _json_text(obj, limit=3200):
    s = json.dumps(obj, ensure_ascii=False, default=str, separators=(",", ":"))
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

    if module == "game":
        d = get_game_analysis()
        if focus == "sentiment":
            payload = {"overview": d["overview"], "sentiment_vs_rating": d["sentiment_vs_rating"],
                       "insights": d["insights"][:4]}
        elif focus == "themes":
            payload = {"themes": d["themes"], "insights": d["insights"][:4]}
        elif focus == "platforms":
            payload = {"platforms": d["platforms"], "polarization": d["polarization"],
                       "insights": d["insights"][:4]}
        elif focus == "keywords":
            payload = {"keywords": d["keywords"],
                       "insights": d["insights"][:4]}
        else:
            payload = {"overview": d["overview"], "rating_distribution": d["rating_distribution"],
                       "insights": d["insights"][:4]}
        return _json_text(payload)

    if module == "retention":
        d = get_retention_analysis()
        if focus == "channels":
            payload = {"channels": d["channels"], "insights": d["insights"][:4]}
        elif focus == "devices":
            payload = {"devices": d["devices"], "insights": d["insights"][:4]}
        elif focus == "cohorts":
            payload = {"overview": d["overview"],
                       "cohorts_first": d["cohorts"][:6],
                       "cohorts_last": d["cohorts"][-6:],
                       "cohort_trend": d["cohort_trend"][::4],
                       "insights": d["insights"][:4]}
        elif focus == "hazard":
            payload = {"hazard": d["hazard"], "average_curve": d["average_curve"],
                       "insights": d["insights"][:4]}
        else:
            payload = {"overview": d["overview"], "average_curve": d["average_curve"],
                       "insights": d["insights"][:4]}
        return _json_text(payload)

    if module == "loan":
        d = get_loan_analysis()
        if focus == "thresholds":
            payload = {"overview": d["overview"], "metrics": d["metrics"],
                       "thresholds": d["thresholds"], "insights": d["insights"][:5]}
        elif focus == "calibration":
            payload = {"calibration": d["calibration"], "insights": d["insights"][:5]}
        elif focus == "importance":
            payload = {"feature_importance": d["feature_importance"], "insights": d["insights"][:4]}
        elif focus == "segments":
            payload = {"segments": d["segments"], "insights": d["insights"][:4]}
        elif focus == "metrics":
            payload = {"overview": d["overview"], "metrics": d["metrics"],
                       "cv_scores": d["cv_scores"], "insights": d["insights"][:5]}
        else:
            payload = {"overview": d["overview"], "metrics": d["metrics"],
                       "insights": d["insights"][:5]}
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


def _call_llm(messages, temperature=0, timeout=45):
    if not DEEPSEEK_KEY:
        return None
    import time
    import requests as req
    for attempt in range(2):
        try:
            r = req.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}",
                         "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": messages,
                      "temperature": temperature},
                timeout=timeout,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except Exception:
            pass
        if attempt == 0:
            time.sleep(0.8)  # 网络抖动 / 429 时重试一次
    return None


def _parse_decision(text):
    if not text:
        return {}
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    try:
        return json.loads(s)
    except Exception:
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except Exception:
                pass
    # 模型偶尔直接输出自然语言：当作 final 回答，而不是丢掉后走通用兜底
    if s.startswith("{") or s.startswith("```"):
        return {}
    return {"action": "final", "reply": s}


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
    # 同一别名在不同模块下指向不同的工具名
    if module == "rental" and "district" in foci:
        foci[foci.index("district")] = "districts"
    return foci


def _infer_focus(module, text):
    foci = _infer_foci(module, text)
    return foci[0] if foci else "overview"


def _module_data(module):
    return {
        "food": get_food_analysis,
        "game": get_game_analysis,
        "retention": get_retention_analysis,
        "loan": get_loan_analysis,
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
        lines.append("米其林分层：" + "、".join(
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


def _game_answer(foci):
    d = get_game_analysis()
    o = d["overview"]
    lines, tools = [], []

    if "rating" in foci:
        p = d["polarization"]
        lines.append(
            f"评分中位 {o['median_rating']:.1f}/10，均值 {o['avg_rating']:.2f}/10；"
            f"极端评分（0–3 或 8–10）占 {_fmt_pct(p['extreme_pct'])}，"
            f"中间分段仅 {_fmt_pct(p['middle_pct'])}")
        tools.append("game.rating")

    if "sentiment" in foci:
        lines.append(
            f"VADER 文本情感：正面 {_fmt_pct(o['positive_pct'])}、负面 {_fmt_pct(o['negative_pct'])}、"
            f"中性 {_fmt_pct(o['neutral_pct'])}；与用户评分一致率 {_fmt_pct(o['agreement_pct'])}，"
            f"相关系数 {o['text_rating_corr']}")
        tools.append("game.sentiment")

    if "platforms" in foci:
        ps = d["platforms"]
        pos = max(ps, key=lambda x: x["positive_pct"])
        neg = max(ps, key=lambda x: x["negative_pct"])
        pol = max(ps, key=lambda x: x["polarization_pct"])
        lines.append(
            f"文本正面率最高 {pos['name']} {_fmt_pct(pos['positive_pct'])}；"
            f"负面率最高 {neg['name']} {_fmt_pct(neg['negative_pct'])}；"
            f"极化最高 {pol['name']} {_fmt_pct(pol['polarization_pct'])}")
        tools.append("game.platforms")

    if "themes" in foci:
        themes = d["themes"]
        top = max(themes, key=lambda x: x["mention_pct"])
        neg = max(themes, key=lambda x: x["negative_pct"])
        lines.append(
            f"提及最多：{top['label']} {_fmt_pct(top['mention_pct'])}；"
            f"负面率最高：{neg['label']} {_fmt_pct(neg['negative_pct'])}")
        tools.append("game.themes")

    if "keywords" in foci:
        lines.append("正面高频词：" + "、".join(
            x["term"] for x in d["keywords"]["positive"][:5]))
        lines.append("负面高频词：" + "、".join(
            x["term"] for x in d["keywords"]["negative"][:5]))
        tools.append("game.keywords")

    if "polarization" in foci:
        p = d["polarization"]
        lines.append(
            f"两极分化：极端评分占 {_fmt_pct(p['extreme_pct'])}；"
            f"好评率（8–10）{_fmt_pct(p['top_box_pct'])}，"
            f"差评率（0–3）{_fmt_pct(p['bottom_box_pct'])}")
        tools.append("game.polarization")

    return lines, tools


def _retention_answer(foci):
    d = get_retention_analysis()
    o = d["overview"]
    lines, tools = [], []

    if "channels" in foci:
        channels = sorted(d["channels"], key=lambda x: -x["values"][4])
        lines.append("渠道 W4 留存：" + "、".join(
            f"{x['name']} {_fmt_pct(x['values'][4])}（用户占 {_fmt_pct(x['share_pct'])}）"
            for x in channels))
        tools.append("retention.channels")

    if "devices" in foci:
        lines.append("设备 W4 留存：" + "、".join(
            f"{x['name']} {_fmt_pct(x['values'][4])}" for x in d["devices"]))
        tools.append("retention.devices")

    if "hazard" in foci:
        lines.append(
            f"首周流失 {_fmt_pct(o['first_week_churn'])}；"
            f"第 2 周条件流失 {_fmt_pct(d['hazard'][1]['churn_pct'])}，之后快速下降")
        tools.append("retention.hazard")

    if "cohorts" in foci:
        lines.append(
            f"{o['cohorts']} 个注册周队列；W4 留存从早期 {_fmt_pct(o['cohort_w4_early'])} "
            f"升至近期 {_fmt_pct(o['cohort_w4_late'])}"
            f"（+{o['cohort_w4_late'] - o['cohort_w4_early']:.1f}pp）")
        tools.append("retention.cohorts")

    if not lines:
        lines, tools = d["insights"][:4], ["retention.overview"]
    return lines, tools


def _loan_answer(foci):
    d = get_loan_analysis()
    o, m = d["overview"], d["metrics"]
    lines, tools = [], []

    if "thresholds" in foci:
        best = min(d["thresholds"], key=lambda x: abs(x["threshold"] - o["best_threshold"]))
        mid = min(d["thresholds"], key=lambda x: abs(x["threshold"] - 0.5))
        lines.append(
            f"收益最优阈值 {best['threshold']:.2f}：通过率 {_fmt_pct(best['approval_pct'])}、"
            f"坏账率 {_fmt_pct(best['bad_rate_pct'])}、违约召回 "
            f"{_fmt_pct(best['default_recall_pct'])}、测试集总期望收益 "
            f"{_fmt_money(best['expected_profit'])}")
        lines.append(
            f"对比默认 0.50：通过率 {_fmt_pct(mid['approval_pct'])}、"
            f"坏账率 {_fmt_pct(mid['bad_rate_pct'])}、违约召回 "
            f"{_fmt_pct(mid['default_recall_pct'])}、总收益 "
            f"{_fmt_money(mid['expected_profit'])}——坏账率翻倍，收益被坏账吃掉")
        tools.append("loan.thresholds")

    if "metrics" in foci:
        lines.append(
            f"随机森林 AUC {o['auc_rf']:.3f}（逻辑回归 {o['auc_lr']:.3f}）、"
            f"KS {o['ks']:.3f}、PR-AUC {m['pr_auc']:.3f}；默认阈值精确率 "
            f"{_fmt_pct(m['precision'] * 100)}、召回率 {_fmt_pct(m['recall'] * 100)}")
        tools.append("loan.metrics")

    if "calibration" in foci:
        lines.append("校准曲线 10 个分箱；高分段预测概率与实际违约率基本贴合，"
                     "模型输出可以直接当概率使用")
        tools.append("loan.calibration")

    if "importance" in foci:
        imp = sorted(d["feature_importance"],
                     key=lambda x: -x["permutation_auc_drop"])[:3]
        lines.append("置换重要性前三：" + "、".join(
            f"{x['feature']}（AUC 下降 {x['permutation_auc_drop']:.3f}）" for x in imp))
        tools.append("loan.importance")

    if "segments" in foci:
        seg = d["segments"]
        high_credit = max(seg["credit"], key=lambda x: x["default_pct"])
        high_debt = max(seg["debt"], key=lambda x: x["default_pct"])
        lines.append(
            f"违约率最高分群：信用分 {high_credit['band']} 为 "
            f"{_fmt_pct(high_credit['default_pct'])}；负债率 {high_debt['band']} 为 "
            f"{_fmt_pct(high_debt['default_pct'])}")
        tools.append("loan.segments")

    if not lines:
        lines, tools = d["insights"][:4], ["loan.overview"]
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
        "日度趋势反映抓取节奏，不是真实招聘周期")
    return lines, tools


_FALLBACK_BUILDERS = {
    "food": _food_answer,
    "game": _game_answer,
    "retention": _retention_answer,
    "loan": _loan_answer,
    "rental": _rental_answer,
    "jobs": _jobs_answer,
}


def _fallback_agent(msg, history):
    """没有 API Key / LLM 失败时的规则编排：调用同一分析层，按问题字段作答。"""
    msg_text = str(msg).lower()
    modules = _match_modules(msg_text, PRIMARY_KEYS) or _match_modules(msg_text, MODULE_KEYS)
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
        intro = (
            "我是全栈数据分析平台的 Agent，可以回答 6 个模块的问题：\n"
            "· 北京餐饮（价格带、菜系、区域、评分、米其林、夜宵）\n"
            "· 游戏评论（情感、评分对照、主题、平台）\n"
            "· 用户留存（队列矩阵、渠道、设备、流失）\n"
            "· 贷款违约（AUC/KS、阈值决策、校准、分群）\n"
            "· 北京租房（分房型区域价格、面积效应、配套）\n"
            "· 数据岗招聘（薪资解析、城市、经验、学历、岗位族）\n\n"
            "试试问：「北京哪个区餐厅最多？」"
            "「数据岗里哪个方向薪资最高？」「贷款阈值应该定多少？」"
        )
        if not DEEPSEEK_KEY:
            intro += "\n\n（当前未配置 DEEPSEEK_KEY，由本地规则引擎直接调用分析层。）"
        return {"reply": intro, "tools": []}

    sections, tools = [], []
    for m in modules[:2]:
        # 当前问题优先；追问没有字段词时，再从历史问题里继承上下文
        foci = _infer_foci(m, msg) or _infer_foci(m, text)
        lines, used = _FALLBACK_BUILDERS[m](foci)
        sections.append(
            f"【{MODULE_LABELS[m]}】\n" + "\n".join(f"· {x}" for x in lines)
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
        <p>用自然语言探索六个分析场景。回答引用分析工具的计算结果，支持连续追问与跨模块对比。</p><div class="agent-mode">{"✳ AI 工具编排模式" if DEEPSEEK_KEY else "◈ 本地规则模式 · 已连接分析工具"}</div>
      </div>

      <div class="chatbox" id="chatbox" role="log" aria-label="分析对话" aria-live="polite">
        <div class="msg agent">👋 你好，我是数据分析 Agent。可以问我北京餐饮的真实人均、具体餐厅推荐、游戏评论的情感与评分错位、留存渠道差异、贷款阈值、租房口径或数据岗薪资。也可以连续追问，比如「数据岗哪个方向薪资最高？再按城市拆一下」。</div>
      </div>

      <div class="suggestions">
        <button data-q="北京餐饮人均消费的真实中位数是多少？为什么不能直接用平均值？">餐饮真实人均</button>
        <button data-q="我想去北京吃饭，帮我推荐一家评分高、评论多的店">餐厅推荐</button>
        <button data-q="游戏评论文本情感和用户评分为什么会对不上？">情感与评分错位</button>
        <button data-q="哪个渠道的用户留存最好？广告投放值得继续吗？">渠道留存质量</button>
        <button data-q="贷款模型的阈值应该定多少？为什么不是 0.5？">贷款最优阈值</button>
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
  <script src="/static/agent.js"></script>
</body></html>"""


@app.post("/api/agent/chat")
async def agent_chat(req: dict):
    msg = str(req.get("message", "")).strip()
    if not msg:
        return {"reply": "请输入问题", "tools": []}

    raw_history = req.get("history") or []
    history = []
    if isinstance(raw_history, list):
        for h in raw_history[-8:]:
            if not isinstance(h, dict):
                continue
            role = h.get("role")
            if role not in ("user", "assistant"):
                continue
            content = str(h.get("content", ""))[:1200]
            if content:
                history.append({"role": role, "content": content})

    # 兼容旧前端：历史里若已经包含当前问题，去掉重复项
    if history and history[-1]["role"] == "user" and history[-1]["content"].strip() == msg:
        history.pop()

    # 有 Key：多轮工具编排
    if DEEPSEEK_KEY:
        # 「推荐一家餐厅」这类请求必须落到具体店铺，不能只回模块概览
        wants_food_rec = (
            any(k in msg for k in ("推荐", "哪家", "好吃", "吃什么", "吃哪"))
            and any(k in msg for k in PRIMARY_KEYS["food"])
        )
        observations = []
        tools_used = []
        for _ in range(3):
            messages = [{"role": "system", "content": AGENT_SYSTEM}]
            messages += history
            messages.append({"role": "user", "content": msg})
            messages += observations
            out = _call_llm(messages)
            decision = _parse_decision(out)
            action = decision.get("action")

            if action == "final":
                if wants_food_rec and not tools_used:
                    # LLM 想直接收尾：强制先取推荐工具，再让它基于真实店名回答
                    action = "call"
                    decision = {"action": "call", "module": "food", "focus": "recommend"}
                else:
                    reply = str(decision.get("reply", "")).strip()
                    if reply:
                        return {"reply": reply, "tools": tools_used}
                    break

            module = str(decision.get("module") or decision.get("tool") or "").lower()
            if action in ("call", "tool") and module in MODULE_LABELS:
                focus = _normalize_focus(decision.get("focus", "overview"))
                if wants_food_rec and module == "food" and not tools_used:
                    focus = "recommend"
                try:
                    result = _agent_tool(module, focus, decision.get("params"))
                except Exception as e:
                    result = _json_text({"error": f"工具执行失败：{e}"})
                tools_used.append(f"{module}.{focus}")
                observations.append({
                    "role": "assistant",
                    "content": json.dumps(decision, ensure_ascii=False),
                })
                observations.append({
                    "role": "user",
                    "content": (
                        f"工具 {module}.{focus} 返回：\n{result}\n\n"
                        "请判断信息是否足够：足够则输出 "
                        '{"action":"final","reply":"..."}；'
                        "否则继续调用下一个工具。"
                    ),
                })
                continue
            break

        # 调用过工具但没给出最终回答：让 LLM 基于观察结果收尾
        if observations:
            messages = [{"role": "system", "content": AGENT_SYSTEM}]
            messages += history
            messages.append({"role": "user", "content": msg})
            messages += observations
            messages.append({
                "role": "user",
                "content": "请直接给出最终回答，不要再调用工具。",
            })
            out = _call_llm(messages)
            decision = _parse_decision(out)
            if decision.get("reply"):
                return {"reply": str(decision["reply"]), "tools": tools_used}
        # LLM 失败：落到规则引擎（工具标签必须与最终回答一致）
        fallback = _fallback_agent(msg, history)
        return {"reply": fallback["reply"], "tools": fallback["tools"]}

    # 无 Key：规则编排
    fallback = _fallback_agent(msg, history)
    return {"reply": fallback["reply"], "tools": fallback["tools"]}


# ===== JSON API =====
@app.get("/api/food")
def api_food():
    """北京餐饮完整分析结果，供页面 / Agent 复用。"""
    return JSONResponse(get_food_analysis())


@app.get("/api/game")
def api_game():
    """游戏评论：VADER 文本情感 + 评分对照 + 主题词典。"""
    return JSONResponse(get_game_analysis())


@app.get("/api/retention")
def api_retention():
    """用户留存：注册周队列矩阵 + 渠道/设备差异。"""
    return JSONResponse(get_retention_analysis())


@app.get("/api/loan")
def api_loan():
    """贷款违约：ROC/PR、KS、阈值决策、校准与分群。"""
    return JSONResponse(get_loan_analysis())


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


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
