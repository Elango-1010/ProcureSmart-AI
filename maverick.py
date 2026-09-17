"""AI Use Case 1: Maverick Spend Detection (Deliverable D-06).

Combines an Isolation Forest anomaly model with rule-based policy validation,
per the approved proposal. Every flagged transaction gets a risk band and a
human-readable explanation - not just a raw anomaly score.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OneHotEncoder

from ..config import ISOLATION_FOREST_PARAMS, MAVERICK_RULES, RISK_BANDS
from ..etl.load import read_table


def _build_features(spend: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    df = spend.copy()
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["off_contract_flag"] = (df["contract_status"] != "ON_CONTRACT").astype(int)

    dept_median = df.groupby("department")["amount"].transform("median")
    df["amount_vs_dept_median"] = df["amount"] / dept_median.replace(0, np.nan)
    df["amount_vs_dept_median"] = df["amount_vs_dept_median"].fillna(1.0)

    cat_median = df.groupby("category")["amount"].transform("median")
    df["amount_vs_cat_median"] = df["amount"] / cat_median.replace(0, np.nan)
    df["amount_vs_cat_median"] = df["amount_vs_cat_median"].fillna(1.0)

    numeric = df[["amount", "off_contract_flag", "amount_vs_dept_median", "amount_vs_cat_median"]].to_numpy()
    return numeric, df


def _rule_based_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Policy rules that run independently of the ML model - per approved proposal."""
    out = df.copy()
    out["rule_off_contract"] = out["contract_status"] != "ON_CONTRACT"
    out["rule_above_approval_threshold"] = out["amount"] > MAVERICK_RULES["requisition_approval_threshold"]
    out["rule_single_txn_alert"] = out["amount"] > MAVERICK_RULES["single_txn_alert_threshold"]
    out["rule_dept_variance"] = out["amount_vs_dept_median"] > MAVERICK_RULES["department_variance_multiplier"]
    out["rule_hits"] = out[[
        "rule_off_contract", "rule_above_approval_threshold",
        "rule_single_txn_alert", "rule_dept_variance",
    ]].sum(axis=1)
    return out


def _risk_band(score: float) -> str:
    for threshold, band in RISK_BANDS:
        if score >= threshold:
            return band
    return "LOW"


def _explain(row: pd.Series) -> str:
    reasons = []
    if row["rule_off_contract"]:
        reasons.append("purchase made outside an approved supplier contract")
    if row["rule_single_txn_alert"]:
        reasons.append(f"transaction value (Rs {row['amount']:,.0f}) exceeds the single-transaction alert threshold")
    elif row["rule_above_approval_threshold"]:
        reasons.append(f"transaction value (Rs {row['amount']:,.0f}) exceeds the standard approval threshold")
    if row["rule_dept_variance"]:
        reasons.append(f"spend is {row['amount_vs_dept_median']:.1f}x the {row['department']} department's median transaction")
    if not reasons:
        reasons.append("flagged by anomaly model on multivariate spend pattern, no single policy rule triggered")
    return "; ".join(reasons).capitalize() + "."


def detect_maverick_spend(engine=None, top_n: int | None = None) -> pd.DataFrame:
    """Run Isolation Forest + rule validation and return risk-scored flagged transactions."""
    spend = read_table("spend_transactions", engine)
    features, df = _build_features(spend)

    model = IsolationForest(**ISOLATION_FOREST_PARAMS)
    model.fit(features)
    raw_scores = -model.score_samples(features)  # higher = more anomalous
    normalised = (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-9)

    df["ml_anomaly_score"] = normalised
    df["ml_flagged"] = model.predict(features) == -1
    df = _rule_based_flags(df)

    # Combined risk score: blend of ML anomaly score and rule hit density
    df["risk_score"] = round(0.6 * df["ml_anomaly_score"] + 0.4 * (df["rule_hits"] / 4), 4)
    df["risk_band"] = df["risk_score"].map(_risk_band)
    df["is_flagged"] = df["ml_flagged"] | (df["rule_hits"] >= 2)
    df["explanation"] = df.apply(_explain, axis=1)

    flagged = df[df["is_flagged"]].sort_values("risk_score", ascending=False)
    cols = [
        "transaction_id", "supplier_name", "department", "category", "amount",
        "contract_status", "risk_score", "risk_band", "rule_hits", "explanation",
        "transaction_date",
    ]
    result = flagged[cols].reset_index(drop=True)
    return result.head(top_n) if top_n else result


def model_validation_metrics(engine=None) -> dict:
    """Sanity metrics for the QA layer: flag rate, risk-band distribution, rule/ML agreement."""
    spend = read_table("spend_transactions", engine)
    features, df = _build_features(spend)
    model = IsolationForest(**ISOLATION_FOREST_PARAMS)
    model.fit(features)
    raw_scores = -model.score_samples(features)
    normalised = (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-9)
    df["ml_flagged"] = model.predict(features) == -1
    df = _rule_based_flags(df)

    both = int((df["ml_flagged"] & (df["rule_hits"] >= 1)).sum())
    ml_only = int((df["ml_flagged"] & (df["rule_hits"] == 0)).sum())
    rule_only = int((~df["ml_flagged"] & (df["rule_hits"] >= 2)).sum())

    return {
        "total_transactions": int(len(df)),
        "ml_flagged_count": int(df["ml_flagged"].sum()),
        "ml_flagged_pct": round(100 * df["ml_flagged"].mean(), 2),
        "rule_flagged_count": int((df["rule_hits"] >= 2).sum()),
        "flagged_by_both": both,
        "ml_only_flags": ml_only,
        "rule_only_flags": rule_only,
        "seeded_high_value_maverick_txns_recovered": int(
            df.loc[df["amount"] > 320_000, "ml_flagged"].sum()
        ),
    }
