"""公开数据项目：同一分析结果供页面、JSON API 和 AI 工具使用。"""
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from .data import jsonable

DATA = Path(__file__).resolve().parent.parent / 'data'
COMMUNITY_SOURCE = '作者从和鲸社区、天池等公开数据社区下载整理；具体下载链接未保留，未逐行独立核实。历史样本用于分析学习与能力展示。'


def clean(obj):
    """标准 JSON，缺失值一律为 null。"""
    if isinstance(obj, dict):
        return {str(k): clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v) for v in obj]
    if isinstance(obj, (float, np.floating)) and not np.isfinite(obj):
        return None
    return jsonable(obj)


def records(frame):
    return clean(frame.to_dict('records'))


@lru_cache(maxsize=1)
def get_movies_analysis():
    raw = pd.read_excel(DATA / 'movies.xlsx')
    d = raw.rename(columns={'电影名称': 'name', '导演': 'director', '作品类型': 'genre',
                            '累计票房': 'revenue', '豆瓣评分': 'douban', '猫眼评分': 'maoyan',
                            '正式上映日期': 'release', '数据截止日期': 'snapshot'})
    d['revenue_yi'] = pd.to_numeric(d['revenue'], errors='coerce') / 1e8
    for col in ['douban', 'maoyan']:
        d[col] = pd.to_numeric(d[col], errors='coerce').where(lambda s: s.between(0, 10))
    d['year'] = pd.to_datetime(d['release'], errors='coerce').dt.year
    tags = d.assign(tag=d['genre'].str.split(',')).explode('tag')
    tags['tag'] = tags['tag'].str.strip()
    genres = tags.groupby('tag').agg(count=('name', 'size'), median_revenue_yi=('revenue_yi', 'median'),
                                   mean_douban=('douban', 'mean')).reset_index().sort_values('count', ascending=False)
    rows = d[['name', 'director', 'genre', 'revenue_yi', 'douban', 'maoyan', 'release', 'snapshot']].sort_values('revenue_yi', ascending=False)
    correlations = []
    for score in ['douban', 'maoyan']:
        valid = d[[score, 'revenue_yi']].dropna().query('revenue_yi > 0')
        correlations.append({'name': score, 'count': len(valid), 'pearson_log_revenue': valid[score].corr(np.log1p(valid['revenue_yi']))})
    overview = {'records': len(raw), 'median_revenue_yi': d['revenue_yi'].median(),
                'mean_douban': d['douban'].mean(), 'mean_maoyan': d['maoyan'].mean(),
                'duplicate_names': int(d['name'].duplicated().sum()),
                'snapshot_start': str(d['snapshot'].min()), 'snapshot_end': str(d['snapshot'].max())}
    return clean({'overview': overview, 'movies': records(rows), 'genres': records(genres),
                  'correlations': correlations,
                  'yearly': records(d.groupby('year').agg(count=('name', 'size'), median_revenue_yi=('revenue_yi', 'median')).reset_index()),
                  'source': COMMUNITY_SOURCE,
                  'insights': [f"样本包含 {len(d)} 部电影，累计票房中位数为 {d['revenue_yi'].median():.2f} 亿元。",
                               f"同一份样本的豆瓣均分 {d['douban'].mean():.2f}、猫眼均分 {d['maoyan'].mean():.2f}；平台用户和评分机制不同。",
                               '先按类型筛选，再结合样本量看票房分布；多类型电影会同时计入多个标签。'],
                  'data_notes': [COMMUNITY_SOURCE, '各影片截止日期不同，累计票房不是同一时点的全市场统计；评分也不是实时评分。',
                                 '120部电影的选样规则未保留，不能用于估计国产电影整体平均票房或年度市场规模。',
                                 '类型使用完整计数，一部多类型电影可出现在多组；相关性使用 log(1+票房亿元)，不代表评分导致票房变化。']})


@lru_cache(maxsize=1)
def get_survey_analysis():
    d = pd.read_csv(DATA / 'mcdonalds.csv')
    d['like_score'] = pd.to_numeric(d['Like'].astype(str).str.extract(r'([+-]?\d+)$')[0], errors='coerce')
    d['segment'] = np.select([d['like_score'] > 0, d['like_score'] < 0], ['正向好感', '负向好感'], default='中立')
    attrs = {'yummy': '美味', 'convenient': '便利', 'spicy': '辛辣', 'fattening': '易发胖',
             'greasy': '油腻', 'fast': '快捷', 'cheap': '便宜', 'tasty': '可口',
             'expensive': '昂贵', 'healthy': '健康', 'disgusting': '令人反感'}
    attribute_rows = []
    for key, label in attrs.items():
        valid = d[key].isin(['Yes', 'No'])
        yes = int((d.loc[valid, key] == 'Yes').sum())
        attribute_rows.append({'name': label, 'valid': int(valid.sum()), 'yes': yes, 'yes_pct': 100 * yes / valid.sum()})
    profiles = []
    for group, frame in d.groupby('segment'):
        profiles.append({'name': group, 'count': len(frame), 'mean_like': frame['like_score'].mean(),
                         **{key: 100 * (frame[key] == 'Yes').sum() / frame[key].isin(['Yes', 'No']).sum() for key in attrs}})
    visit_order = ['Never', 'Once a year', 'Every three months', 'Once a month', 'Once a week', 'More than once a week']
    labels = ['从不', '每年一次', '每三个月一次', '每月一次', '每周一次', '每周多次']
    visit = d.groupby('VisitFrequency').agg(count=('Like', 'size'), mean_like=('like_score', 'mean')).reindex(visit_order).reset_index()
    visit['name'] = labels
    d['age_band'] = pd.cut(d['Age'], [0, 29, 44, 59, np.inf], labels=['≤29岁', '30–44岁', '45–59岁', '≥60岁'])
    ages = d.groupby('age_band', observed=True).agg(count=('Like', 'size'), mean_like=('like_score', 'mean')).reset_index().rename(columns={'age_band': 'name'})
    segments = d['segment'].value_counts()
    return clean({'overview': {'records': len(d), 'mean_like': d['like_score'].mean(),
                               'positive_pct': 100 * (d['like_score'] > 0).mean(), 'median_age': d['Age'].median(),
                               'missing_like': int(d['like_score'].isna().sum())},
                  'attributes': attribute_rows, 'profiles': profiles, 'visits': records(visit), 'ages': records(ages),
                  'segments': [{'name': name, 'count': int(n)} for name, n in segments.items()],
                  'source': COMMUNITY_SOURCE,
                  'insights': [f"{len(d):,}份问卷中，正向好感占 {100 * (d['like_score'] > 0).mean():.1f}%，平均好感 {d['like_score'].mean():.2f}（−5至+5）。",
                               '品牌属性题统计回答 Yes 的比例；好感分组是描述性分组，不是自动聚类得到的客群。',
                               '到访频率与好感度可作关联对照，不能据此推断提高到访频率会提升好感。'],
                  'data_notes': [COMMUNITY_SOURCE, '这是一份消费者调查样本，不是麦当劳交易、营收或中国消费者总体数据。',
                                 '保留原始英文问卷字段，界面提供中文解释；调查时间与抽样细节未在本地文件中保留。',
                                 '正向=好感分>0，负向<0，中立=0；属性比例以有效Yes/No回答为分母，不作因果推断。']})


@lru_cache(maxsize=1)
def get_housing_analysis():
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.impute import SimpleImputer
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, mean_squared_log_error
    d = pd.read_csv(DATA / 'housing' / 'train.csv')
    unlabeled = pd.read_csv(DATA / 'housing' / 'test.csv')
    nums = ['GrLivArea', 'OverallQual', 'YearBuilt', 'TotalBsmtSF', 'GarageCars', 'FullBath']
    cats = ['Neighborhood', 'HouseStyle', 'BldgType']
    x_train, x_valid, y_train, y_valid = train_test_split(d[nums + cats], d['SalePrice'], test_size=.2, random_state=42)
    prep = ColumnTransformer([('num', SimpleImputer(strategy='median'), nums),
                              ('cat', make_pipeline(SimpleImputer(strategy='most_frequent'), OneHotEncoder(handle_unknown='ignore')), cats)])
    model = make_pipeline(prep, RandomForestRegressor(n_estimators=120, min_samples_leaf=3, random_state=42, n_jobs=1))
    model.fit(x_train, np.log1p(y_train))
    predicted = np.maximum(0, np.expm1(model.predict(x_valid)))
    baseline = np.full(len(y_valid), y_train.median())
    metrics = {'train_count': len(x_train), 'validation_count': len(x_valid),
               'mae_usd': mean_absolute_error(y_valid, predicted), 'baseline_mae_usd': mean_absolute_error(y_valid, baseline),
               'rmsle': np.sqrt(mean_squared_log_error(y_valid, predicted)),
               'baseline_rmsle': np.sqrt(mean_squared_log_error(y_valid, baseline)),
               'method': '固定80/20随机留出（seed=42）；训练集内插补及编码；9项房屋特征；随机森林拟合log1p售价。'}
    neighborhoods = d.groupby('Neighborhood').agg(count=('Id', 'size'), median_price=('SalePrice', 'median')).reset_index().rename(columns={'Neighborhood': 'name'}).sort_values('median_price', ascending=False)
    quality = d.groupby('OverallQual').agg(count=('Id', 'size'), median_price=('SalePrice', 'median')).reset_index().rename(columns={'OverallQual': 'name'})
    scatter = d[['Id', 'Neighborhood', 'GrLivArea', 'SalePrice', 'OverallQual', 'YrSold']].rename(columns={'Id': 'id', 'Neighborhood': 'neighborhood', 'GrLivArea': 'area_sqft', 'SalePrice': 'price', 'OverallQual': 'quality', 'YrSold': 'year'})
    validation = pd.DataFrame({'actual': y_valid.to_numpy(), 'predicted': predicted, 'id': y_valid.index.to_numpy()}).sort_values('actual')
    validation['id'] = d.loc[validation['id'], 'Id'].to_numpy()
    source = 'Kaggle House Prices: Advanced Regression Techniques；美国爱荷华州Ames历史房屋成交数据。'
    return clean({'overview': {'records': len(d), 'unlabeled_records': len(unlabeled), 'median_price_usd': d['SalePrice'].median(),
                               'neighborhoods': d['Neighborhood'].nunique(), 'year_start': int(d['YrSold'].min()), 'year_end': int(d['YrSold'].max())},
                  'neighborhoods': records(neighborhoods), 'quality': records(quality), 'scatter': records(scatter),
                  'metrics': metrics, 'validation': records(validation), 'source': source,
                  'source_url': 'https://www.kaggle.com/competitions/house-prices-advanced-regression-techniques/data',
                  'insights': [f"{len(d):,}条已知成交价格样本，售价中位数 ${d['SalePrice'].median():,.0f}；这是售价，不是月租金。",
                               f"固定留出验证集 {len(y_valid)} 套房屋，模型MAE为 ${metrics['mae_usd']:,.0f}，训练集售价中位数基线MAE为 ${metrics['baseline_mae_usd']:,.0f}。",
                               '北京租房以人民币/月计，美国房屋以美元/套计；分别展示，不能直接计算国内外价格高低。'],
                  'data_notes': [source, '训练集1,460条有售价；Kaggle测试集1,459条未公开售价，只报告其规模，不参与描述性售价统计或模型评分。',
                                 '展示模型为平台独立重算的固定留出基线，不冒用原项目排行榜分数；不是跨时间验证，也不代表未来定价能力。',
                                 '面积为地上居住面积（平方英尺）；房屋总体质量为1–10档。社区分组差异混有房屋特征与成交年份差异。']})
