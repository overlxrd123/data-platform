"""北京餐饮行业分析 — 内容口径。

数据：44,512 家北京店铺（高德/大众点评口径），16 区。
关键清洗：
  1. 人均消费 = 0 表示未采集到价格，不是「免费」，必须剔除后再算价格统计；
  2. 评分缺失 60.8%，评分分析只在有评分样本上做；
  3. 评论数中位数为 0，热度分析同时看「零评论占比」和「头部集中度」。
"""
import re
from functools import lru_cache

import numpy as np
import pandas as pd

from .data import load_food, jsonable

PRICE_BANDS = [
    ("30元以下", 0, 30),
    ("30-60元", 30, 60),
    ("60-100元", 60, 100),
    ("100-200元", 100, 200),
    ("200元以上", 200, np.inf),
]

MICHELIN_ORDER = ["银牌", "金牌", "铂金", "钻石", "黑钻"]


def _prepare():
    df = load_food().copy()
    df = df.rename(columns={
        "人均消费": "price",
        "评分": "rating",
        "评论数量": "reviews",
        "菜系类型": "cuisine",
        "归属商圈": "area",
        "county": "district",
        "米其林推荐指数": "michelin",
        "营业时间": "hours",
    })
    df["cuisine"] = df["cuisine"].fillna("未标注")
    df["area"] = df["area"].fillna("未标注")
    return df


def _price_band(price):
    for label, lo, hi in PRICE_BANDS:
        if lo <= price < hi:
            return label
    return PRICE_BANDS[-1][0]


def _parse_hours(text):
    """返回 (开门小时, 关门小时)，解析失败返回 None。

    样本格式：'营业中 10:30-23:30' / '休息中 09:30营业' / '营业中 全天营业'
    """
    if not isinstance(text, str):
        return None
    if "全天" in text:
        return (0.0, 24.0)
    m = re.search(r"(\d{1,2}):(\d{2})\s*[-–—~至]\s*(次日)?\s*(\d{1,2}):(\d{2})", text)
    if not m:
        return None
    open_h = int(m.group(1)) + int(m.group(2)) / 60
    close_h = int(m.group(4)) + int(m.group(5)) / 60
    if m.group(3) or close_h < open_h:
        close_h += 24
    return (open_h, close_h)


@lru_cache(maxsize=1)
def _prepared():
    """缓存清洗后的明细表，供整体分析和按条件推荐共用。"""
    return _prepare()


def _shop_rows(sub):
    return [
        {
            "name": str(row["店铺名称"]).strip(),
            "cuisine": row["cuisine"],
            "district": row["district"],
            "area": row["area"],
            "price": int(row["price"]),
            "rating": round(float(row["rating"]), 1) if pd.notna(row["rating"]) else None,
            "reviews": int(row["reviews"]),
            "michelin": None if pd.isna(row["michelin"]) else str(row["michelin"]),
        }
        for _, row in sub.iterrows()
    ]


def _to_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=64)
def recommend_food(district=None, max_price=None, min_price=None,
                   cuisine=None, limit=8) -> dict:
    """按区域/菜系/价格筛选具体店铺。

    默认要求「有评分 + 评论数 ≥ 50」；样本不足时依次放宽到 10 条、
    只要评分非空，并在返回里用 relaxed 标记，避免给出 1 条评论的 5.0 分。
    """
    df = _prepared()
    pool = df[df["price"] > 0]

    if district and str(district).strip() not in ("北京", "全北京", "全市", "不限"):
        name = str(district).strip()
        if name and not name.endswith(("区", "县")):
            name += "区"
        pool = pool[pool["district"] == name]

    if cuisine and str(cuisine).strip() not in ("", "餐厅", "美食", "饭店", "不限"):
        pool = pool[pool["cuisine"].astype(str).str.contains(str(cuisine).strip(), na=False)]

    min_price = _to_float(min_price)
    max_price = _to_float(max_price)
    if min_price is not None:
        pool = pool[pool["price"] >= min_price]
    if max_price is not None:
        pool = pool[pool["price"] <= max_price]

    base = pool[pool["rating"].notna() & (pool["reviews"] >= 50)]
    relaxed = False
    if base.empty:
        base = pool[pool["rating"].notna() & (pool["reviews"] >= 10)]
        relaxed = not base.empty
    if base.empty:
        base = pool[pool["rating"].notna()]
        relaxed = not base.empty

    limit = max(1, min(int(limit), 8))
    ranked = base.sort_values(
        ["rating", "reviews"], ascending=[False, False]
    ).head(limit)

    return jsonable({
        "filters": {
            "district": district,
            "cuisine": cuisine,
            "min_price": min_price,
            "max_price": max_price,
        },
        "matched": int(len(base)),
        "relaxed": relaxed,
        "shops": _shop_rows(ranked),
    })


@lru_cache(maxsize=1)
def get_food_analysis() -> dict:
    df = _prepared()
    valid = df[df["price"] > 0].copy()
    valid["price_band"] = valid["price"].apply(_price_band)
    rated = valid[valid["rating"].notna()]
    hours = df["hours"].dropna().apply(_parse_hours).dropna()
    late = hours[hours.apply(lambda x: x[1] >= 22)]

    # ── 概览 ───────────────────────────────────────────
    overview = {
        "stores": int(len(df)),
        "stores_with_price": int(len(valid)),
        "price_coverage_pct": round(len(valid) / len(df) * 100, 1),
        "stores_rated": int(df["rating"].notna().sum()),
        "rating_coverage_pct": round(df["rating"].notna().mean() * 100, 1),
        "rating_coverage_of_valid_pct": round(valid["rating"].notna().mean() * 100, 1),
        "price_median": int(valid["price"].median()),
        "price_mean": round(valid["price"].mean(), 1),
        "price_p75": int(valid["price"].quantile(0.75)),
        "price_p90": int(valid["price"].quantile(0.90)),
        "districts": int(df["district"].nunique()),
        "cuisines": int(df["cuisine"].nunique()),
        "business_areas": int(df.loc[df["area"] != "未标注", "area"].nunique()),
        "reviews_total": int(valid["reviews"].sum()),
        "zero_review_pct": round((valid["reviews"] == 0).mean() * 100, 1),
    }

    # ── 价格分布（0-300，超过 300 并入最后一档）──────────
    clipped = valid["price"].clip(upper=300)
    counts, edges = np.histogram(clipped, bins=np.arange(0, 311, 10))
    price_distribution = [
        {"start": int(edges[i]), "end": int(edges[i + 1]), "count": int(counts[i])}
        for i in range(len(counts))
    ]

    # ── 价格带结构 ─────────────────────────────────────
    price_bands = []
    for label, lo, hi in PRICE_BANDS:
        sub = valid[valid["price_band"] == label]
        top = sub["cuisine"].value_counts().head(3)
        price_bands.append({
            "band": label,
            "stores": int(len(sub)),
            "share_pct": round(len(sub) / len(valid) * 100, 1),
            "median_price": int(sub["price"].median()) if len(sub) else None,
            "avg_rating": round(sub["rating"].mean(), 2) if sub["rating"].notna().any() else None,
            "top_cuisines": [{"name": k, "stores": int(v)} for k, v in top.items()],
        })

    # ── 菜系：规模 / 溢价 / 口碑 ───────────────────────
    cuisine = (
        valid.groupby("cuisine")
        .agg(
            stores=("price", "size"),
            median_price=("price", "median"),
            mean_price=("price", "mean"),
            avg_rating=("rating", "mean"),
            median_reviews=("reviews", "median"),
        )
        .query("stores >= 30")
        .sort_values("median_price", ascending=False)
    )
    cuisine_table = [
        {
            "name": name,
            "stores": int(row["stores"]),
            "share_pct": round(row["stores"] / len(valid) * 100, 1),
            "median_price": int(row["median_price"]),
            "mean_price": round(row["mean_price"], 1),
            "avg_rating": None if pd.isna(row["avg_rating"]) else round(row["avg_rating"], 2),
            "median_reviews": int(row["median_reviews"]),
        }
        for name, row in cuisine.iterrows()
    ]

    # ── 区域 ───────────────────────────────────────────
    district = (
        valid.groupby("district")
        .agg(
            stores=("price", "size"),
            median_price=("price", "median"),
            p90_price=("price", lambda s: s.quantile(0.90)),
            avg_rating=("rating", "mean"),
        )
        .sort_values("median_price", ascending=False)
    )
    districts = [
        {
            "name": name,
            "stores": int(row["stores"]),
            "median_price": int(row["median_price"]),
            "p90_price": int(row["p90_price"]),
            "avg_rating": None if pd.isna(row["avg_rating"]) else round(row["avg_rating"], 2),
        }
        for name, row in district.iterrows()
    ]

    # ── 商圈（样本 >= 80）──────────────────────────────
    area_df = valid[valid["area"] != "未标注"]
    area = (
        area_df.groupby("area")
        .agg(
            stores=("price", "size"),
            median_price=("price", "median"),
            avg_rating=("rating", "mean"),
        )
        .query("stores >= 80")
        .sort_values("median_price", ascending=False)
    )
    business_areas = [
        {
            "name": name,
            "stores": int(row["stores"]),
            "median_price": int(row["median_price"]),
            "avg_rating": None if pd.isna(row["avg_rating"]) else round(row["avg_rating"], 2),
        }
        for name, row in area.iterrows()
    ]

    # ── 评分 ───────────────────────────────────────────
    rating_dist = rated["rating"].round(1).value_counts().sort_index()
    by_band = []
    for label, _, _ in PRICE_BANDS:
        sub = rated[rated["price_band"] == label]
        by_band.append({
            "band": label,
            "rated_stores": int(len(sub)),
            "avg_rating": round(sub["rating"].mean(), 2) if len(sub) else None,
        })
    corr = rated[["price", "rating"]].corr(method="spearman").iloc[0, 1]
    rating = {
        "rated_stores": int(len(rated)),
        "distribution": [{"score": float(k), "count": int(v)} for k, v in rating_dist.items()],
        "by_price_band": by_band,
        "price_rating_corr": round(float(corr), 3),
    }

    # ── 评论热度集中度 ─────────────────────────────────
    rev_sorted = valid["reviews"].sort_values(ascending=False)
    total_rev = rev_sorted.sum()
    concentration = {
        "total_reviews": int(total_rev),
        "top1_pct_share": round(rev_sorted.head(max(1, int(len(rev_sorted) * 0.01))).sum() / total_rev * 100, 1),
        "top5_pct_share": round(rev_sorted.head(max(1, int(len(rev_sorted) * 0.05))).sum() / total_rev * 100, 1),
        "top10_pct_share": round(rev_sorted.head(max(1, int(len(rev_sorted) * 0.10))).sum() / total_rev * 100, 1),
    }

    # ── 米其林体系 ─────────────────────────────────────
    michelin = []
    for tier in MICHELIN_ORDER:
        sub = valid[valid["michelin"] == tier]
        if len(sub) == 0:
            continue
        michelin.append({
            "tier": tier,
            "stores": int(len(sub)),
            "median_price": int(sub["price"].median()),
            "mean_price": round(sub["price"].mean(), 1),
            "avg_rating": round(sub["rating"].mean(), 2) if sub["rating"].notna().any() else None,
        })

    # ── 营业时间 ───────────────────────────────────────
    # 只有约 31% 的店铺能解析出完整时段（多数只有「几点营业」没有打烊时间），
    # 所以夜宵比例只在「有完整时段」的样本上计算，不能外推到全部店铺。
    parsed = df[df["hours"].apply(_parse_hours).notna()].copy()
    parsed["close_hour"] = parsed["hours"].apply(_parse_hours).apply(lambda x: x[1])
    parsed["is_late"] = parsed["close_hour"] >= 23
    district_late = (
        parsed.groupby("district")
        .agg(parsed_stores=("is_late", "size"), late_stores=("is_late", "sum"))
        .query("parsed_stores >= 50")
    )
    district_late["late_pct"] = (
        district_late["late_stores"] / district_late["parsed_stores"] * 100
    ).round(1)
    district_late = district_late.sort_values("late_pct", ascending=False)
    late_rows = parsed[parsed["is_late"]]
    late_night = {
        "parsed_stores": int(len(parsed)),
        "parsed_pct": round(len(parsed) / len(df) * 100, 1),
        "late_stores": int(len(late_rows)),
        "late_pct_of_parsed": round(len(late_rows) / len(parsed) * 100, 1) if len(parsed) else None,
        "late_median_price": int(late_rows.loc[late_rows["price"] > 0, "price"].median()) if len(late_rows) else None,
        "top_districts": [
            {
                "name": name,
                "parsed_stores": int(row["parsed_stores"]),
                "late_pct": float(row["late_pct"]),
            }
            for name, row in district_late.head(5).iterrows()
        ],
    }

    # ── 推荐候选 ───────────────────────────────────────
    # 只在「有评分 + 评论数 ≥ 50」的样本里推荐：评分缺失 60.8%，
    # 且 1 条评论的 5.0 分没有参考价值。推荐结果不是全量店铺排名。
    rec_pool = valid[valid["rating"].notna() & (valid["reviews"] >= 50)].copy()

    top_rated = rec_pool.sort_values(
        ["rating", "reviews"], ascending=[False, False]
    ).head(8)
    value = rec_pool[rec_pool["price"] <= 100].sort_values(
        ["rating", "reviews"], ascending=[False, False]
    ).head(6)
    popular = valid[valid["reviews"] > 0].sort_values(
        ["reviews", "rating"], ascending=[False, False]
    ).head(6)
    recommendations = {
        "eligible_stores": int(len(rec_pool)),
        "rule": "评分非空且评论数 ≥ 50；按评分、评论数排序",
        "top_rated": _shop_rows(top_rated),
        "value": _shop_rows(value),
        "popular": _shop_rows(popular),
    }

    # ── 业务结论 ───────────────────────────────────────
    top_cuisine = cuisine_table[0] if cuisine_table else None
    cheapest_district = districts[-1] if districts else None
    priciest_district = districts[0] if districts else None
    insights = [
        f"价格数据覆盖 {overview['price_coverage_pct']}%（{len(valid):,}/{len(df):,} 家），"
        f"其余 {overview['stores'] - len(valid):,} 家人均消费记为 0，是未采集而非免费，已剔除。",
        f"有效样本人均消费中位数 ¥{overview['price_median']}，"
        f"P90 为 ¥{overview['price_p90']}——八成店铺人均在 145 元以内，北京餐饮主体仍是大众消费。",
        f"区域价差显著：{priciest_district['name']}中位价 ¥{priciest_district['median_price']}，"
        f"{cheapest_district['name']}仅 ¥{cheapest_district['median_price']}，相差 "
        f"{priciest_district['median_price'] / max(cheapest_district['median_price'], 1):.1f} 倍。",
        f"评论高度头部化：前 1% 店铺拿走 {concentration['top1_pct_share']}% 的评论，"
        f"前 10% 拿走 {concentration['top10_pct_share']}%，而 {overview['zero_review_pct']}% 的店铺一条评论都没有。",
        f"评分与价格只有弱相关（Spearman {rating['price_rating_corr']}）："
        f"均价从 30 元以下的 4.47 分升到 200 元以上的 4.66 分，"
        "方向对但差距很小——贵不等于好吃，高价更多来自品类和商圈定位。",
        f"米其林体系内部价格断层明显：银牌中位价 ¥{michelin[0]['median_price']}，"
        f"金牌 ¥{michelin[1]['median_price']}，铂金及以上进入千元档。",
        f"在有完整营业时段的 {late_night['parsed_stores']:,} 家店里，"
        f"{late_night['late_pct_of_parsed']}% 营业到 23 点以后；"
        f"夜宵比例最高的是{late_night['top_districts'][0]['name']}"
        f"（{late_night['top_districts'][0]['late_pct']}%），"
        f"其次是{late_night['top_districts'][1]['name']}"
        f"（{late_night['top_districts'][1]['late_pct']}%）。"
        "注意这只能说明「可解析时段」的样本，不能外推到全量店铺。",
    ]
    if top_cuisine:
        insights.append(
            f"{top_cuisine['name']}是溢价最高的主流菜系（中位价 ¥{top_cuisine['median_price']}），"
            "而同为高店铺数的火锅中位价更低，说明「品类规模」和「客单价」不是一回事。"
        )

    return jsonable({
        "overview": overview,
        "data_notes": [
            "人均消费为 0 的记录视为未采集，价格类统计全部剔除，共 13,309 家（29.9%）。",
            "评分缺失 60.8%，评分相关分析只在有评分的 16,025 家（占有效样本 51.4%）上做。",
            "评论数中位数为 0，热度分析同时看零评论占比和头部集中度。",
            "营业时间只有 31.1% 能解析出完整时段，夜宵比例仅在该子样本上计算。",
        ],
        "price_distribution": price_distribution,
        "price_bands": price_bands,
        "cuisine_table": cuisine_table,
        "districts": districts,
        "business_areas": business_areas,
        "rating": rating,
        "review_concentration": concentration,
        "michelin": michelin,
        "late_night": late_night,
        "recommendations": recommendations,
        "insights": insights,
    })
