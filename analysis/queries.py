"""七模块白名单只读查询；筛选后统计总数，再分页，绝不执行生成的SQL。"""
import re
from functools import lru_cache

COMMON={'keyword','view','sort_by','order','limit','offset'}
FILTERS={
 'movies':{'genre','min_score','min_price','max_price'},
 'food':{'district','cuisine','min_score','min_price','max_price'},
 'rental':{'district','rent_type','min_price','max_price','min_area','max_area'},
 'housing':{'neighborhood','min_price','max_price','min_area','max_area'},
 'jobs':{'city','family','education','experience','min_price','max_price'},
 'survey':set(), 'retailrocket':{'start_date','end_date'},
}
VIEWS={'survey':{'attributes','visits','ages','segments'},'retailrocket':{'daily','retention','funnel','categories','availability'}}
SORTS={'movies':{'name','revenue_yi','douban','maoyan'},'food':{'name','price','rating','reviews'},
       'rental':{'id','price','area'},'housing':{'id','price','area'},'jobs':{'name','price'},
       'survey':{'name','count','yes_pct','mean_like'},'retailrocket':{'event_date_utc','day_n','pair_count','total_events','purchase_events','active_visitors','buying_visitors','daily_buyer_rate_pct','retention_rate_pct'}}


def validate_params(module, params):
    if module not in FILTERS or not isinstance(params,dict):raise ValueError('query params must be an object')
    p=dict(params)
    if set(p)-(COMMON|FILTERS[module]):raise ValueError('unsupported query field')
    for k in ['limit','offset']:
        v=p.get(k,8 if k=='limit' else 0)
        if isinstance(v,bool) or not isinstance(v,int) or not (1<=v<=20 if k=='limit' else 0<=v<=100000):raise ValueError('invalid pagination')
        p[k]=v
    for k,v in p.items():
        if k.startswith(('min_','max_')):
            import math
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError('invalid numeric bound')
        elif k not in ('limit','offset') and (not isinstance(v,str) or len(v)>100):raise ValueError('invalid text filter')
    for suffix in ['price','score','area']:
        if p.get('min_'+suffix,0)>p.get('max_'+suffix,float('inf')):raise ValueError('reversed bounds')
    if p.get('order','desc') not in ('asc','desc'):raise ValueError('invalid order')
    if 'sort_by' in p and p['sort_by'] not in SORTS[module]:raise ValueError('invalid sort')
    if 'view' in p and p['view'] not in VIEWS.get(module,{'records'}):raise ValueError('invalid view')
    if module=='survey' and 'sort_by' in p:
        columns={'attributes':{'name','yes_pct'},'visits':{'name','count','mean_like'},'ages':{'name','count','mean_like'},'segments':{'name','count'}}
        if p['sort_by'] not in columns[p.get('view','attributes')]:raise ValueError('sort not supported by view')
    if module=='retailrocket' and any(k in p for k in ('start_date','end_date')) and p.get('view','daily')!='daily':raise ValueError('date filters require daily view')
    for k in ('start_date','end_date'):
        if k in p:
            from datetime import date
            date.fromisoformat(p[k])
    if p.get('start_date','')>p.get('end_date','9999-12-31'):raise ValueError('reversed dates')
    return p


@lru_cache(maxsize=16)
def _table(module,view):
    import pandas as pd
    from .portfolio import get_movies_analysis,get_survey_analysis,get_housing_analysis
    from .data import load_rental,load_jobs
    if module=='movies':return pd.DataFrame(get_movies_analysis()['movies']), 'revenue_yi','票房亿元；评分/10；逐片截止日见snapshot'
    if module=='housing':
        return pd.DataFrame(get_housing_analysis()['scatter']).rename(columns={'area_sqft':'area'}),'price','美元/套成交售价；面积平方英尺，不是月租金'
    if module=='rental':
        d=load_rental().rename(columns={'rent_price':'price'})
        return d[['id','district','community','rent_type','price','area']].copy(),'price','人民币/月挂牌租金，面积平方米'
    if module=='food':
        from .food import _prepared
        d=_prepared().rename(columns={'店铺名称':'name'})
        d=d[['name','district','cuisine','price','rating','reviews']].copy()
        d['price']=d['price'].where(d['price']>0)
        return d,'rating','人均人民币；未知价格为null，不是免费；历史样本非实时推荐'
    if module=='jobs':
        from .jobs import _parse_salary,_family
        d=load_jobs().rename(columns={'岗位名称':'name','公司所在城市地点':'city','薪资':'salary','公司名称':'company','工作经验':'experience','学历要求':'education'})
        d=d[['name','city','salary','company','experience','education']].copy()
        d['family']=d['name'].map(_family)
        d['price']=d['salary'].map(lambda s:sum(_parse_salary(s)[:2])/2)
        d=d[d['family']!='非数据/其他']
        return d,'price','price为税前月薪区间中点（人民币）；保留原始salary，不代表录用薪资'
    if module=='survey':
        d=pd.DataFrame(get_survey_analysis()[view])
        return d,('yes_pct' if view=='attributes' else 'count'),'麦当劳调查汇总；好感分-5至+5，不返回个人问卷'
    from .retailrocket import get_retailrocket_analysis
    d=pd.DataFrame(get_retailrocket_analysis()[view])
    return d,{'daily':'event_date_utc','retention':'day_n','funnel':'pair_count','categories':'purchase_events','availability':'total_events'}[view],'UTC历史汇总；漏斗为访客—商品对；首次观察不是注册'


def query(module,params=None):
    from .portfolio import records
    p=validate_params(module,params or {})
    view=p.get('view',{'survey':'attributes','retailrocket':'daily'}.get(module,'records'))
    d,default_sort,units=_table(module,view); d=d.copy()
    for key in FILTERS[module]-{'start_date','end_date'}:
        if key not in p:continue
        if key.startswith(('min_','max_')):
            col={'score':'douban' if module=='movies' else 'rating','price':'revenue_yi' if module=='movies' else 'price','area':'area'}[key.split('_',1)[1]]
            d=d[d[col].ge(p[key]) if key.startswith('min_') else d[col].le(p[key])]
        else:
            d=d[d[key].fillna('').astype(str).str.contains(p[key],regex=False,case=False)]
    if 'keyword' in p:
        mask=d.select_dtypes(include=['object','string']).fillna('').astype(str).apply(lambda col:col.str.contains(p['keyword'],regex=False,case=False)).any(axis=1)
        d=d[mask]
    for key,op in [('start_date','ge'),('end_date','le')]:
        if key in p:
            if 'event_date_utc' not in d:raise ValueError('date filters require daily view')
            d=d[getattr(d.event_date_utc,op)(p[key])]
    sort=p.get('sort_by',default_sort)
    if sort not in d:raise ValueError('sort not supported by selected view')
    # Stable pagination, nulls always last; no random truncation.
    d=d.sort_values(sort,ascending=p.get('order','desc')=='asc',kind='stable',na_position='last')
    total=len(d); rows=records(d.iloc[p['offset']:p['offset']+p['limit']])
    return {'module':module,'view':view,'filters':p,'total_matches':total,'offset':p['offset'],'limit':p['limit'],
            'has_more':p['offset']+len(rows)<total,'rows':rows,'units':units,
            'message':'没有符合条件的记录，请调整筛选条件。' if not total else '仅列出当前页；数量以total_matches为准。'}


def infer_params(module,text):
    """离线识别常见条件；当前问题放最后，较新的条件覆盖旧条件。"""
    p={}
    for district in re.findall(r'(?:朝阳|海淀|东城|西城|丰台|通州|昌平|大兴|顺义|石景山)区?',text):
        if module in ('food','rental'):p['district']=district if district.endswith('区') else district+'区'
    for word in ['北京','上海','深圳','广州','杭州','成都','武汉']:
        if module=='jobs' and word in text:p['city']=word
    for word in ['动画','科幻','喜剧','爱情','动作','战争','悬疑','犯罪']:
        if module=='movies' and word in text:p['genre']=word
    if module=='movies':
        quoted=re.findall(r'《([^》]+)》',text)
        if quoted:p['keyword']=quoted[-1]
    for word in ['火锅','烧烤','日本料理','粤菜','西餐']:
        if module=='food' and word in text:p['cuisine']=word
    for word in ['整租','合租']:
        if module=='rental' and word in text:p['rent_type']=word
    if module=='jobs':
        for word in ['数据分析','数据开发','算法','数据治理']:
            if word in text:p['family']=word
        for word in ['本科','硕士','博士','大专']:
            if word in text:p['education']=word
    prices=re.findall(r'(?:预算|不超过|低于|以内|以下)\s*(\d+(?:\.\d+)?)\s*(万)?',text)
    prices+=re.findall(r'(\d+(?:\.\d+)?)\s*(万)?\s*(?:元)?(?:以内|以下)',text)
    if prices and module in ('food','rental','housing','jobs'):
        n,wan=prices[-1];p['max_price']=float(n)*(10000 if wan else 1)
    count=re.findall(r'(?:前|列出|给我)\s*(\d+)\s*(?:个|部|家|条|套)?',text)
    if count:p['limit']=min(20,max(1,int(count[-1])))
    if '前十' in text:p['limit']=10
    if any(w in text for w in ['便宜','最低','从低到高']):p.update(sort_by='price',order='asc')
    if module=='movies':
        if '评分' in text:p['sort_by']='douban'
        if '票房' in text:p['sort_by']='revenue_yi'
    if module=='survey':
        p['view']='visits' if any(w in text for w in ['频率','到访']) else 'ages' if '年龄' in text else 'segments' if any(w in text for w in ['分组','人群','客群']) else 'attributes'
    if module=='retailrocket':
        p['view']='retention' if any(w in text for w in ['留存','回访','d7','D7']) else 'funnel' if '漏斗' in text else 'categories' if '类别' in text else 'availability' if '可售' in text else 'daily'
        if p['view']=='daily':
            dates=re.findall(r'\d{4}-\d{2}-\d{2}',text)
            if dates:p.update(start_date=dates[0],end_date=dates[-1])
        if p['view']=='daily' and any(w in text for w in ['购买率','购买占比']):p['sort_by']='daily_buyer_rate_pct'
    if any(w in text for w in ['下一页','再来一页']):p['offset']=p.get('limit',8)
    return p


def wants_query(text):
    return any(w in text for w in ['有哪些','有什么','有些什么','列出','名单','明细','找','推荐','吃什么','吃哪','吃顿','预算','以内','以下','下一页','再来','前十','前10','排名','最高','最低','便宜','只看','筛选','按评分','按票房','《'])


def answer(module,params):
    result=query(module,params)
    labels={'name':'名称','price':'价格','area':'面积','revenue_yi':'票房亿元','douban':'豆瓣','maoyan':'猫眼','count':'样本数','yes_pct':'认同率%','mean_like':'平均好感','event_date_utc':'日期','day_n':'第N日','retention_rate_pct':'回访率%','pair_count':'访客—商品对','total_events':'事件数','purchase_events':'购买事件','id':'编号','district':'区域','city':'城市','community':'小区','family':'岗位族','salary':'原始薪资','rent_type':'租型','cuisine':'菜系','rating':'评分','reviews':'评论数','neighborhood':'社区'}
    labels.update(active_visitors='活跃访客',buying_visitors='购买访客',daily_buyer_rate_pct='购买访客占比%',eligible_visitors='可观察访客',returned_visitors='回访访客',category_id='类别编号',stage_name='阶段',status='可售状态')
    lines=[f"符合条件共{result['total_matches']}条，本页从第{result['offset']+1}条起列出{len(result['rows'])}条。" if result['rows'] else result['message'],result['units']]
    for row in result['rows']:
        parts=[]
        for key,v in row.items():
            if key not in labels or v is None:continue
            if isinstance(v,float):v=f'{v:,.2f}'
            parts.append(f'{labels[key]}：{v}')
        lines.append('；'.join(parts))
    if result['has_more']:lines.append('还有更多结果，可以继续问“下一页”。')
    return lines,[module+'.query']
