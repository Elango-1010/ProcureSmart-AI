import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const inr = (n) =>
  "\u20b9" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

export default function Dashboard() {
  const [kpis, setKpis] = useState(null);
  const [spend, setSpend] = useState(null);
  const [maverick, setMaverick] = useState([]);
  const [narrative, setNarrative] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      api.kpis(),
      api.spendSummary(),
      api.maverickSpend(6),
      api.narrative(),
    ])
      .then(([k, s, m, n]) => {
        setKpis(k);
        setSpend(s);
        setMaverick(m);
        setNarrative(n);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="empty">
        Could not reach the API at /api — is the FastAPI server running on
        port 8000?
        <br />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{error}</span>
      </div>
    );
  }

  if (!kpis || !spend) return <div className="loading">LOADING SPEND DATA…</div>;

  return (
    <>
      <div className="kpi-row">
        <div className="kpi">
          <div className="kpi-label">Total tracked spend</div>
          <div className="kpi-value">{inr(kpis.total_spend)}</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Off-contract spend</div>
          <div className={`kpi-value ${kpis.off_contract_spend_pct > 20 ? "alert" : ""}`}>
            {kpis.off_contract_spend_pct}%
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Requisition approval rate</div>
          <div className="kpi-value signal">{kpis.requisition_approval_rate_pct}%</div>
        </div>
        <div className="kpi">
          <div className="kpi-label">Pending requisitions</div>
          <div className="kpi-value">{kpis.pending_requisitions}</div>
        </div>
      </div>

      {narrative && (
        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Procurement intelligence summary</span>
            <span className="panel-note">
              source: {narrative.source === "llm" ? "Azure OpenAI" : "rule-based fallback"}
            </span>
          </div>
          <div className="narrative-block">{narrative.narrative}</div>
        </div>
      )}

      <div className="two-col">
        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Spend by category</span>
            <span className="panel-note">{spend.by_category.length} categories</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th className="num">Spend</th>
                <th className="num">% of total</th>
              </tr>
            </thead>
            <tbody>
              {spend.by_category.slice(0, 6).map((row) => (
                <tr key={row.category}>
                  <td>{row.category}</td>
                  <td className="num">{inr(row.total_spend)}</td>
                  <td className="num">{row.pct_of_total}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Top flagged transactions</span>
            <span className="panel-note">maverick spend</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Supplier</th>
                <th className="num">Amount</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {maverick.map((row) => (
                <tr key={row.transaction_id}>
                  <td>{row.supplier_name}</td>
                  <td className="num">{inr(row.amount)}</td>
                  <td>
                    <span className={`badge ${row.risk_band.toLowerCase()}`}>
                      {row.risk_band}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
