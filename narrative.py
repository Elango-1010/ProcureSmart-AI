"""AI Use Case 4: Intelligent Procurement Summary Generation (Deliverable D-09).

Uses the OpenAI API when a key is configured; falls back to a template-based
narrative generator otherwise, so the demo is never dependent on network/API
availability (Risk #17 in the approved proposal's risk register).
"""
from __future__ import annotations

from ..analytics import budget as budget_analytics
from ..analytics import spend as spend_analytics
from ..config import LLM_ENABLED, OPENAI_API_KEY, OPENAI_MODEL
from .maverick import detect_maverick_spend


def _rule_based_narrative(context: dict) -> str:
    """Deterministic narrative - always available, no external dependency."""
    s = context["spend"]
    k = context["kpis"]
    top_cat = s["by_category"][0] if s["by_category"] else None
    top_dept = s["by_department"][0] if s["by_department"] else None

    lines = []
    lines.append(
        f"Total tracked procurement spend stands at Rs {s['total_spend']:,.0f} across "
        f"{s['transaction_count']:,} transactions."
    )
    if top_cat:
        lines.append(
            f"{top_cat['category']} is the largest spend category at Rs {top_cat['total_spend']:,.0f} "
            f"({top_cat['pct_of_total']}% of total spend)."
        )
    if top_dept:
        lines.append(
            f"{top_dept['department']} is the highest-spending department "
            f"(Rs {top_dept['total_spend']:,.0f}, {top_dept['pct_of_total']}% of total)."
        )
    lines.append(
        f"Off-contract spend is currently {s['off_contract_spend_pct']}% of total spend - "
        f"{'within' if s['off_contract_spend_pct'] < 20 else 'above'} the acceptable range."
    )
    lines.append(
        f"{context['maverick_count']} transactions have been flagged as maverick spend by the "
        "anomaly detection engine and warrant procurement review."
    )
    lines.append(
        f"Requisition approval rate is {k['requisition_approval_rate_pct']}% with "
        f"{k['pending_requisitions']} requisitions currently pending action."
    )
    return " ".join(lines)


def _call_llm(context: dict) -> str:
    """Call the configured LLM to produce a fluent narrative from the same context."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        "You are a procurement intelligence assistant. Write a concise, business-facing "
        "3-4 sentence weekly procurement summary from this data. Be specific with figures, "
        "and highlight risk (maverick spend, off-contract %) alongside spend trends.\n\n"
        f"Data: {context}"
    )
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


def generate_narrative(engine=None, force_fallback: bool = False) -> dict:
    """Generate a procurement intelligence narrative, LLM-backed with rule-based fallback."""
    s = spend_analytics.spend_summary(engine)
    k = budget_analytics.procurement_kpis(engine)
    maverick_count = len(detect_maverick_spend(engine))

    context = {"spend": s, "kpis": k, "maverick_count": maverick_count}

    if LLM_ENABLED and not force_fallback:
        try:
            narrative = _call_llm(context)
            return {"narrative": narrative, "source": "llm", "model": OPENAI_MODEL}
        except Exception as exc:  # noqa: BLE001 - deliberate: any API failure falls back
            fallback = _rule_based_narrative(context)
            return {
                "narrative": fallback,
                "source": "rule_based_fallback",
                "fallback_reason": str(exc),
            }

    return {"narrative": _rule_based_narrative(context), "source": "rule_based"}
