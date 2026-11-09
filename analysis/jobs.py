"""数据岗招聘 — 薪资解析与岗位结构。

这份数据有三个必须先处理的问题，否则结论会失真：
  1. 薪资是字符串（「1.2-1.8万·14薪」「20-35万/年」），单位、月/年、
     发薪月数混在一起，必须先统一成月薪与年包两个口径；
  2. 招聘数据按「数据」关键词抓取，但混入了销售、质量、结构、机械等
     非数据岗（约一半），不剔除会稀释岗位结构；
  3. 发布时间一半集中在同一天，是抓取时间而非真实发布时间，
     不能用来分析招聘需求的时间趋势。
"""
import re
from functools import lru_cache

import numpy as np
import pandas as pd

from .data import jsonable, load_jobs

EXPERIENCE_ORDER = ["无需经验", "1年", "2年", "3-4年", "5-7年", "8-9年", "10年以上"]
EDUCATION_ORDER = ["高中", "中技/中专", "大专", "本科", "硕士", "博士"]
SIZE_ORDER = ["少于50人", "50-150人", "150-500人", "500-1000人",
              "1000-5000人", "5000-10000人", "10000人以上"]

_SALARY_RE = re.compile(
    r"^([0-9.]+)(千|万)?-([0-9.]+)(千|万)(·([0-9]+)薪|/年)?$"
)
_UNIT = {"千": 1000, "万": 10000}


def _parse_salary(s):
    """返回 (月薪下限, 月薪上限, 年薪下限, 年薪上限, 发薪月数)。"""
    s = str(s).strip()
    m = _SALARY_RE.match(s)
    if m:
        a, ua, b, ub, rest, months = m.groups()
        ua = ua or ub                      # 「2-4万」左边省略单位，沿用右边
        lo = float(a) * _UNIT[ua]
        hi = float(b) * _UNIT[ub]
        if rest == "/年":
            return lo / 12, hi / 12, lo, hi, 12
        mo = int(months) if months else 12
        return lo, hi, lo * mo, hi * mo, mo
    m = re.match(r"^([0-9.]+)千及以下$", s)
    if m:
        v = float(m.group(1)) * 1000
        return v, v, v * 12, v * 12, 12
    m = re.match(r"^([0-9.]+)元/天$", s)
    if m:
        v = float(m.group(1))
        return v * 21.75, v * 21.75, v * 261, v * 261, 12
    m = re.match(r"^([0-9.]+)千/天$", s)
    if m:
        v = float(m.group(1)) * 1000
        return v * 21.75, v * 21.75, v * 261, v * 261, 12
    return np.nan, np.nan, np.nan, np.nan, np.nan


def _family(title):
    """按岗位名称做职能分类（数据集没有 JD 文本，只能做到这一层）。"""
    t = str(title)
    if any(k in t for k in
           ["算法", "机器学习", "深度学习", "NLP", "CV", "大模型", "推荐",
            "数据挖掘", "数据科学家"]):
        return "算法"
    if any(k in t for k in ["数据治理", "数据质量", "元数据"]):
        return "数据治理"
    if any(k in t for k in ["数据产品", "数据运营", "数据策略"]):
        return "数据产品/运营"
    if any(k in t for k in ["BI", "商业分析", "业务分析", "经营分析"]):
        return "BI/商业分析"
    if "需求分析" in t:
        return "需求分析"
    if any(k in t for k in
           ["数据开发", "大数据开发", "ETL", "数仓", "数据仓库", "数据平台",
            "数据架构", "数据工程", "数据库开发", "报表开发"]):
        return "数据开发"
    if any(k in t for k in ["数据分析", "数据专员", "数据统计", "Data Analyst"]):
        return "数据分析"
    if any(k in t for k in
           ["数据管理", "数据采集", "数据处理", "数据建模", "数据运维", "大数据运维"]):
        return "数据相关其他"
    return "非数据/其他"


def _stats(sub):
    m = sub["monthly_mid"].dropna()
    a = sub["annual_mid"].dropna()
    if not len(m):
        return {"count": int(len(sub)), "monthly_median": None,
                "annual_median": None, "monthly_p25": None, "monthly_p75": None}
    return {
        "count": int(len(sub)),
        "monthly_median": int(round(m.median())),
        "annual_median": int(round(a.median())) if len(a) else None,
        "monthly_p25": int(round(m.quantile(.25))),
        "monthly_p75": int(round(m.quantile(.75))),
    }


@lru_cache(maxsize=1)
def get_jobs_analysis() -> dict:
    df = load_jobs().copy()
    df.columns = [c.strip() for c in df.columns]

    parsed = df["薪资"].apply(_parse_salary)
    parsed = pd.DataFrame(
        parsed.tolist(), columns=["m_lo", "m_hi", "a_lo", "a_hi", "months"],
        index=df.index,
    )
    df = pd.concat([df, parsed], axis=1)
    df["monthly_mid"] = (df["m_lo"] + df["m_hi"]) / 2
    df["annual_mid"] = (df["a_lo"] + df["a_hi"]) / 2
    df["family"] = df["岗位名称"].map(_family)

    total = len(df)
    city_counts = df["公司所在城市地点"].value_counts()
    top3 = city_counts.head(3)
    date_counts = df["发布时间"].str[:10].value_counts()
    top_date = date_counts.index[0]

    # ── 概况 ───────────────────────────────────────────
    salary_ok = df["monthly_mid"].notna()
    overview = {
        "postings": int(total),
        "companies": int(df["公司名称"].nunique()),
        "cities": int(df["公司所在城市地点"].nunique()),
        "top3_city_share_pct": round(float(top3.sum() / total) * 100, 1),
        "data_job_share_pct": round(float((df["family"] != "非数据/其他").mean()) * 100, 1),
        "salary_parsed": int(salary_ok.sum()),
        "salary_parsed_pct": round(float(salary_ok.mean()) * 100, 1),
        "monthly_median": int(round(df.loc[salary_ok, "monthly_mid"].median())),
        "monthly_p25": int(round(df.loc[salary_ok, "monthly_mid"].quantile(.25))),
        "monthly_p75": int(round(df.loc[salary_ok, "monthly_mid"].quantile(.75))),
        "annual_median": int(round(df.loc[salary_ok, "annual_mid"].median())),
        "multi_month_share_pct": round(
            float(df["薪资"].astype(str).str.contains("·[0-9]+薪").mean()) * 100, 1
        ),
        "date_start": str(df["发布时间"].min())[:10],
        "date_end": str(df["发布时间"].max())[:10],
        "top_date": str(top_date),
        "top_date_share_pct": round(float(date_counts.iloc[0] / total) * 100, 1),
    }

    # ── 城市 ───────────────────────────────────────────
    cities = []
    for city, sub in df.groupby("公司所在城市地点"):
        if len(sub) < 30:
            continue
        row = {"city": city, "share_pct": round(len(sub) / total * 100, 1)}
        row.update(_stats(sub))
        cities.append(row)
    cities.sort(key=lambda x: -x["monthly_median"])

    # 控制岗位族 / 经验后的城市对比（避免「岗位结构不同」被误读成「同岗不同价」）
    city_controlled = []
    da = df[df["family"] == "数据分析"]
    da_mid = da[da["工作经验"].isin(["2年", "3-4年"])]
    for city in [c["city"] for c in cities]:
        all_sub = df[df["公司所在城市地点"] == city]
        da_sub = da[da["公司所在城市地点"] == city]
        mid_sub = da_mid[da_mid["公司所在城市地点"] == city]
        city_controlled.append({
            "city": city,
            "all_n": int(len(all_sub)),
            "all_median": _stats(all_sub)["monthly_median"],
            "da_n": int(len(da_sub)),
            "da_median": _stats(da_sub)["monthly_median"],
            "da_mid_n": int(len(mid_sub)),
            "da_mid_median": _stats(mid_sub)["monthly_median"] if len(mid_sub) >= 10 else None,
        })

    # ── 经验 / 学历 / 公司 ─────────────────────────────
    experience = []
    for name in EXPERIENCE_ORDER:
        sub = df[df["工作经验"] == name]
        if not len(sub):
            continue
        row = {"group": name}
        row.update(_stats(sub))
        experience.append(row)

    education = []
    for name in EDUCATION_ORDER:
        sub = df[df["学历要求"] == name]
        if not len(sub):
            continue
        row = {"group": name}
        row.update(_stats(sub))
        education.append(row)

    company_type = []
    for name, sub in df.groupby("公司性质"):
        if len(sub) < 10:
            continue
        row = {"group": name}
        row.update(_stats(sub))
        company_type.append(row)
    company_type.sort(key=lambda x: -x["monthly_median"])

    company_size = []
    for name in SIZE_ORDER:
        sub = df[df["公司人员规模"] == name]
        if not len(sub):
            continue
        row = {"group": name}
        row.update(_stats(sub))
        company_size.append(row)

    # ── 岗位族 ─────────────────────────────────────────
    family_order = ["算法", "BI/商业分析", "数据开发", "数据治理", "需求分析",
                    "数据相关其他", "数据产品/运营", "数据分析", "非数据/其他"]
    families = []
    for name in family_order:
        sub = df[df["family"] == name]
        if not len(sub):
            continue
        row = {"family": name, "share_pct": round(len(sub) / total * 100, 1)}
        row.update(_stats(sub))
        families.append(row)

    # ── 发薪月数 ───────────────────────────────────────
    month_bucket = df["months"].fillna(12)
    month_dist = []
    for label, mask in [
        ("12薪", month_bucket <= 12),
        ("13薪", month_bucket == 13),
        ("14薪", month_bucket == 14),
        ("15薪及以上", month_bucket >= 15),
    ]:
        sub = df[mask]
        month_dist.append({
            "label": label,
            "count": int(len(sub)),
            "share_pct": round(len(sub) / total * 100, 1),
            "monthly_median": _stats(sub)["monthly_median"],
        })

    # ── 时间：只展示，不下结论 ─────────────────────────
    daily = [
        {"date": str(d), "count": int(n)}
        for d, n in date_counts.sort_index().items()
    ]

    # ── 结论 ───────────────────────────────────────────
    top_city = cities[0]
    beijing = next((c for c in city_controlled if c["city"] == "北京"), None)
    shanghai = next((c for c in city_controlled if c["city"] == "上海"), None)
    shenzhen = next((c for c in city_controlled if c["city"] == "深圳"), None)
    guangzhou = next((c for c in city_controlled if c["city"] == "广州"), None)
    exp_none = next(x for x in experience if x["group"] == "无需经验")
    exp_1 = next(x for x in experience if x["group"] == "1年")
    exp_34 = next(x for x in experience if x["group"] == "3-4年")
    exp_57 = next(x for x in experience if x["group"] == "5-7年")
    exp_89 = next(x for x in experience if x["group"] == "8-9年")
    edu_map = {x["group"]: x for x in education}
    fam_map = {x["family"]: x for x in families}
    size_map = {x["group"]: x for x in company_size}

    insights = [
        f"共 {total:,} 条岗位、{overview['companies']:,} 家公司、"
        f"{overview['cities']} 个城市；上海/北京/深圳合计 "
        f"{overview['top3_city_share_pct']}%，岗位高度集中在三个一线城市。",
        f"按岗位名称分类，只有 {overview['data_job_share_pct']}% 是数据相关岗位，"
        f"其余是销售工程师、质量工程师、结构工程师等——"
        "招聘数据按关键词抓取，混入了大量非目标岗位；不先清洗，"
        "「数据岗薪资」会被非数据岗稀释。",
        f"全样本月薪中位数 {overview['monthly_median']:,} 元，"
        f"年包中位数 {overview['annual_median']:,} 元；"
        f"{overview['multi_month_share_pct']}% 的岗位写了 13 薪及以上，"
        "所以「月薪 × 12」会低估实际年包。",
        f"经验溢价明显：1 年 {exp_1['monthly_median']:,} 元 → "
        f"3-4 年 {exp_34['monthly_median']:,} 元 → "
        f"5-7 年 {exp_57['monthly_median']:,} 元 → "
        f"8-9 年 {exp_89['monthly_median']:,} 元；"
        f"从 1 年到 3-4 年月薪中位数提升 "
        f"{(exp_34['monthly_median'] / exp_1['monthly_median'] - 1) * 100:.0f}%，"
        "是职业早期最明显的一次跃迁。3-4 年也是招聘量最大的经验段。"
        f"注意「无需经验」中位 {exp_none['monthly_median']:,} 元，"
        f"反而高于 1 年的 {exp_1['monthly_median']:,} 元——"
        "这不是经验倒挂，而是无经验岗位里混入了算法/开发等高薪校招岗，"
        "说明分组比较前要先看组内岗位结构。"
        "（8 年以上样本仅 61 / 28 条，高段位中位数波动较大。）",
        f"岗位族薪资排序：算法 {fam_map['算法']['monthly_median']:,} 元 > "
        f"BI/商业分析 {fam_map['BI/商业分析']['monthly_median']:,} 元 > "
        f"数据开发 {fam_map['数据开发']['monthly_median']:,} 元 > "
        f"数据分析 {fam_map['数据分析']['monthly_median']:,} 元——"
        f"数据分析岗位数量最多（{fam_map['数据分析']['count']} 条），"
        "但薪资最低，供给最饱和；往「分析 + 工程」或「分析 + 算法」走才有溢价。",
        f"城市差异不能只看总中位数：北京全样本 "
        f"{beijing['all_median']:,} 元，但同为数据分析岗时 "
        f"{beijing['da_median']:,} 元，限定 2-4 年经验后 "
        f"{beijing['da_mid_median']:,} 元；上海/深圳/广州同条件下分别为 "
        f"{shanghai['da_mid_median']:,} / {shenzhen['da_mid_median']:,} / "
        f"{guangzhou['da_mid_median']:,} 元——北京始终最高，且控制岗位与经验后，"
        f"与上海的差距从全样本的 "
        f"{(beijing['all_median'] / shanghai['all_median'] - 1) * 100:.0f}% "
        f"扩大到 {(beijing['da_mid_median'] / shanghai['da_mid_median'] - 1) * 100:.0f}%，"
        "说明北京的高薪不只是「高薪岗位占比更高」造成的。",
        f"学历溢价：大专 {edu_map['大专']['monthly_median']:,} 元、"
        f"本科 {edu_map['本科']['monthly_median']:,} 元、"
        f"硕士 {edu_map['硕士']['monthly_median']:,} 元；"
        "本科到硕士的溢价约 "
        f"{(edu_map['硕士']['monthly_median'] / edu_map['本科']['monthly_median'] - 1) * 100:.0f}%，"
        "但硕士岗位数量只有本科的 "
        f"{edu_map['硕士']['count'] / edu_map['本科']['count'] * 100:.0f}%。",
        f"公司规模与薪资正相关：10000 人以上 "
        f"{size_map['10000人以上']['monthly_median']:,} 元，"
        f"少于 50 人 {size_map['少于50人']['monthly_median']:,} 元，"
        f"相差 {(size_map['10000人以上']['monthly_median'] / size_map['少于50人']['monthly_median'] - 1) * 100:.0f}%。",
        f"时间维度不可用：{overview['top_date_share_pct']}% 的岗位发布时间都是 "
        f"{overview['top_date']}，仅凭日期集中不能区分抓取时间和发布时间，"
        "因此本模块不做「招聘需求上升/下降」的趋势判断。",
    ]

    return jsonable({
        "overview": overview,
        "data_notes": [
            "作者从和鲸社区、天池等公开数据社区下载整理，原始下载链接未保留；采样范围和发布时间含义未独立核实。",
            "薪资解析覆盖 3,486/3,523 条（98.9%）；37 条为空，未参与薪资统计。",
            "月薪统一为税前月薪；年包 = 月薪 × 发薪月数（默认 12，13/14/15 薪按标注）。",
            "「20-35万/年」按年包直接除以 12 换算月薪；日薪按 21.75 天/月、261 天/年折算。",
            "岗位族按岗位名称关键词分类，没有 JD 文本，无法做技能词频与技能溢价。",
            "发布时间 50.1% 集中在 2023-11-30，不据此推断招聘需求趋势。",
            "学历缺失 120 条、公司规模缺失 184 条，分组统计时自然排除。",
        ],
        "cities": cities,
        "city_controlled": city_controlled,
        "experience": experience,
        "education": education,
        "company_type": company_type,
        "company_size": company_size,
        "families": families,
        "month_distribution": month_dist,
        "daily": daily,
        "insights": insights,
    })
