import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const inr = (n) =>
  "\u20b9" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

export default function Approvals() {
  const [items, setItems] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [validation, setValidation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function refresh() {
    api.requisitions("PENDING").then(setItems).catch((e) => setError(e.message));
  }

  useEffect(refresh, []);

  async function toggleExpand(id) {
    if (expanded === id) {
      setExpanded(null);
      setValidation(null);
      return;
    }
    setExpanded(id);
    setValidation(await api.validateRequisition(id));
  }

  async function decide(id, decision) {
    setBusy(true);
    try {
      await api.decideRequisition(id, { approver: "L&D Reviewer", decision });
      setExpanded(null);
      refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!items) return <div className="loading">LOADING REQUISITIONS…</div>;

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">Approval queue</span>
        <span className="panel-note">{items.length} pending</span>
      </div>

      {error && <div className="feedback err">{error}</div>}

      {items.length === 0 ? (
        <div className="empty">No pending requisitions right now.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Requester</th>
              <th>Department</th>
              <th>Category</th>
              <th className="num">Amount</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <React.Fragment key={r.requisition_id}>
                <tr>
                  <td className="id">{r.requisition_id}</td>
                  <td>{r.requester}</td>
                  <td>{r.department}</td>
                  <td>{r.category}</td>
                  <td className="num">{inr(r.estimated_amount)}</td>
                  <td className="num">
                    <button className="ghost" onClick={() => toggleExpand(r.requisition_id)}>
                      {expanded === r.requisition_id ? "Hide" : "Review"}
                    </button>
                  </td>
                </tr>
                {expanded === r.requisition_id && validation && (
                  <tr>
                    <td colSpan={6} style={{ background: "var(--paper)" }}>
                      <div style={{ padding: "12px 4px" }}>
                        <div style={{ marginBottom: 8, fontSize: 13 }}>
                          Preferred supplier used:{" "}
                          <strong>
                            {validation.requested_supplier_is_preferred ? "Yes" : "No"}
                          </strong>
                          {validation.preferred_supplier_alternative && (
                            <> — suggest <strong>{validation.preferred_supplier_alternative}</strong></>
                          )}
                          <br />
                          Budget check:{" "}
                          <strong>
                            {validation.budget_check_passed ? "Passed" : "Review needed"}
                          </strong>{" "}
                          ({validation.budget_note})
                          <br />
                          System recommendation: <strong>{validation.recommendation}</strong>
                        </div>
                        <div style={{ display: "flex", gap: 8 }}>
                          <button
                            className="ghost approve"
                            disabled={busy}
                            onClick={() => decide(r.requisition_id, "APPROVED")}
                          >
                            Approve
                          </button>
                          <button
                            className="ghost reject"
                            disabled={busy}
                            onClick={() => decide(r.requisition_id, "REJECTED")}
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
