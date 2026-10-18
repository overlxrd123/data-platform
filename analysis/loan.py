"""贷款违约预测 — 模型评估口径。

旧版只有两件事：两个模型的 AUC 柱子 + 特征重要性。
新版补齐一个风控模型真正该看的指标：
  ROC / PR 曲线、KS、混淆矩阵、阈值决策、概率校准、交叉验证稳定性、
  以及「通过率 vs 坏账率 vs 期望收益」的业务权衡。

数据为模拟信贷样本（5,000 条），违约标签由已知的非线性风险函数生成，
所以可以验证模型是否学到了真实结构，而不是在噪声上过拟合。
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from .data import jsonable

N = 5000
# 业务假设：放对一笔赚 2,000，放错一笔亏 10,000（坏账损失约为收益的 5 倍）
PROFIT_GOOD = 2000
LOSS_BAD = 10000


def _generate():
    # 固定随机数流，保证与旧页面 / README 中披露的指标可复现
    rs = np.random.RandomState(42)
    X = pd.DataFrame({
        "credit_score": np.clip(rs.normal(650, 80, N).astype(int), 300, 850),
        "debt_ratio": rs.uniform(0, .7, N).round(2),
        "income": np.clip(rs.lognormal(8.8, .5, N).astype(int), 30000, 2000000),
        "has_house": rs.choice([0, 1], N, p=[.5, .5]),
        "has_car": rs.choice([0, 1], N, p=[.4, .6]),
        "age": np.clip(rs.normal(38, 10, N).astype(int), 22, 65),
        "emp_years": np.clip(rs.exponential(5, N).astype(int), 0, 40),
    })
    risk = (
        -1.5
        + 3.0 * ((X["debt_ratio"] > 0.5) & (X["credit_score"] < 600)).astype(int)
        + 2.5 * ((X["debt_ratio"] > 0.35) & (X["income"] < 90000)).astype(int)
        + 1.5 * ((X["has_house"] == 0) & (X["has_car"] == 0) & (X["debt_ratio"] > 0.3)).astype(int)
        - 0.01 * X["credit_score"] / 10
        - 0.2 * X["has_house"]
        - 0.15 * X["has_car"]
    )
    log_odds = risk + rs.normal(0, 1.2, N)
    pd_true = 1 / (1 + np.exp(-log_odds))
    y = (pd_true > np.percentile(pd_true, 85)).astype(int)
    return X, y


def _downsample(x, y, n=60):
    if len(x) <= n:
        return x, y
    idx = np.linspace(0, len(x) - 1, n).astype(int)
    return x[idx], y[idx]


@lru_cache(maxsize=1)
def get_loan_analysis() -> dict:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score, confusion_matrix, f1_score, precision_recall_curve,
        precision_score, recall_score, roc_auc_score, roc_curve,
    )
    from sklearn.model_selection import StratifiedKFold, train_test_split

    X, y = _generate()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=.2, random_state=42
    )
    rf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    rf.fit(X_train, y_train)
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X_train, y_train)

    p_rf = rf.predict_proba(X_test)[:, 1]
    p_lr = lr.predict_proba(X_test)[:, 1]
    auc_rf = roc_auc_score(y_test, p_rf)
    auc_lr = roc_auc_score(y_test, p_lr)

    # ── ROC / PR 曲线 ──────────────────────────────────
    fpr, tpr, _ = roc_curve(y_test, p_rf)
    fpr_d, tpr_d = _downsample(fpr, tpr)
    roc = [{"fpr": round(float(a), 3), "tpr": round(float(b), 3)}
           for a, b in zip(fpr_d, tpr_d)]
    ks = float(np.max(tpr - fpr))

    prec, rec, _ = precision_recall_curve(y_test, p_rf)
    prec_d, rec_d = _downsample(rec, prec)
    pr = [{"recall": round(float(a), 3), "precision": round(float(b), 3)}
          for a, b in zip(rec_d, prec_d)]
    # PR-AUC（用梯形积分近似）
    order = np.argsort(rec)
    pr_auc = float(np.trapz(prec[order], rec[order]))

    # ── 0.5 阈值下的分类表现 ───────────────────────────
    pred = (p_rf >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, pred).ravel()
    metrics = {
        "auc_rf": round(float(auc_rf), 4),
        "auc_lr": round(float(auc_lr), 4),
        "auc_gap": round(float(auc_rf - auc_lr), 4),
        "ks": round(ks, 4),
        "pr_auc": round(pr_auc, 4),
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "precision": round(float(precision_score(y_test, pred)), 4),
        "recall": round(float(recall_score(y_test, pred)), 4),
        "f1": round(float(f1_score(y_test, pred)), 4),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "test_size": int(len(y_test)),
        "default_rate_true": round(float(y.mean()) * 100, 1),
        "default_rate_pred": round(float(pred.mean()) * 100, 1),
    }

    # ── 阈值决策：通过率 / 坏账率 / 违约召回 / 期望收益 ──
    thresholds = []
    for t in np.arange(0.05, 0.96, 0.05):
        approved = p_rf < t
        n_app = int(approved.sum())
        if n_app == 0:
            continue
        bad = int(((y_test == 1) & approved).sum())
        good = int(((y_test == 0) & approved).sum())
        profit = good * PROFIT_GOOD - bad * LOSS_BAD
        thresholds.append({
            "threshold": round(float(t), 2),
            "approval_pct": round(n_app / len(y_test) * 100, 1),
            "bad_rate_pct": round(bad / n_app * 100, 1),
            "default_recall_pct": round(
                ((y_test == 1) & ~approved).sum() / max(1, int((y_test == 1).sum())) * 100, 1
            ),
            "expected_profit": int(profit),
            "profit_per_applicant": int(round(profit / n_app)),
        })
    best_t = max(thresholds, key=lambda x: x["expected_profit"]) if thresholds else None

    # ── 概率校准（十分位）──────────────────────────────
    calib = pd.DataFrame({"p": p_rf, "y": y_test})
    calib["bin"] = pd.qcut(calib["p"], 10, labels=False, duplicates="drop")
    calibration = []
    for b, sub in calib.groupby("bin"):
        calibration.append({
            "bin": int(b) + 1,
            "predicted_pct": round(float(sub["p"].mean()) * 100, 1),
            "actual_pct": round(float(sub["y"].mean()) * 100, 1),
            "count": int(len(sub)),
        })

    # ── 特征重要性 + 置换重要性 ─────────────────────────
    imp = pd.DataFrame({
        "feature": X.columns,
        "impurity": rf.feature_importances_,
    }).sort_values("impurity", ascending=False)
    perm = permutation_importance(
        rf, X_test, y_test, n_repeats=10, random_state=42, scoring="roc_auc"
    )
    perm_map = dict(zip(X.columns, perm.importances_mean))
    feature_importance = [
        {
            "feature": r["feature"],
            "impurity": round(float(r["impurity"]), 4),
            "permutation_auc_drop": round(float(perm_map.get(r["feature"], 0)), 4),
        }
        for _, r in imp.iterrows()
    ]

    # ── 5 折交叉验证 ───────────────────────────────────
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = []
    for tr, te in cv.split(X, y):
        m = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
        m.fit(X.iloc[tr], y.iloc[tr])
        cv_scores.append(roc_auc_score(y.iloc[te], m.predict_proba(X.iloc[te])[:, 1]))
    cv_scores = np.array(cv_scores)

    # ── 分群违约率 ─────────────────────────────────────
    df = X.copy()
    df["y"] = y.values
    df["credit_band"] = pd.cut(
        df["credit_score"], [299, 579, 669, 739, 799, 850],
        labels=["300-579", "580-669", "670-739", "740-799", "800-850"],
    )
    df["debt_band"] = pd.cut(
        df["debt_ratio"], [-0.01, 0.2, 0.35, 0.5, 1.0],
        labels=["<20%", "20-35%", "35-50%", ">50%"],
    )
    segment_credit = [
        {"band": str(name), "count": int(len(sub)),
         "default_pct": round(float(sub["y"].mean()) * 100, 1)}
        for name, sub in df.groupby("credit_band", observed=True)
    ]
    segment_debt = [
        {"band": str(name), "count": int(len(sub)),
         "default_pct": round(float(sub["y"].mean()) * 100, 1)}
        for name, sub in df.groupby("debt_band", observed=True)
    ]

    overview = {
        "samples": N,
        "features": int(X.shape[1]),
        "default_rate": metrics["default_rate_true"],
        "auc_rf": metrics["auc_rf"],
        "auc_lr": metrics["auc_lr"],
        "ks": metrics["ks"],
        "cv_mean": round(float(cv_scores.mean()), 4),
        "cv_std": round(float(cv_scores.std()), 4),
        "best_threshold": best_t["threshold"] if best_t else None,
        "best_approval_pct": best_t["approval_pct"] if best_t else None,
        "best_bad_rate_pct": best_t["bad_rate_pct"] if best_t else None,
    }

    top_feat = feature_importance[0]
    worst_seg = max(segment_credit, key=lambda x: x["default_pct"])
    insights = [
        f"随机森林 AUC {metrics['auc_rf']:.3f}，逻辑回归 {metrics['auc_lr']:.3f}，"
        f"差距 {(auc_rf - auc_lr) * 100:.1f} 个百分点——"
        "违约风险主要由「高负债 × 低信用」「高负债 × 低收入」这类非线性交互驱动，"
        "树模型能捕捉，线性模型不能。",
        f"5 折交叉验证 AUC {cv_scores.mean():.3f} ± {cv_scores.std():.3f}，"
        "模型稳定性可以，不是某一次切分碰运气。",
        f"KS = {ks:.3f}，PR-AUC = {pr_auc:.3f}；"
        f"0.5 阈值下召回 {metrics['recall'] * 100:.0f}%、精确率 {metrics['precision'] * 100:.0f}%——"
        "风控更关心「坏客户有没有被拦住」，所以阈值不该默认取 0.5。",
        f"按「好客户赚 {PROFIT_GOOD:,}、坏客户亏 {LOSS_BAD:,}」的假设，"
        f"最优阈值约 {best_t['threshold']}，通过率 {best_t['approval_pct']}%，"
        f"通过客户坏账率 {best_t['bad_rate_pct']}%——"
        "阈值本质是通过率与坏账率的业务交换，应由成本和收益决定，不是模型决定。",
        f"最强预测因子是「{top_feat['feature']}」；"
        f"信用分最低的一档（{worst_seg['band']}）违约率 {worst_seg['default_pct']}%，"
        "风险分层非常清晰。",
        f"概率校准：最高风险十分位的预测违约率 {calibration[-1]['predicted_pct']}%、"
        f"实际 {calibration[-1]['actual_pct']}%——排序能力好，但绝对概率偏低。"
        "如果要把预测值当 PD 用于定价或拨备，需要再做 Platt / Isotonic 校准。",
    ]

    return jsonable({
        "overview": overview,
        "data_notes": [
            "数据为 5,000 条模拟信贷样本，违约标签由已知的非线性风险函数生成。",
            "训练/测试按 8:2 切分；随机森林 100 棵树、最大深度 6。",
            f"期望收益假设：好客户收益 {PROFIT_GOOD:,} 元，坏客户损失 {LOSS_BAD:,} 元。",
            "特征重要性同时给出不纯度重要性和测试集置换重要性，后者更能反映真实预测贡献。",
        ],
        "metrics": metrics,
        "roc": roc,
        "pr": pr,
        "thresholds": thresholds,
        "calibration": calibration,
        "feature_importance": feature_importance,
        "cv_scores": [round(float(s), 4) for s in cv_scores],
        "segments": {
            "credit": segment_credit,
            "debt": segment_debt,
        },
        "insights": insights,
    })
