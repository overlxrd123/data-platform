"""北京租房市场 — 分租型（整租/合租）口径。

这份数据最容易犯的错误是「直接比较不同房型的租金」：
整租中位租金 5,236 元、合租 1,400 元，看起来差 3.7 倍，
但整租中位面积 88.8㎡、合租 17.5㎡，两者面积区间几乎不重叠
（合租 10–25㎡，整租 45–160㎡），直接比价没有意义。

更重要的一点：在这份数据里，同一房型内部「租金 × 面积」几乎不相关
（合租 r≈0.008，整租 r≈-0.011），租金近似按房型固定。
所以单价（元/㎡）随面积下降是「总价 ÷ 面积」的机械结果，
不能解读为小户型/核心地段溢价。分析必须先分房型，再谈区域。
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from .data import jsonable, load_rental

AREA_BINS = [9, 15, 20, 25, 45, 60, 75, 90, 110, 130, 160]
AREA_LABELS = ["10-15㎡", "15-20㎡", "20-25㎡", "25-45㎡", "45-60㎡",
               "60-75㎡", "75-90㎡", "90-110㎡", "110-130㎡", "130-160㎡"]
DISTRICT_ORDER = ["西城区", "东城区", "海淀区", "朝阳区", "丰台区",
                  "石景山区", "通州区", "昌平区", "大兴区", "顺义区"]


@lru_cache(maxsize=1)
def get_rental_analysis() -> dict:
    df = load_rental().copy()

    # ── 概况 ───────────────────────────────────────────
    overview = {
        "listings": int(len(df)),
        "districts": int(df["district"].nunique()),
        "rent_median": int(df["rent_price"].median()),
        "rent_p25": int(df["rent_price"].quantile(.25)),
        "rent_p75": int(df["rent_price"].quantile(.75)),
        "unit_median": round(float(df["unit_price"].median()), 1),
        "area_median": round(float(df["area"].median()), 1),
        "whole_share_pct": round(float((df["rent_type"] == "整租").mean()) * 100, 1),
        "subway_share_pct": round(float(df["has_subway"].mean()) * 100, 1),
        "date_start": str(df["publish_date"].min()),
        "date_end": str(df["publish_date"].max()),
    }

    # ── 房型：整租 vs 合租 ──────────────────────────────
    rent_types = []
    for name in ["整租", "合租"]:
        sub = df[df["rent_type"] == name]
        rent_types.append({
            "name": name,
            "count": int(len(sub)),
            "share_pct": round(len(sub) / len(df) * 100, 1),
            "rent_median": int(sub["rent_price"].median()),
            "area_median": round(float(sub["area"].median()), 1),
            "unit_median": round(float(sub["unit_price"].median()), 1),
            "area_min": round(float(sub["area"].min()), 1),
            "area_max": round(float(sub["area"].max()), 1),
            "area_p25": round(float(sub["area"].quantile(.25)), 1),
            "area_p75": round(float(sub["area"].quantile(.75)), 1),
        })

    # ── 区域：全样本与分房型 ────────────────────────────
    districts = []
    for name, sub in df.groupby("district"):
        districts.append({
            "district": name,
            "count": int(len(sub)),
            "rent_median": int(sub["rent_price"].median()),
            "unit_median": round(float(sub["unit_price"].median()), 1),
            "area_median": round(float(sub["area"].median()), 1),
            "whole_pct": round(float((sub["rent_type"] == "整租").mean()) * 100, 1),
            "subway_pct": round(float(sub["has_subway"].mean()) * 100, 1),
        })
    districts.sort(key=lambda x: -x["unit_median"])

    district_by_type = {}
    for rtype in ["整租", "合租"]:
        rows = []
        sub = df[df["rent_type"] == rtype]
        for name, g in sub.groupby("district"):
            rows.append({
                "district": name,
                "count": int(len(g)),
                "rent_median": int(g["rent_price"].median()),
                "unit_median": round(float(g["unit_price"].median()), 1),
                "area_median": round(float(g["area"].median()), 1),
            })
        rows.sort(key=lambda x: -x["unit_median"])
        base = rows[-1]["unit_median"]
        for r in rows:
            r["premium_vs_lowest_pct"] = round((r["unit_median"] / base - 1) * 100, 1)
        district_by_type[rtype] = rows

    # ── 面积分档：单价随面积下降是除法效应 ──────────────
    df["area_band"] = pd.cut(df["area"], AREA_BINS, labels=AREA_LABELS)
    area_bands = []
    small_gap = None
    for label, sub in df.groupby("area_band", observed=True):
        if len(sub) < 50:      # 25–45㎡ 只有个位数房源，是房型断层，不参与对比
            small_gap = {"band": str(label), "count": int(len(sub))}
            continue
        area_bands.append({
            "band": str(label),
            "count": int(len(sub)),
            "rent_median": int(sub["rent_price"].median()),
            "unit_median": round(float(sub["unit_price"].median()), 1),
            "area_median": round(float(sub["area"].median()), 1),
        })

    # 房型内部租金与面积的相关性（说明租金并不随面积增长）
    rent_area_corr = {
        rtype: round(float(df.loc[df["rent_type"] == rtype, "rent_price"].corr(
            df.loc[df["rent_type"] == rtype, "area"]
        )), 3)
        for rtype in ["整租", "合租"]
    }

    # ── 地铁与配套：单变量对比 ──────────────────────────
    def compare_amenity(col, label):
        base = df[df[col] == 0]
        has = df[df[col] == 1]
        base_unit = float(base["unit_price"].median())
        has_unit = float(has["unit_price"].median())
        return {
            "name": col,
            "label": label,
            "yes_count": int(len(has)),
            "no_count": int(len(base)),
            "yes_share_pct": round(len(has) / len(df) * 100, 1),
            "yes_unit_median": round(has_unit, 1),
            "no_unit_median": round(base_unit, 1),
            "diff_pct": round((has_unit / base_unit - 1) * 100, 1),
        }

    amenities = [
        compare_amenity("has_subway", "近地铁"),
        compare_amenity("has_school", "近学校"),
        compare_amenity("has_hospital", "近医院"),
        compare_amenity("has_mall", "近商场"),
    ]

    # 地铁距离分档
    df["subway_band"] = pd.cut(
        df["subway_distance"], [0, .5, 1.0, 1.5, 3.0, 5.0],
        labels=["<0.5km", "0.5-1km", "1-1.5km", "1.5-3km", "3-5km"],
    )
    subway_distance = [
        {
            "band": str(label),
            "count": int(len(sub)),
            "unit_median": round(float(sub["unit_price"].median()), 1),
            "rent_median": int(sub["rent_price"].median()),
        }
        for label, sub in df.groupby("subway_band", observed=True)
    ]

    # ── 装修 / 楼层 / 朝向 ──────────────────────────────
    def compare_category(col, order):
        rows = []
        for name in order:
            sub = df[df[col] == name]
            if not len(sub):
                continue
            rows.append({
                "group": name,
                "count": int(len(sub)),
                "rent_median": int(sub["rent_price"].median()),
                "unit_median": round(float(sub["unit_price"].median()), 1),
            })
        return rows

    attributes = {
        "decoration": compare_category("decoration", ["毛坯", "简装", "精装"]),
        "floor": compare_category("floor", ["低楼层", "中楼层", "高楼层"]),
        "orientation": compare_category(
            "orientation",
            ["北", "南", "东", "西", "东南", "西南", "南北", "东西"],
        ),
    }

    # ── 月度趋势 ───────────────────────────────────────
    df["month"] = df["publish_date"].str[:7]
    trend = [
        {
            "month": month,
            "count": int(len(sub)),
            "rent_median": int(sub["rent_price"].median()),
            "unit_median": round(float(sub["unit_price"].median()), 1),
        }
        for month, sub in df.groupby("month")
    ]
    m2024 = np.mean([r["unit_median"] for r in trend if r["month"].startswith("2024")])
    m2025 = np.mean([r["unit_median"] for r in trend if r["month"].startswith("2025")])

    # ── 地图 / 散点抽样 ─────────────────────────────────
    sample = df.sample(n=min(800, len(df)), random_state=42)
    scatter = [
        {
            "lat": round(float(r.lat), 4),
            "lng": round(float(r.lng), 4),
            "rent": int(r.rent_price),
            "area": round(float(r.area), 1),
            "unit": round(float(r.unit_price), 1),
            "district": r.district,
            "rent_type": r.rent_type,
        }
        for r in sample.itertuples()
    ]

    # ── 结论 ───────────────────────────────────────────
    whole = next(x for x in rent_types if x["name"] == "整租")
    shared = next(x for x in rent_types if x["name"] == "合租")
    d_whole = district_by_type["整租"]
    d_shared = district_by_type["合租"]
    low_area, high_area = area_bands[0], area_bands[-1]
    max_amen = max(amenities, key=lambda x: abs(x["diff_pct"]))
    trend_pct = round((m2025 / m2024 - 1) * 100, 1)
    attr_names = {"decoration": "装修", "floor": "楼层", "orientation": "朝向"}
    attr_spread = {
        attr_names[k]: round(
            (max(r["unit_median"] for r in rows)
             / min(r["unit_median"] for r in rows) - 1) * 100, 1
        )
        for k, rows in attributes.items()
    }

    insights = [
        f"共 {len(df):,} 条房源、{df['district'].nunique()} 个区，"
        f"发布时间 {overview['date_start']} 至 {overview['date_end']}。"
        "10 个区各约 3,500 条、整租/合租接近 1:1，分布过于均匀，"
        "只描述当前下载样本的结构，不据此推断全北京市场。",
        f"整租中位租金 {whole['rent_median']:,} 元、合租 {shared['rent_median']:,} 元，"
        f"但面积中位数分别是 {whole['area_median']}㎡ 和 {shared['area_median']}㎡，"
        "两者面积区间几乎不重叠——直接比租金会把「房型差异」误读成「价格差异」。",
        f"区域价格分层清晰：整租单价最高 {d_whole[0]['district']} "
        f"{d_whole[0]['unit_median']} 元/㎡，最低 {d_whole[-1]['district']} "
        f"{d_whole[-1]['unit_median']} 元/㎡，高出 {d_whole[0]['premium_vs_lowest_pct']}%"
        f"（约 {d_whole[0]['unit_median'] / d_whole[-1]['unit_median']:.1f} 倍）；"
        f"合租同样是从 {d_shared[0]['district']} 到 {d_shared[-1]['district']}，"
        f"高出 {d_shared[0]['premium_vs_lowest_pct']}%"
        f"（约 {d_shared[0]['unit_median'] / d_shared[-1]['unit_median']:.1f} 倍）。",
        f"同一房型内部租金与面积几乎不相关（整租 r={rent_area_corr['整租']}、"
        f"合租 r={rent_area_corr['合租']}），租金近似按房型固定；"
        f"所以单价从 {low_area['band']} 的 {low_area['unit_median']} 元/㎡ "
        f"降到 {high_area['band']} 的 {high_area['unit_median']} 元/㎡，"
        "主要是「总价÷面积」的机械结果，不是小户型溢价。",
        f"地铁、学区、医院、商场四个标签的单价差异最大仅 "
        f"{abs(max_amen['diff_pct'])}%（{max_amen['label']}，方向为负），"
        f"装修和楼层的组间差异不到 1%，朝向最大 {attr_spread['朝向']}%；"
        "这些字段在当前样本里的区分度有限，不能据此写「地铁房溢价」的结论。",
        f"2024 年月均单价 {m2024:.1f} 元/㎡，2025 年 {m2025:.1f} 元/㎡，"
        f"变化 {trend_pct}%，月度波动大于年度趋势，看不出明显上涨或季节性。",
    ]

    return jsonable({
        "overview": overview,
        "data_notes": [
            "数据来源：作者从和鲸社区、天池等公开数据社区下载整理，具体下载链接未保留；北京市租房数据集（35,082 条），字段含区域/商圈/小区/租金/面积/房型/配套/经纬度。",
            "单价 = 租金 ÷ 面积，原数据已自带该字段，复核误差 < 0.01 元/㎡。",
            "区域对比统一先分「整租 / 合租」，避免房型结构差异造成辛普森悖论。",
            "地铁距离单位为公里：有地铁标签的房源距离 0.1–1.5km，无标签的为 1.5–5km。",
            "配套与装修字段的组间差异接近 0，分析中如实标注，不强行解释为溢价。",
        ],
        "rent_types": rent_types,
        "districts": districts,
        "district_by_type": district_by_type,
        "area_bands": area_bands,
        "area_gap": small_gap,
        "rent_area_corr": rent_area_corr,
        "amenities": amenities,
        "subway_distance": subway_distance,
        "attributes": attributes,
        "attribute_spread_pct": attr_spread,
        "trend": trend,
        "scatter": scatter,
        "insights": insights,
    })
