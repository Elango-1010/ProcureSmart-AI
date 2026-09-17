import React, { useEffect, useState } from "react";
import { api } from "../api.js";

const inr = (n) =>
  "\u20b9" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

export default function Governance() {
  const [catalogue, setCatalogue] = useState(null);
  const [consolidation, setConsolidation] = useState(null);
  const [savings, setSavings] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.catalogue(), api.consolidation(), api.savings()])
      .then(([c, co, sv]) => {
        setCatalogue(c);
        setConsolidation(co);
        setSavings(sv);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="empty">{error}</div>;
  if (!catalogue) return <div className="loading">LOADING GOVERNANCE CATALOGUE…</div>;

  return (
    <>
      <div className="panel">
        <div className="panel-head">
          <span className="panel-title">Data asset catalogue</span>
          <span className="panel-note">{catalogue.length} registered assets</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Asset</th>
              <th>Type</th>
              <th className="num">Rows</th>
              <th>Upstream lineage</th>
            </tr>
          </thead>
          <tbody>
            {catalogue.map((a) => (
              <tr key={a.asset_id}>
                <td>{a.asset_name}</td>
                <td>{a.asset_type}</td>
                <td className="num">{a.row_count}</td>
                <td>
                  {a.upstream_assets
                    ? a.upstream_assets.split(",").map((u) => (
                        <span className="lineage-chip" key={u}>{u}</span>
                      ))
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="two-col">
        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Supplier consolidation opportunities</span>
            <span className="panel-note">{consolidation?.length || 0} found</span>
          </div>
          {consolidation && consolidation.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th className="num">Suppliers</th>
                  <th className="num">Est. savings</th>
                </tr>
              </thead>
              <tbody>
                {consolidation.slice(0, 8).map((c) => (
                  <tr key={c.category}>
                    <td>{c.category}</td>
                    <td className="num">{c.supplier_count}</td>
                    <td className="num">{inr(c.estimated_savings)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">No consolidation opportunities found.</div>
          )}
        </div>

        <div className="panel">
          <div className="panel-head">
            <span className="panel-title">Contract renewal alerts</span>
            <span className="panel-note">{savings?.renewal_alert_count || 0} due</span>
          </div>
          {savings && savings.contract_renewal_alerts.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Contract</th>
                  <th className="num">Days left</th>
                  <th>Priority</th>
                </tr>
              </thead>
              <tbody>
                {savings.contract_renewal_alerts.map((c) => (
                  <tr key={c.contract_id}>
                    <td className="id">{c.contract_id}</td>
                    <td className="num">{c.days_to_expiry}</td>
                    <td>
                      <span className={`badge ${c.priority.toLowerCase()}`}>{c.priority}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty">No contracts due for renewal soon.</div>
          )}
        </div>
      </div>
    </>
  );
}
