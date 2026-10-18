"""用户留存分析 — 队列（Cohort）口径。

旧版的做法是两个错误叠在一起：
  1. 只有一条「第 N 周留存 = 第 N 周回访人数 / 全年注册总数」的曲线，
     分母用全年总量，第 5 周的比率被稀释到个位数，不是留存率；
  2. 没有队列概念，不同注册时间的用户在同一个坐标上比较。

新版模拟到「用户 × 周」粒度：
  - 每个用户有注册日、渠道、设备；
  - 按注册周分队列，同一队列跟踪 8 周，得到真正的留存矩阵；
  - 渠道/设备差异、队列趋势、流失风险都能从矩阵里读出来。

数据是模拟的（没有真实 App 埋点），但生成机制显式、可复现。
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from .data import jsonable

START = pd.Timestamp("2024-01-01")
END = pd.Timestamp("2024-12-31")
WEEKS = 8

# 基准周留存（第 0 周 = 注册周）
BASE_CURVE = np.array([1.00, 0.420, 0.290, 0.230, 0.195, 0.175, 0.160, 0.150, 0.142])

CHANNELS = [
    ("自然流量", 0.45, 1.00),
    ("推荐", 0.20, 1.22),
    ("广告投放", 0.35, 0.85),
]
DEVICES = [("iOS", 0.45, 1.06), ("Android", 0.55, 0.95)]


def _simulate():
    rng = np.random.default_rng(42)
    days = pd.date_range(START, END, freq="D")
    weekday_mult = np.where(days.weekday >= 5, 1.25, 1.0)
    progress = np.linspace(1.0, 1.35, len(days))          # 全年缓慢增长
    daily = rng.poisson(45, len(days)) * weekday_mult * progress
    daily = np.maximum(1, daily * rng.uniform(0.85, 1.15, len(days))).astype(int)

    frames = []
    uid = 0
    for d, n in zip(days, daily):
        if n == 0:
            continue
        ch = rng.choice([c[0] for c in CHANNELS], size=n, p=[c[1] for c in CHANNELS])
        dv = rng.choice([c[0] for c in DEVICES], size=n, p=[c[1] for c in DEVICES])
        frames.append(pd.DataFrame({
            "user_id": np.arange(uid, uid + n),
            "signup_date": d,
            "channel": ch,
            "device": dv,
        }))
        uid += n
    users = pd.concat(frames, ignore_index=True)

    # 队列趋势：越晚注册的队列，留存略好（产品迭代的累积效果）
    cohort_week = users["signup_date"].dt.isocalendar().week.astype(int)
    min_week = cohort_week.min()
    trend = np.clip(
        1.0 + 0.008 * (cohort_week - min_week), 1.0, 1.30
    ).values

    ch_mult = users["channel"].map({c[0]: c[2] for c in CHANNELS}).values
    dv_mult = users["device"].map({d[0]: d[2] for d in DEVICES}).values
    # 个体异质性：有人天然更黏，有人注册即走
    hetero = np.clip(rng.lognormal(0.0, 0.25, len(users)), 0.5, 2.0)

    # 每个用户每周的留存概率
    probs = BASE_CURVE[None, 1:] * (ch_mult * dv_mult * trend * hetero)[:, None]
    probs = np.clip(probs, 0.0, 0.98)

    # 用「条件留存」模拟逐个用户流失：一旦流失不再回来
    active = np.ones((len(users), WEEKS + 1), dtype=bool)
    prev = np.ones(len(users))
    for k in range(WEEKS):
        cond = np.where(prev > 0, probs[:, k] / prev, 0.0)
        survives = rng.random(len(users)) < cond
        active[:, k + 1] = active[:, k] & survives
        prev = probs[:, k]
    return users, active


@lru_cache(maxsize=1)
def get_retention_analysis() -> dict:
    users, active = _simulate()

    iso = users["signup_date"].dt.isocalendar()
    users["cohort"] = (
        iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    )
    users["cohort_start"] = users["signup_date"] - pd.to_timedelta(
        users["signup_date"].dt.weekday, unit="D"
    )

    def curve(mask):
        sub = active[mask.values]
        return (sub.mean(axis=0) * 100).round(1).tolist()

    all_curve = curve(pd.Series(True, index=users.index))

    # ── 队列矩阵 ───────────────────────────────────────
    cohorts = []
    for name, idx in users.groupby("cohort").groups.items():
        sub = active[users.index.isin(idx)]
        cohorts.append({
            "cohort": name,
            "start": users.loc[idx[0], "cohort_start"].strftime("%Y-%m-%d"),
            "size": int(len(idx)),
            "values": (sub.mean(axis=0) * 100).round(1).tolist(),
        })
    cohorts.sort(key=lambda x: x["start"])

    # ── 渠道 / 设备 ────────────────────────────────────
    channels = []
    for name, _, _ in CHANNELS:
        mask = users["channel"] == name
        channels.append({
            "name": name,
            "users": int(mask.sum()),
            "share_pct": round(mask.mean() * 100, 1),
            "values": curve(mask),
        })

    devices = []
    for name, _, _ in DEVICES:
        mask = users["device"] == name
        devices.append({
            "name": name,
            "users": int(mask.sum()),
            "share_pct": round(mask.mean() * 100, 1),
            "values": curve(mask),
        })

    # ── 流失风险 ───────────────────────────────────────
    avg = np.array(all_curve) / 100
    hazard = []
    for k in range(1, WEEKS + 1):
        at_risk = avg[k - 1]
        hazard.append({
            "week": k,
            "churn_pct": round((1 - avg[k] / at_risk) * 100, 1) if at_risk > 0 else None,
        })

    # ── 队列趋势：W4 留存随注册时间变化 ─────────────────
    cohort_trend = [
        {"cohort": c["cohort"], "start": c["start"], "w4": c["values"][4]}
        for c in cohorts
    ]
    # 首尾各取 8 个「完整队列」做对比：末尾不完整的注册周只有一两天，
    # 样本量小、波动大，直接拿单周比会得出错误结论。
    median_size = float(np.median([c["size"] for c in cohorts]))
    full = [c for c in cohorts if c["size"] >= 0.6 * median_size]
    early_avg = round(float(np.mean([c["values"][4] for c in full[:8]])), 1)
    late_avg = round(float(np.mean([c["values"][4] for c in full[-8:]])), 1)

    overview = {
        "users": int(len(users)),
        "days": int((END - START).days + 1),
        "avg_daily_signups": round(len(users) / ((END - START).days + 1), 1),
        "cohorts": int(len(cohorts)),
        "w1_retention": all_curve[1],
        "w4_retention": all_curve[4],
        "w8_retention": all_curve[8],
        "first_week_churn": round(100 - all_curve[1], 1),
        "cohort_w4_early": early_avg,
        "cohort_w4_late": late_avg,
        "observed_until": (END + pd.Timedelta(weeks=WEEKS)).strftime("%Y-%m-%d"),
    }

    # ── 结论 ───────────────────────────────────────────
    ch_map = {c["name"]: c for c in channels}
    organic, referral, ads = ch_map["自然流量"], ch_map["推荐"], ch_map["广告投放"]
    dv_map = {d["name"]: d for d in devices}
    insights = [
        f"共 {len(users):,} 名注册用户、{len(cohorts)} 个注册周队列，"
        f"观测窗口 {START:%Y-%m-%d} 至 {overview['observed_until']}。",
        f"首周流失 {overview['first_week_churn']}%，第 4 周留存 {overview['w4_retention']}%，"
        f"第 8 周 {overview['w8_retention']}%——留存曲线「先陡后平」，"
        "首周是最大流失口，激活动作必须放在注册后 7 天内。",
        f"渠道差异明显：推荐渠道 W4 留存 {referral['values'][4]}%，"
        f"自然流量 {organic['values'][4]}%，广告投放只有 {ads['values'][4]}%——"
        f"广告投放占注册量的 {ads['share_pct']}%，规模接近自然流量，但留存质量最低；"
        "拉新成本要按留存后的 LTV 回收，而不是按注册数考核。",
        f"设备差异较小但稳定：iOS W4 留存 {dv_map['iOS']['values'][4]}%，"
        f"Android {dv_map['Android']['values'][4]}%。",
        f"队列在缓慢变好：年初 8 个队列平均 W4 留存 {early_avg}%，"
        f"年末 8 个队列 {late_avg}%，提升 {round(late_avg - early_avg, 1)} 个百分点——"
        "单周队列波动可达 ±3pp，所以看趋势要用多周平均，不能拿首尾两周直接比较。",
    ]

    return jsonable({
        "overview": overview,
        "data_notes": [
            "数据为模拟 App 注册与活跃埋点：每日注册量含周末效应和全年增长趋势。",
            "留存定义为「注册后第 N 周仍有活跃」，一旦流失不回流；第 0 周恒为 100%。",
            "渠道留存倍率：推荐 1.22、自然 1.00、广告 0.85；设备：iOS 1.06、Android 0.95。",
            "队列趋势按注册周线性加成（每周 +0.8%，上限 1.30），模拟产品迭代带来的缓慢改善。",
        ],
        "average_curve": all_curve,
        "cohorts": cohorts,
        "channels": channels,
        "devices": devices,
        "hazard": hazard,
        "cohort_trend": cohort_trend,
        "insights": insights,
    })
