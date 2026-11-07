# 全栈数据分析平台

FastAPI + Pandas + Scikit-learn + ECharts 的一体化数据分析平台：约 284.2 万条主要记录（不同记录单位的样本数之和）、7 个业务模块、统一分析层、JSON API，以及支持一次规划最多 3 个工具、流式回答和调用诊断（无 API Key 或调用失败时降级为规则引擎）的 AI Agent。

在线地址：https://data-platform-vp73.onrender.com

## 功能模块

| 模块 | 数据量 | 核心内容 |
|---|---:|---|
| 北京餐饮 | 44,512 家店铺 | 缺失价格与评分、菜系与区域、评论集中度、原始推荐标签 |
| 麦当劳消费者调查 | 1,453 份问卷 | 品牌属性、好感规则分组、到访频率与年龄差异 |
| 美国房价 | 1,460 条已知售价 | Ames历史房屋成交售价、社区与质量、独立留出模型验证 |
| 国产电影 | 120 部电影 | 类型多标签、票房与评分关联、筛选与逐片截止日期 |
| 北京租房 | 35,082 条房源 | 分房型区域租金、面积和单价关系、配套字段质量 |
| 数据岗招聘 | 3,523 条岗位 | 薪资解析、岗位去噪、城市及经验学历结构 |
| 电商行为 | 2,756,101 条事件 | Retailrocket有序漏斗、真实D1/D7/D30与周回访、属性时点 |

AI Agent接入以上七个模块；页面、JSON API和问答共用分析结果。
美国房屋为**美元/套成交售价、平方英尺面积**，北京房屋为**人民币/月租金、平方米面积**，不直接比较两者价格高低。
美国另有1,459条未公开售价的Kaggle测试记录，仅展示其规模，不计入售价统计、模型评分或首页主要样本总数。

## 模块替换与分析口径

- 旧游戏评论、贷款违约、模拟注册留存退出导航、API与AI工具目录；源文件保留以便回退。
- 旧页面分别重定向到消费者调查、国产电影与电商行为；旧API返回HTTP 410及替代模块，防止旧客户端误读新数据。
- 美国房价平台模型独立重算：80/20留出，seed=42，训练集内拟合插补和编码，随机森林拟合log1p售价，比较中位数基线。不是原项目Kaggle排行榜成绩，不是时间外验证。
- 电影为120部历史样本，各影片截止日不同；类型采用完整多标签计数，不能累加当独立电影数或估计年度全市场规模。
- 问卷按好感分正/零/负分组，不称自动聚类；属性为有效Yes/No中Yes占比，关联不能写成因果。
- 餐饮原始“米其林推荐指数”的银牌、金牌等标签来源未核实，界面使用“原始推荐标签”，不称官方米其林评级。
- 回访使用Retailrocket真实匿名行为；首次观察不等于注册，第7日回访不等于7天内回访。

## 架构

```
data_platform/
├── app.py                  # FastAPI 入口：页面 + JSON API + Agent
├── agent_runtime.py        # 异步模型调用、工具规划、流式事件与诊断日志
├── analysis/               # 纯计算分析层（无 HTML / 无绘图）
│   ├── data.py             # 数据加载缓存 + JSON 序列化
│   ├── food.py
│   ├── portfolio.py        # 美国房价 / 国产电影 / 消费者调查
│   ├── game.py             # 旧文件保留，不注册为活动模块
│   ├── retention.py        # 旧模拟模块，不再提供服务
│   ├── loan.py             # 旧模拟模块，不再提供服务
│   ├── rental.py
│   └── jobs.py
│   └── retailrocket.py     # Retailrocket MySQL汇总快照与统一API口径
├── static/
│   ├── cover.html          # 封面页骨架
│   ├── cover.css / cover.js # 封面样式与数据球动画
│   ├── shell.js            # 模块页章节导航 / 图表导出
│   ├── workspace.js        # 工作台数据集搜索与规模图
│   ├── app.css             # 设计系统：深色主题 / 响应式
│   ├── common.js           # KPI / 面板 / 表格 / ECharts 封装
│   ├── food.js … jobs.js   # 保留模块的页面脚本
│   ├── portfolio.js        # 消费者调查 / 美国房价 / 国产电影
│   ├── agent.js            # 对话交互
│   └── echarts.min.js      # 已内置，离线可用
├── data/
│   ├── beijing_rental.csv  # 35,082 条
│   ├── job_data.csv        # 3,523 条
│   ├── movies.xlsx         # 120部电影
│   ├── mcdonalds.csv       # 1,453份问卷
│   ├── housing/            # 原始train/test和字段说明
│   └── retailrocket/       # MySQL汇总快照
├── bj_food_analysis.xlsx   # 44,512 条
├── Metacriticgames8.csv    # 2,531 条
└── requirements.txt
```

分析层统一暴露 `get_xxx_analysis() -> dict`，页面、JSON API、Agent 复用同一份结果，避免业务口径分叉。

前端不依赖 Vue/React 或构建工具：FastAPI 返回页面骨架，浏览器端 `fetch` JSON API 后用 ECharts 渲染交互图表，首屏与部署都很轻。入口为封面页 `/`，工作台在 `/workspace`；工作台支持数据集搜索与规模分布图，模块页支持章节导航、图表导出、响应式布局与键盘跳转。

## JSON API

| 接口 | 内容 |
|------|------|
| `GET /api/food` | 餐饮价格/菜系/区域/评分/原始推荐标签/夜宵/推荐候选 |
| `GET /api/survey` | 问卷属性、好感分组、年龄和到访频率 |
| `GET /api/housing` | Ames成交售价、社区与质量、模型与基线验证 |
| `GET /api/movies` | 电影票房、评分、类型标签、逐片截止日期 |
| `GET /api/rental` | 房型、区域、面积、配套、月度趋势、地图抽样 |
| `GET /api/jobs` | 薪资、城市、经验、学历、公司、岗位族 |
| `GET /api/retailrocket` | 真实电商快照来源、每日/星期/小时、漏斗与窗口、回访、类别、可售状态 |
| `POST /api/agent/chat` | 兼容 JSON 接口；返回 `reply / tools / source / request_id / elapsed_ms / fallback_reason` |
| `POST /api/agent/chat/stream` | 同样的 `{message, history}` 输入；逐行 JSON，事件为 `status / delta / heartbeat / done` |

## 全栈平台的 AI Agent：工具与上下文

全栈数据分析平台的 Agent 不让 LLM 直接算数：LLM 只负责选择工具和组织语言，所有数字都来自 `analysis/*.py` 的 Pandas / Scikit-learn 计算。

- **按字段拆工具**：例如 `housing.validation`、`survey.attributes`、`movies.ratings`、`retailrocket.retention`、`rental.rent_types`、`food.recommend`。
- **具体餐厅推荐**：全栈平台的 `food.recommend` 支持区域、菜系、价格四类筛选条件：`district / cuisine / min_price / max_price`。默认只在「评分非空 + 评论数 ≥ 50」的 3,310 家店里推荐，避免 1 条评论的 5.0 分；样本不足时依次放宽到 10 条评论、只要评分非空，并在返回里标 `relaxed`。
- **推荐约束**：推荐请求必须经过 `food.recommend`，保留模型提取的区域、菜系和预算；缺少推荐计划时明确降级，不把未经查询的模型回答当作数据推荐。
- **历史隔离（多轮对话）**：多轮历史只用于理解「它 / 这个 / 再按城市拆一下」这类指代；模块识别以当前问题为准，只有当前问题没提模块时，才继承最近一条带模块的历史，避免前面问过租房、后面每个问题都带租房，导致回答串模块。
- **减少等待**：常见问候与致谢直接回复；多个分析维度一次规划，最多执行 3 个工具。正常数据问题通常只需一次规划请求和一次答案请求，取代原先多轮规划。规划启用 JSON 输出，最终答案使用上游流式响应。
- **异步与取消**：用 HTTPX 异步请求，数据工具在线程中执行，等待大模型时不会堵住其他页面请求。前端显示真实处理阶段、等待秒数和逐步生成的正文；“停止”会取消请求。已启动的同步数据计算线程不能强行中止。
- **有界等待**：连接超时 5 秒，上游空闲读取超时默认 20 秒，整轮处理预算默认 45 秒。仅快速返回的 429/500/502/503/504 重试一次；认证、余额、权限错误及超时不重试。兜底最多另外等待 8 秒；浏览器 120 秒上限还包括免费实例的冷启动。
- **降级一致**：模型失败、JSON 解析失败、流式中断都记录原因并返回本地分析；页面明确标记来源，失败前的部分模型正文会被完整替换，不拼接为成功回答。

## 本地运行

```bash
pip install -r requirements.txt
# 方式一：复制 .env.example 为 .env，填入 DEEPSEEK_KEY（推荐，不会被提交）
# 方式二：set DEEPSEEK_KEY=sk-xxx
python app.py
```

不设置 Key 时 Agent 自动使用规则编排，页面与七个 JSON API 不受影响。

访问 http://127.0.0.1:8000

活动模块不再加载VADER情感词典；ECharts已内置于 `static/`，新模块数据均在 `data/`，不依赖同级项目或外部数据库。首次访问美国房价接口会计算并缓存固定留出验证结果。

## 数据说明

- 餐饮、租房、招聘、电影、消费者调查由作者从和鲸社区、天池等公开数据社区下载整理，原始下载链接未保留。该说法记录作者提供的下载背景，不意味着每份文件均已独立追溯到同一网站。
- 美国房价来自Kaggle House Prices比赛；Retailrocket来源链接随模块与快照说明保留。
- 历史样本用于学习与能力展示；选样规则、缺失、时间窗口及外推边界在各模块说明。
- 详细数据位置、来源与核实状态见 [数据来源说明](docs/data_sources.md)。

## AI 调用日志与部署

本地修改不会自动更新线上服务。提交并推送代码到 Render 连接的 GitHub 分支后，部署新版本；构建仍需 `pip install -r requirements.txt`，新版本增加了 HTTPX 依赖。启动命令仍为 `python app.py`。

Render 的 Environment 必须配置 `DEEPSEEK_KEY`，不能将 `.env` 或密钥提交到 Git。可选环境变量：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `DEEPSEEK_READ_TIMEOUT` | `20` | 上游空闲读取超时秒数 |
| `AGENT_TIMEOUT_SECONDS` | `45` | 规划、重试、取数、生成的整轮处理预算 |
| `DEEPSEEK_MAX_TOKENS` | `800` | 每次模型请求的输出 token 上限 |

日志直接输出到服务标准错误流，在 Render Logs 中可见。以 `request_id` 关联同一轮对话，关注 `llm_response` 的 `status`、`agent_fallback` 的 `reason`，以及 `agent_done` 的 `source / elapsed_ms`。日志不记录 API Key、认证头、问题正文、模型正文或上游响应正文。

典型事件包括 `agent_start`、`llm_request`、`llm_response`、`llm_first_text`、`tool_done`、`llm_parse_failure`、`agent_timeout`、`agent_fallback`、`agent_done`。例如（仅示例）：

```json
{"event":"llm_response","request_id":"example","phase":"plan","attempt":1,"status":401,"elapsed_ms":300}
{"event":"agent_fallback","request_id":"example","reason":"http_401"}
```

常见兜底原因：`missing_key`、`http_401`、`http_402`、`http_403`、`http_429`、`upstream_timeout`、`total_timeout`、`network_error`、`invalid_json`、`invalid_plan`、`incomplete_stream`。浏览器最终结果的 `source` 为 `llm`（模型）、`rules`（本地规则）、`local`（快捷回复）或 `error`。

免费 Render 实例从休眠唤醒的时间发生在应用接收请求之前，以上优化不能消除冷启动；页面的模式提示也仅表示配置了非空密钥，不是上游连通性检查。

## AI 模块验证

不调用真实模型的自动测试：

```bash
python -m unittest discover -s tests -v
node tests/test_agent_frontend.cjs
```

覆盖快捷回复、无密钥、401、超时、短暂 HTTP 故障重试、JSON 解析、批量工具规划、推荐筛选、流式中断、整轮预算、请求取消、并发等待、旧接口兼容，以及前端 UTF-8 分块、历史记录、兜底替换与停止操作。


## Retailrocket 电商模块（新增）

页面 `/module/retailrocket`，接口 `/api/retailrocket`。已接入封面、侧栏、工作台、规模分布和AI工具目录。原来的模拟注册留存模块已退出服务；电商模块展示真实匿名数据的首次观察访客回访。

### 数据架构与部署

平台读取 `data/retailrocket/` 中10份小型MySQL汇总CSV及manifest.json，不连接开发电脑的localhost MySQL，不包含原始276万行日志，不需要新增数据库密码或SQLAlchemy依赖。页面明确显示非实时、2015年历史样本、UTC、快照导入时间及CC BY-NC-SA 4.0数据许可。数据来源：[Kaggle](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset)，完整独立分析：[GitHub](https://github.com/overlxrd123/retailrocket-business-analysis)。

快照在独立分析项目中通过Python连接MySQL生成。重新运行独立项目绘图导出后，在平台根目录执行：

```powershell
python scripts/refresh_retailrocket.py --results-dir "D:\retailrocket-analysis\results"
```

工具会先检查10份输入及关键总数，再替换快照、记录文件SHA-256和导入时间。批量刷新不是跨文件数据库事务，请在维护时执行并重启服务，避免服务读取到刷新中的混合版本。导入时间不是数据采集时间。固定全期访客数来自本数据集已核对的visitor_summary，不能改用每日人数之和替代，也不能把该工具当作任意新数据集通用导入器。

启动仍为 `python app.py`。本地源代码不会自动更新Render，提交、推送和部署须另行执行。平台已有未提交更改，本次没有执行Git提交或远程推送。

### 交互与口径

- 每日趋势支持起止日期、活跃/购买/占比切换、缩放。日期筛选仅影响趋势图，7日滚动指标先按完整样本计算，不在筛选起点重置。
- 星期、7月周末与小时分布、有序漏斗、共同样本窗口、精确日回访、周热力图、类别和可售状态共10个交互图表。
- 漏斗单位是访客—商品对，要求同商品有严格浏览→加购→购买时间顺序。主漏斗至少24小时观察期，窗口比较共同要求7天观察期，两组分母不同。
- D7为精确第7个UTC自然日，周回访第1周为首次观察后第7—13天。首个不完整入群周、第0周不在热图展示；不成熟格子灰色，不能当作零。
- 类别未知保留。最后已知不可售不等同于确定缺货；未知不等于不可售。状态构成各柱分母不同，不是状态导致购买的因果比较。
- Agent注册 `retailrocket.overview / trend / funnel / retention / products`；无密钥时规则回答也引用同一分析层。未在本次测试中调用真实模型，既有模型降级测试与新增接口测试均使用本地/模拟响应。

### 验证

```powershell
python -m unittest discover -s tests -v
node --check static/retailrocket.js
node tests/test_agent_frontend.cjs
```

新增测试核对2,756,101条事件、137完整日、漏斗和窗口数量、留存分子、JSON空值及路由/Agent工具。没有运行新的A/B实验，也不声称上线后实现营收或转化提升。

## 本地验证

```bash
python -m unittest discover -s tests -p "test_*.py"
node tests/test_agent_frontend.cjs
node --check static/portfolio.js
```

新增回归覆盖电影多标签对账、问卷分母和好感编码、美国已知/未知售价隔离与验证误差复算、旧路由退出及新模块问答。
