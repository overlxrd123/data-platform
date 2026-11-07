"""Retailrocket：只消费经过核对的 MySQL 汇总快照，不读取原始日志或凭据。"""
from functools import lru_cache
from pathlib import Path
import json

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / 'data' / 'retailrocket'


def records(frame):
    # pandas JSON encoder converts NaN to null; API must never emit NaN/Infinity.
    return json.loads(frame.to_json(orient='records', date_format='iso', force_ascii=False))


@lru_cache(maxsize=1)
def get_retailrocket_analysis():
    manifest = json.loads((DATA_DIR / 'manifest.json').read_text(encoding='utf-8'))
    def load(name):
        return pd.read_csv(DATA_DIR / (name + '_mysql.csv'))
    daily = load('daily_metrics').sort_values('event_date_utc')
    if len(daily) != 139 or int(daily.total_events.sum()) != 2756101:
        raise ValueError('Retailrocket快照校验失败，请重新导出汇总数据')
    complete = daily[daily.is_boundary_date.eq(0)].copy()
    complete['active_7d'] = complete.active_visitors.rolling(7).mean()
    complete['buyers_7d'] = complete.buying_visitors.rolling(7).mean()
    complete['buyer_rate_7d'] = 100 * complete.buying_visitors.rolling(7).sum() / complete.active_visitors.rolling(7).sum()
    funnel = load('funnel_metrics').sort_values('stage_order')
    windows = load('funnel_windows').sort_values('window_hours')
    if windows.viewing_pairs.nunique() != 1:
        raise ValueError('漏斗窗口比较样本不一致')
    windows['view_to_purchase_pct'] = 100 * windows.purchase_pairs / windows.viewing_pairs
    retention = load('retention_metrics').sort_values('day_n')
    cohorts = load('weekly_retention')
    cohorts = cohorts[(cohorts.week_index >= 1) & (cohorts.cohort_week >= '2015-05-04')]
    mature = cohorts.groupby('cohort_week').retention_rate_pct.count()
    cohorts = cohorts[cohorts.cohort_week.isin(mature[mature > 0].index)]
    categories = load('category_metrics')
    available = load('availability_metrics')
    for frame in (categories, available):
        if int(frame.total_events.sum()) != 2756101 or int(frame.purchase_events.sum()) != 22457:
            raise ValueError('商品汇总快照未通过事件数核对')
    available['status'] = available.available.map(lambda x: '未知' if pd.isna(x) else ('可售' if int(x) == 1 else '不可售'))
    coverage = categories.groupby('category_match_status', as_index=False).total_events.sum()
    top = categories[categories.category_match_status.eq('matched')].nlargest(12, 'purchase_events')
    inc = int(windows.iloc[-1].purchase_pairs - windows.iloc[0].purchase_pairs)
    notes = [
        '来源为真实匿名电商数据，页面使用已核验的MySQL汇总快照，不是实时数据库连接。',
        '日期按UTC；每日趋势排除首尾不完整日。首次观察访客不等于新注册用户。',
        '漏斗单位为访客—商品对，要求同商品浏览<加购<购买；仅从样本内首次浏览启动窗口。',
        '主漏斗需要24小时观察期；窗口对比统一需要7天，左右样本不可直接相减。',
        'D7是精确第7日回访；周回访第1周是首次观察后第7—13天。灰色格子是观察不足，不是0。',
        '属性按行为发生前最后记录匹配；未知不等于不可售。不可售购买可能涉及属性更新滞后，不能推断缺货损失。',
        '原始事件未自动去重；事件量保留重复记录。跨日、小时、类别的去重访客不能直接相加。',
        '该数据没有渠道、营收和实验分组；页面不提供收入估算或真实A/B效果结论。',
    ]
    insights = [
        'UTC周末访问与购买占比较低；7月11—12日及25—26日高访问、低购买占比并存，原因尚待验证。',
        f'共同观察样本中，24小时到7天增加{inc:,}对有序购买，约{100 * inc / windows.iloc[0].purchase_pairs:.1f}%；延迟购买只解释部分差异。',
        '精确日回访率D1约2.766%、D7约0.565%、D30约0.159%；不能把未回访等同于永久流失。',
        '23.84%的事件没有历史类别；约6.3%的购买事件匹配到最后已知不可售状态，应先核查属性时点再解释业务。',
    ]
    return {
        'overview': {'events': int(daily.total_events.sum()), 'visitors': manifest['verified_overview']['visitors'],
                     'purchase_events': int(categories.purchase_events.sum()), 'days': len(daily), 'complete_days': len(complete),
                     'first_date': str(daily.event_date_utc.min()), 'last_date': str(daily.event_date_utc.max())},
        'provenance': manifest, 'daily': records(complete), 'weekday': records(load('weekday_metrics')),
        'july': records(load('july_weekend_comparison')), 'hourly': records(load('july_hourly')),
        'funnel': records(funnel), 'windows': records(windows), 'retention': records(retention),
        'cohorts': records(cohorts), 'categories': records(top), 'coverage': records(coverage),
        'availability': records(available), 'insights': insights, 'data_notes': notes,
    }
