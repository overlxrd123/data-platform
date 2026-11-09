"""业务问题→量化证据→建议→验证；建议均为待验证动作，不声称已实现收益。"""
from functools import lru_cache
import numpy as np
from .portfolio import get_movies_analysis, get_survey_analysis, get_housing_analysis, clean
from .food import get_food_analysis
from .jobs import get_jobs_analysis
from .rental import get_rental_analysis
from .retailrocket import get_retailrocket_analysis

LOADERS = dict(movies=get_movies_analysis, survey=get_survey_analysis, housing=get_housing_analysis,
               food=get_food_analysis, jobs=get_jobs_analysis, rental=get_rental_analysis,
               retailrocket=get_retailrocket_analysis)


@lru_cache(maxsize=7)
def get_brief(slug):
    d = LOADERS[slug]()
    o = d['overview']
    detail = None
    if slug == 'movies':
        rows = sorted(d['movies'], key=lambda r: r['revenue_yi'], reverse=True)
        total = sum(r['revenue_yi'] for r in rows)
        share = 100 * sum(r['revenue_yi'] for r in rows[:10]) / total
        # Sensitivity to a single blockbuster; retain the original full sample.
        pairs = [(r['douban'], r['revenue_yi']) for r in rows if r['douban'] is not None]
        corr = lambda a: float(np.corrcoef([r[0] for r in a], np.log1p([r[1] for r in a]))[0, 1])
        detail = {'title':'票房集中度与头部敏感性', 'headers':['统计项','数值','解释'], 'rows':[
            ['Top10票房占样本合计',f'{share:.1f}%','同一份120部电影样本，不是全国市场份额'],
            ['全部电影：豆瓣与log票房相关',f'{corr(pairs):.3f}',f'{len(pairs)}部有效配对'],
            ['去掉票房最高一部后的相关',f'{corr(pairs[1:]):.3f}',f'{len(pairs)-1}部；仅敏感性对照，原样本不删除']]}
        problem='电影评分与票房的关系，是否被少量头部影片影响？'
        evidence=f'Top10电影占样本累计票房的{share:.1f}%；应结合中位数和去掉最大值后的相关系数判断。'
        interpretation='大票房影片会明显影响总量；样本的类型结构和评分平台差异，也会改变相关结果。'
        action='选取同类型、相近上映时期的电影做案例比较，避免只用总榜推断哪类电影更值得投资。'
        verification='扩大同类型样本并统一观察截止窗口；检查不同分组和极端值处理下，结论方向是否一致。'
    elif slug == 'survey':
        # Cross-tab uses original questionnaire categories, not generated labels.
        import pandas as pd
        from .portfolio import DATA
        raw = pd.read_csv(DATA/'mcdonalds.csv')
        score = pd.to_numeric(raw['Like'].str.extract(r'([+-]?\d+)$')[0], errors='coerce')
        frequent = raw['VisitFrequency'].isin(['Once a month','Once a week','More than once a week'])
        positive = score > 0
        cells = [(name,int(mask.sum())) for name,mask in [
            ('有好感·每月及以上',positive & frequent),('有好感·低于每月',positive & ~frequent),
            ('中立或负向·每月及以上',~positive & frequent),('中立或负向·低于每月',~positive & ~frequent)]]
        detail={'title':'好感与到访频率交叉分组','headers':['人群','样本数','占全部问卷'],
                'rows':[[name,str(n),f'{100*n/len(raw):.1f}%'] for name,n in cells]}
        target=cells[1][1]
        problem='喜欢麦当劳但到访不频繁的人群，有多大？'
        evidence=f'{target}名受访者好感分大于0、到访低于每月一次，占全部问卷{100*target/len(raw):.1f}%。'
        interpretation='这类人群可以作为进一步访谈对象，但低频原因可能是距离、价格、饮食习惯，不能直接认定发券有效。'
        action='先访谈有好感的低频人群，按便利性、价格和产品需求分类，再设计小范围触达方案。'
        verification='如后续开展真实实验，应随机设置触达组与对照组，比较增量到访，并同时观察优惠成本与退订率。'
    elif slug == 'housing':
        rows=d['validation']
        detail_rows=[]
        for name,lo,hi in [('低价：<15万美元',0,150000),('中价：15–30万美元',150000,300000),('高价：≥30万美元',300000,float('inf'))]:
            group=[r for r in rows if lo<=r['actual']<hi]
            errors=[r['predicted']-r['actual'] for r in group]
            detail_rows.append([name,str(len(group)),f'${np.mean(np.abs(errors)):,.0f}' if group else '—',f'${np.mean(errors):+,.0f}' if group else '—'])
        detail={'title':'不同价位的验证误差','headers':['真实售价区间','验证房屋数','MAE','平均预测偏差'], 'rows':detail_rows}
        gain=100*(1-d['metrics']['mae_usd']/d['metrics']['baseline_mae_usd'])
        problem='模型是否比简单基线更准，误差是否集中在特定价位？'
        evidence=f"同一{len(rows)}套验证房屋上，MAE相比训练集售价中位数基线降低{gain:.1f}%；分价位检查仍然必要。"
        interpretation='平均误差会掩盖高价房和少见房屋的风险；平均预测偏差为负表示低估，为正表示高估。'
        action='把模型定位为历史样本估价辅助；优先人工复核误差较大的价位，不能把单次随机留出成绩当未来保证。'
        verification='下一步按成交年份留出，并比较各价位误差稳定性；只在训练数据中调整模型，再用独立测试集评估。'
    elif slug == 'food':
        problem='如何用当前样本筛选价格合适、评价信息较充分的餐厅？'
        evidence=f"价格有效样本{o['stores_with_price']:,}家，覆盖{o['price_coverage_pct']}%；有效人均中位数{o['price_median']}元，评分覆盖{o['rating_coverage_pct']}%。"
        interpretation='人均为0不能当免费；缺评分的餐厅不能按0分排名，低评论量的高分也可能不稳定。'
        action='先选区域、菜系与预算，再结合评分和评论量生成候选；推荐时显示放宽条件，不保证当前营业和价格。'
        verification='抽查候选店最新价格与营业状态；比较不同评论量门槛下推荐名单是否稳定。'
    elif slug == 'rental':
        types={r['name']:r for r in d['rent_types']}
        problem='租房预算应按整租还是合租、哪些区域来比较？'
        evidence='；'.join(f"{name}中位月租{r['rent_median']:,.0f}元、面积{r['area_median']}㎡" for name,r in types.items())+'。'
        interpretation='整租和合租的面积结构不同，混合中位数不能直接作为同一种房型的预算。单价还受总价÷面积的机械关系影响。'
        action='先确定房型与预算，再在同房型下比较区域租金、面积和单价；不根据当前样本宣称地铁或学区溢价。'
        verification='对候选区域抽查当前挂牌；收集同区域、同房型、相近面积的可比房源，检查差异是否仍存在。'
    elif slug == 'jobs':
        problem='求职者应优先比较哪些岗位，而不是只看整体平均薪资？'
        evidence=f"{o['postings']:,}条记录中，数据相关岗位占{o['data_job_share_pct']}%；薪资可解析覆盖{o['salary_parsed_pct']}%。"
        interpretation='岗位名称包含噪声，整体薪资混有不同职能、经验和城市结构；城市高薪不能直接解读为同岗溢价。'
        action='先筛岗位族，再比较城市和经验要求；统一月薪与发薪月数，结合岗位数量制定投递清单。'
        verification='补充具体JD、岗位链接和最新招聘日期，再核对职责与技能要求；不从当前集中日期推断招聘趋势。'
    else:
        funnel=d['funnel']; start,cart,buy=[int(r['pair_count']) for r in funnel]
        problem='同一访客、同一商品的浏览→加购→购买，主要流失在哪一步？'
        evidence=f'{start:,}对起点样本中，{cart:,}对随后加购（{100*cart/start:.2f}%），{buy:,}对完成有序购买（{100*buy/start:.2f}%）。'
        interpretation='漏斗单位为访客—商品对，不是人数或订单；加购前流失较多，但没有页面交互和曝光数据，不能直接断定原因。'
        action='优先核查商品信息、可售属性时点和加购入口埋点，再用真实实验验证改版；未知属性不直接填成不可售。'
        verification='实验须有真实随机分组；主指标使用一致窗口的有序购买率，观察加购率、延迟购买与异常事件等辅助指标。'
    return clean(dict(question=problem,evidence=evidence,interpretation=interpretation,action=action,
                      verification=verification,detail=detail,status='分析建议与待验证假设；尚未实施，不代表已获得业务收益。'))
