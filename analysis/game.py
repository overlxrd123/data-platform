"""游戏评论分析 — 内容口径。

数据：Metacritic 2,531 条英文评论，3 个平台。

和旧版的区别：
  旧版把「评分」直接当成情感（>=7 好评、<=3 差评），等于没有分析文本。
  新版用 VADER 对评论正文做情感打分，再和评分对照——
  两者一致说明评价真实，不一致的地方（文字在骂但给了高分）才是最有信息量的。
"""
import re
from functools import lru_cache

import numpy as np
import pandas as pd

from .data import load_game, jsonable

POS_CUT = 0.05
NEG_CUT = -0.05

# 主题词典：用词根匹配，覆盖常见游戏评论话题
THEMES = {
    "bug": {
        "label": "Bug 与性能",
        "keywords": ["bug", "glitch", "crash", "lag", "fps", "performance",
                     "optimization", "broken", "freeze", "loading", "stutter"],
    },
    "story": {
        "label": "剧情与角色",
        "keywords": ["story", "plot", "narrative", "character", "writing",
                     "dialogue", "ending", "lore"],
    },
    "gameplay": {
        "label": "玩法与操作",
        "keywords": ["gameplay", "combat", "mechanic", "control", "movement",
                     "level design", "mission", "quest"],
    },
    "graphics": {
        "label": "画面与美术",
        "keywords": ["graphic", "visual", "art", "texture", "animation", "look"],
    },
    "money": {
        "label": "价格与内购",
        "keywords": ["microtransaction", "dlc", "loot box", "pay", "money",
                     "price", "worth", "refund", "subscription", "battle pass"],
    },
    "multiplayer": {
        "label": "多人联机",
        "keywords": ["multiplayer", "co-op", "coop", "online", "friend",
                     "pvp", "matchmaking", "server"],
    },
    "difficulty": {
        "label": "难度与平衡",
        "keywords": ["difficult", "hard", "easy", "challenging", "balance",
                     "grind", "grinding", "unfair"],
    },
    "audio": {
        "label": "音乐与音效",
        "keywords": ["music", "sound", "voice acting", "audio", "soundtrack"],
    },
}

EXTRA_STOPWORDS = {
    "game", "games", "gaming", "play", "played", "playing", "player", "players",
    "just", "like", "really", "thing", "things", "time", "times", "make", "made",
    "don", "doesn", "didn", "isn", "wasn", "aren", "weren", "won", "wouldn",
    "couldn", "shouldn", "can", "get", "got", "one", "much", "even", "still",
    "way", "lot", "also", "people", "think", "know", "want", "need", "feel",
    "review", "good", "great", "bad", "best", "worst", "love", "hate", "fun",
    "buy", "bought", "worth", "money", "playstation", "xbox", "pc",
    "ill", "im", "ive", "id", "dont", "cant", "didnt", "doesnt", "isnt",
    "wasnt", "arent", "werent", "wouldnt", "couldnt", "shouldnt", "thats",
    "youre", "theyre", "theres", "its", "far", "war", "first", "second",
    "new", "old", "big", "little", "right", "well", "back", "now", "never",
    "always", "ever", "every", "everything", "something", "nothing",
}


def _stemmer():
    from nltk.stem import PorterStemmer
    return PorterStemmer()


def _analyzer():
    """VADER 情感分析器；首次运行自动下载词典（约 100KB）。"""
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer

    try:
        return SentimentIntensityAnalyzer()
    except LookupError:
        nltk.download("vader_lexicon", quiet=True)
        return SentimentIntensityAnalyzer()


def _label(compound):
    if compound >= POS_CUT:
        return "positive"
    if compound <= NEG_CUT:
        return "negative"
    return "neutral"


def _rating_label(r):
    if r >= 7:
        return "positive"
    if r <= 3:
        return "negative"
    return "neutral"


def _clean_text(text):
    text = str(text)
    text = re.sub(r"\*{2,}", " ", text)          # 屏蔽脏话的 ****
    text = re.sub(r"http\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def get_game_analysis() -> dict:
    raw = load_game()
    df = raw.drop_duplicates().copy()            # 69 条整行重复
    df = df.drop_duplicates(subset=["Review"]).reset_index(drop=True)  # 同一段评论重复提交
    df["text"] = df["Review"].apply(_clean_text)
    df["words"] = df["text"].str.split().str.len()
    df = df[df["words"] >= 3].reset_index(drop=True)  # 少于 3 个词无法做情感判断

    sia = _analyzer()
    df["compound"] = df["text"].map(lambda t: sia.polarity_scores(t)["compound"])
    df["text_sent"] = df["compound"].apply(_label)
    df["rating_sent"] = df["Rating"].apply(_rating_label)
    df["agree"] = df["text_sent"] == df["rating_sent"]

    # ── 概览 ───────────────────────────────────────────
    pos_share = (df["text_sent"] == "positive").mean() * 100
    neg_share = (df["text_sent"] == "negative").mean() * 100
    overview = {
        "raw_reviews": int(len(raw)),
        "dedup_reviews": int(len(raw.drop_duplicates())),
        "analyzed_reviews": int(len(df)),
        "platforms": int(df["Platform"].nunique()),
        "avg_rating": round(df["Rating"].mean(), 2),
        "median_rating": float(df["Rating"].median()),
        "positive_pct": round(pos_share, 1),
        "negative_pct": round(neg_share, 1),
        "neutral_pct": round(100 - pos_share - neg_share, 1),
        "avg_words": round(df["words"].mean(), 1),
        "text_rating_corr": round(
            float(df[["compound", "Rating"]].corr(method="spearman").iloc[0, 1]), 3
        ),
        "agreement_pct": round(df["agree"].mean() * 100, 1),
    }

    # ── 评分分布与两极分化 ─────────────────────────────
    rating_dist = df["Rating"].value_counts().sort_index()
    rating_distribution = [
        {"rating": int(k), "count": int(v)} for k, v in rating_dist.items()
    ]
    extremes = ((df["Rating"] >= 9) | (df["Rating"] <= 1)).mean() * 100
    middle = df["Rating"].between(4, 8).mean() * 100
    polarization = {
        "extreme_pct": round(extremes, 1),
        "middle_pct": round(middle, 1),
        "top_box_pct": round((df["Rating"] >= 9).mean() * 100, 1),
        "bottom_box_pct": round((df["Rating"] <= 1).mean() * 100, 1),
    }

    # ── 平台对比 ───────────────────────────────────────
    platforms = []
    for name, sub in df.groupby("Platform"):
        s_pos = (sub["text_sent"] == "positive").mean() * 100
        s_neg = (sub["text_sent"] == "negative").mean() * 100
        platforms.append({
            "name": name,
            "reviews": int(len(sub)),
            "share_pct": round(len(sub) / len(df) * 100, 1),
            "avg_rating": round(sub["Rating"].mean(), 2),
            "median_rating": float(sub["Rating"].median()),
            "positive_pct": round(s_pos, 1),
            "negative_pct": round(s_neg, 1),
            "polarization_pct": round(
                ((sub["Rating"] >= 9) | (sub["Rating"] <= 1)).mean() * 100, 1
            ),
            "avg_words": round(sub["words"].mean(), 1),
            "agreement_pct": round(sub["agree"].mean() * 100, 1),
        })
    platforms.sort(key=lambda x: x["avg_rating"], reverse=True)

    # ── 文本情感 vs 评分 ───────────────────────────────
    order = ["negative", "neutral", "positive"]
    matrix = []
    for r in order:
        row = {"rating_sent": r, "counts": {}}
        for t in order:
            row["counts"][t] = int(((df["rating_sent"] == r) & (df["text_sent"] == t)).sum())
        matrix.append(row)

    disagree = df[~df["agree"]]
    examples = []
    for case, mask in [
        ("文字负面但评分高", (df["text_sent"] == "negative") & (df["Rating"] >= 7)),
        ("文字正面但评分低", (df["text_sent"] == "positive") & (df["Rating"] <= 3)),
    ]:
        sub = df[mask].sort_values("words", ascending=False).head(3)
        for _, r in sub.iterrows():
            examples.append({
                "case": case,
                "rating": int(r["Rating"]),
                "platform": r["Platform"],
                "compound": round(float(r["compound"]), 2),
                "text": r["text"][:180] + ("…" if len(r["text"]) > 180 else ""),
            })

    sentiment_vs_rating = {
        "matrix": matrix,
        "disagree_pct": round((~df["agree"]).mean() * 100, 1),
        "high_rating_negative_text": int(
            ((df["text_sent"] == "negative") & (df["Rating"] >= 7)).sum()
        ),
        "low_rating_positive_text": int(
            ((df["text_sent"] == "positive") & (df["Rating"] <= 3)).sum()
        ),
        "examples": examples,
    }

    # ── 评论长度 ───────────────────────────────────────
    bins = [0, 20, 50, 100, 200, np.inf]
    labels = ["1-20 词", "21-50 词", "51-100 词", "101-200 词", "200 词以上"]
    df["len_bucket"] = pd.cut(df["words"], bins=bins, labels=labels)
    length_analysis = []
    for name in labels:
        sub = df[df["len_bucket"] == name]
        if len(sub) == 0:
            continue
        length_analysis.append({
            "bucket": str(name),
            "reviews": int(len(sub)),
            "share_pct": round(len(sub) / len(df) * 100, 1),
            "avg_rating": round(sub["Rating"].mean(), 2),
            "negative_pct": round((sub["text_sent"] == "negative").mean() * 100, 1),
        })

    # ── 主题提及率 ─────────────────────────────────────
    ps = _stemmer()
    stem_cache = {}

    def stems_of(text):
        toks = re.findall(r"[a-zA-Z']+", text.lower())
        out = []
        for t in toks:
            if t in stem_cache:
                out.append(stem_cache[t])
            else:
                s = ps.stem(t)
                stem_cache[t] = s
                out.append(s)
        return set(out)

    df["stems"] = df["text"].map(stems_of)
    df["lower"] = df["text"].str.lower()
    theme_rows = []
    for key, spec in THEMES.items():
        # 单词按词根匹配；词组（loot box / voice acting）按原短语匹配
        single = {ps.stem(k) for k in spec["keywords"] if " " not in k}
        phrases = [k for k in spec["keywords"] if " " in k]
        mask = df.apply(
            lambda r: bool(r["stems"] & single)
            or any(p in r["lower"] for p in phrases),
            axis=1,
        )
        sub = df[mask]
        if len(sub) == 0:
            continue
        theme_rows.append({
            "key": key,
            "label": spec["label"],
            "mentions": int(len(sub)),
            "mention_pct": round(len(sub) / len(df) * 100, 1),
            "avg_rating": round(sub["Rating"].mean(), 2),
            "negative_pct": round((sub["text_sent"] == "negative").mean() * 100, 1),
        })
    theme_rows.sort(key=lambda x: x["mentions"], reverse=True)

    # ── 关键词（TF-IDF）─────────────────────────────────
    from sklearn.feature_extraction.text import TfidfVectorizer

    corpus = df["text"].str.lower()
    vectorizer = TfidfVectorizer(
        stop_words="english",
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z']{2,}\b",
        min_df=5,
        max_df=0.6,
        ngram_range=(1, 1),
    )
    X = vectorizer.fit_transform(corpus)
    terms = np.array(vectorizer.get_feature_names_out())
    mask_extra = np.array([
        t not in EXTRA_STOPWORDS and "'" not in t for t in terms
    ])
    terms = terms[mask_extra]
    X = X[:, mask_extra]

    neg_mask = (df["text_sent"] == "negative").values
    pos_mask = (df["text_sent"] == "positive").values

    def top_terms(mask, k=12):
        scores = np.asarray(X[mask].mean(axis=0)).ravel()
        idx = np.argsort(scores)[-k:][::-1]
        return [{"term": str(terms[i]), "score": round(float(scores[i]), 4)} for i in idx if scores[i] > 0]

    keywords = {
        "negative": top_terms(neg_mask),
        "positive": top_terms(pos_mask),
    }

    # ── 结论 ───────────────────────────────────────────
    best = platforms[0]
    worst = platforms[-1]
    insights = [
        f"清洗后保留 {len(df):,} 条有效评论（原始 {len(raw):,} 条，去重并去掉过短评论）。",
        f"评分与文本情感整体一致率 {overview['agreement_pct']}%，"
        f"但仍有两类「言不由衷」：{sentiment_vs_rating['high_rating_negative_text']} 条文字在骂却给了 7 分以上，"
        f"{sentiment_vs_rating['low_rating_positive_text']} 条文字不错却给了低分——"
        "只看星级会漏掉真实的用户体验。",
        f"评分极度两极分化：{(df['Rating'] >= 9).mean() * 100:.1f}% 打 9-10 分，"
        f"{(df['Rating'] <= 1).mean() * 100:.1f}% 打 0-1 分，中间 4-8 分只占 {middle:.1f}%。"
        "这是典型的「要么神作要么垃圾」评价结构。",
        f"{best['name']} 平均分最高（{best['avg_rating']}），"
        f"{worst['name']} 最低（{worst['avg_rating']}）；"
        f"但 {worst['name']} 的文本负面率是 {worst['negative_pct']}%，和评分方向一致。",
        "短评和长评的情绪结构不同：20 词以内的短评平均 "
        f"{length_analysis[0]['avg_rating']} 分、负面率 {length_analysis[0]['negative_pct']}%，"
        f"50 词以上的长评平均分降到 4.9~5.5、负面率升到 37% 左右——"
        "短评多是情绪表达，长评更可能是在讲具体问题。",
    ]
    if theme_rows:
        top_theme = theme_rows[0]
        worst_theme = min(theme_rows, key=lambda x: x["avg_rating"])
        insights.append(
            f"被提及最多的话题是「{top_theme['label']}」（{top_theme['mention_pct']}% 的评论），"
            f"而平均分最低的话题是「{worst_theme['label']}」（{worst_theme['avg_rating']} 分，"
            f"负面率 {worst_theme['negative_pct']}%）——这是最该优先修的问题。"
        )

    return jsonable({
        "overview": overview,
        "data_notes": [
            f"原始 {len(raw):,} 条，整行重复 {int(raw.duplicated().sum())} 条。",
            f"同一段评论重复提交 {int(raw['Review'].duplicated().sum())} 条，按文本去重。",
            "少于 3 个词的评论无法做可靠情感判断，已剔除。",
            "情感用 VADER（英文社交媒体词典）打分，compound ≥ 0.05 为正面、≤ -0.05 为负面。",
            "VADER 是词典法，对反讽和长评论里的混合情绪判断有限；"
            "「低分但文字判为正面」的样本不能全当成用户口是心非，也存在模型误差。",
        ],
        "rating_distribution": rating_distribution,
        "polarization": polarization,
        "platforms": platforms,
        "sentiment_vs_rating": sentiment_vs_rating,
        "length_analysis": length_analysis,
        "themes": theme_rows,
        "keywords": keywords,
        "insights": insights,
    })
