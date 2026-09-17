"""ProcureSmart AI - FastAPI backend (Deliverable D-10).

Run with: uvicorn src.api.main:app --reload
Docs at:  http://localhost:8000/docs
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..analytics import budget as budget_analytics
from ..analytics import spend as spend_analytics
from ..analytics import supplier as supplier_analytics
from ..ai import consolidation, maverick, narrative, savings
from ..etl.load import query, read_table
from ..governance.catalogue import GovernanceCatalogue
from ..schema import get_engine

app = FastAPI(
    title="ProcureSmart AI API",
    description="Smart Procurement Management Platform - S4-I-22",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ENGINE = get_engine()


def _clean_records(df: pd.DataFrame) -> list[dict]:
    """Convert NaN/NaT to None and numpy scalars to native Python types."""
    safe = df.astype(object).where(pd.notnull(df), None)
    records = safe.to_dict("records")
    return [{k: _to_native(v) for k, v in row.items()} for row in records]


def _to_native(value):
    if isinstance(value, (bool,)):
        return value
    if hasattr(value, "item"):  # numpy scalar types (bool_, int64, float64, ...)
        return value.item()
    return value


def _clean_record(series: pd.Series) -> dict:
    return {k: _to_native(None if pd.isna(v) else v) for k, v in series.to_dict().items()}


# ---------------------------------------------------------------- schemas --

class RequisitionCreate(BaseModel):
    requester: str
    department: str
    category: str
    requested_supplier_id: Optional[str] = None
    estimated_amount: float
    justification: str


class RequisitionDecision(BaseModel):
    approver: str
    decision: str  # APPROVED / REJECTED
    remarks: Optional[str] = None


# ------------------------------------------------------------------ health --

@app.get("/health")
def health():
    return {"status": "ok", "service": "procuresmart-ai", "time": datetime.utcnow().isoformat()}


# --------------------------------------------------------------- analytics --

@app.get("/api/analytics/spend")
def get_spend_summary():
    return spend_analytics.spend_summary(ENGINE)


@app.get("/api/analytics/suppliers")
def get_supplier_analytics():
    return supplier_analytics.supplier_analytics_summary(ENGINE)


@app.get("/api/analytics/kpis")
def get_kpis():
    return budget_analytics.procurement_kpis(ENGINE)


@app.get("/api/analytics/budget-utilisation")
def get_budget_utilisation():
    return _clean_records(budget_analytics.budget_utilisation(ENGINE))


# --------------------------------------------------------------------- AI --

@app.get("/api/ai/maverick-spend")
def get_maverick_spend(top_n: int = 25):
    return maverick.detect_maverick_spend(ENGINE, top_n=top_n).to_dict("records")


@app.get("/api/ai/maverick-spend/validation")
def get_maverick_validation():
    return maverick.model_validation_metrics(ENGINE)


@app.get("/api/ai/consolidation")
def get_consolidation():
    return consolidation.consolidation_opportunities(ENGINE).to_dict("records")


@app.get("/api/ai/savings")
def get_savings():
    result = savings.savings_summary(ENGINE)
    return {
        "contract_renewal_alerts": _clean_records(pd.DataFrame(result["contract_renewal_alerts"])),
        "volume_milestone_opportunities": _clean_records(pd.DataFrame(result["volume_milestone_opportunities"])),
        "renewal_alert_count": result["renewal_alert_count"],
        "milestone_opportunity_count": result["milestone_opportunity_count"],
    }


@app.get("/api/ai/narrative")
def get_narrative(force_fallback: bool = False):
    return narrative.generate_narrative(ENGINE, force_fallback=force_fallback)


# ----------------------------------------------------------- requisitions --

@app.get("/api/requisitions")
def list_requisitions(status: Optional[str] = None):
    df = read_table("requisitions", ENGINE)
    if status:
        df = df[df["status"] == status.upper()]
    return _clean_records(df.sort_values("requisition_id"))


@app.get("/api/requisitions/{requisition_id}")
def get_requisition(requisition_id: str):
    df = read_table("requisitions", ENGINE)
    row = df[df["requisition_id"] == requisition_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Requisition not found")
    return _clean_record(row.iloc[0])


@app.get("/api/requisitions/{requisition_id}/validate")
def validate_requisition(requisition_id: str):
    """Intelligent validation: preferred supplier check, budget check, duplicate check."""
    reqs = read_table("requisitions", ENGINE)
    row = reqs[reqs["requisition_id"] == requisition_id]
    if row.empty:
        raise HTTPException(status_code=404, detail="Requisition not found")
    req = row.iloc[0]

    suppliers = read_table("suppliers", ENGINE)
    category_suppliers = suppliers[suppliers["category"] == req["category"]]
    preferred = category_suppliers[category_suppliers["is_preferred"].astype(bool)]

    requested_is_preferred = bool(
        req["requested_supplier_id"] in preferred["supplier_id"].values
    )

    util = budget_analytics.budget_utilisation(ENGINE)
    dept_budget = util[util["department"] == req["department"]]
    budget_ok = True
    budget_note = "No budget record found for this department."
    if not dept_budget.empty:
        remaining = float(dept_budget.iloc[0]["remaining_budget"])
        budget_ok = remaining >= req["estimated_amount"]
        budget_note = f"Remaining department budget: Rs {remaining:,.0f}"

    similar = reqs[
        (reqs["department"] == req["department"])
        & (reqs["category"] == req["category"])
        & (reqs["requisition_id"] != requisition_id)
    ]

    alternate_suppliers = category_suppliers[
        category_suppliers["supplier_id"] != req["requested_supplier_id"]
    ]["supplier_name"].tolist()

    return {
        "requisition_id": requisition_id,
        "requested_supplier_is_preferred": bool(requested_is_preferred),
        "preferred_supplier_alternative": (
            None if requested_is_preferred or preferred.empty
            else preferred.iloc[0]["supplier_name"]
        ),
        "budget_check_passed": bool(budget_ok),
        "budget_note": budget_note,
        "similar_previous_requisitions": int(len(similar)),
        "alternative_suppliers": alternate_suppliers[:5],
        "recommendation": (
            "Approve - within policy" if requested_is_preferred and budget_ok
            else "Flag for review - " + (
                "non-preferred supplier" if not requested_is_preferred else "budget constraint"
            )
        ),
    }


@app.post("/api/requisitions")
def create_requisition(req: RequisitionCreate):
    reqs = read_table("requisitions", ENGINE)
    next_num = len(reqs) + 1
    new_id = f"REQ{next_num:05d}"
    new_row = pd.DataFrame([{
        "requisition_id": new_id,
        "requester": req.requester,
        "department": req.department,
        "category": req.category,
        "requested_supplier_id": req.requested_supplier_id,
        "estimated_amount": req.estimated_amount,
        "justification": req.justification,
        "status": "PENDING",
        "approver": None,
        "decided_at": None,
    }])
    new_row.to_sql("requisitions", ENGINE, if_exists="append", index=False)
    return {"requisition_id": new_id, "status": "PENDING"}


@app.post("/api/requisitions/{requisition_id}/decide")
def decide_requisition(requisition_id: str, decision: RequisitionDecision):
    if decision.decision.upper() not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="decision must be APPROVED or REJECTED")
    with ENGINE.begin() as conn:
        result = conn.exec_driver_sql(
            "UPDATE requisitions SET status = ?, approver = ?, decided_at = ? "
            "WHERE requisition_id = ?",
            (decision.decision.upper(), decision.approver, datetime.utcnow().isoformat(), requisition_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Requisition not found")
    return {"requisition_id": requisition_id, "status": decision.decision.upper()}


# ------------------------------------------------------------------- governance --

@app.get("/api/governance/catalogue")
def get_catalogue():
    df = query("SELECT * FROM data_assets", ENGINE)
    return _clean_records(df)


@app.get("/api/governance/audit-log")
def get_audit_log(limit: int = 50):
    df = query(f"SELECT * FROM audit_log ORDER BY created_at DESC LIMIT {int(limit)}", ENGINE)
    return _clean_records(df)
