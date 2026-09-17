import React, { useState } from "react";
import { api } from "../api.js";

const CATEGORIES = [
  "IT Hardware", "IT Software & Licences", "Office Supplies",
  "Professional Services", "Travel", "Facilities Maintenance",
  "Marketing Services", "Logistics & Freight",
];

const DEPARTMENTS = [
  "IT", "Facilities", "Marketing", "Operations",
  "Human Resources", "Finance", "R&D", "Logistics",
];

export default function SubmitRequisition() {
  const [form, setForm] = useState({
    requester: "",
    department: DEPARTMENTS[0],
    category: CATEGORIES[0],
    requested_supplier_id: "",
    estimated_amount: "",
    justification: "",
  });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (key) => (e) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const payload = {
        ...form,
        estimated_amount: Number(form.estimated_amount),
        requested_supplier_id: form.requested_supplier_id || null,
      };
      const created = await api.createRequisition(payload);
      const validation = await api.validateRequisition(created.requisition_id);
      setResult({ created, validation });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">New requisition</span>
        <span className="panel-note">validated automatically on submit</span>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="field">
            <label>Requester name</label>
            <input required value={form.requester} onChange={update("requester")} />
          </div>
          <div className="field">
            <label>Department</label>
            <select value={form.department} onChange={update("department")}>
              {DEPARTMENTS.map((d) => <option key={d}>{d}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Category</label>
            <select value={form.category} onChange={update("category")}>
              {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Requested supplier ID (optional)</label>
            <input
              placeholder="e.g. SUP0001"
              value={form.requested_supplier_id}
              onChange={update("requested_supplier_id")}
            />
          </div>
          <div className="field">
            <label>Estimated amount (₹)</label>
            <input
              type="number" min="1" required
              value={form.estimated_amount}
              onChange={update("estimated_amount")}
            />
          </div>
        </div>
        <div className="form-grid full">
          <div className="field">
            <label>Justification</label>
            <textarea required value={form.justification} onChange={update("justification")} />
          </div>
        </div>
        <div className="actions">
          <button className="primary" type="submit" disabled={submitting}>
            {submitting ? "Submitting…" : "Submit requisition"}
          </button>
        </div>
      </form>

      {error && <div className="feedback err">{error}</div>}

      {result && (
        <div className="feedback ok">
          <strong>{result.created.requisition_id}</strong> created and validated:
          <table style={{ marginTop: 10 }}>
            <tbody>
              <tr>
                <td>Preferred supplier used</td>
                <td className="num">
                  {result.validation.requested_supplier_is_preferred ? "Yes" : "No"}
                </td>
              </tr>
              {result.validation.preferred_supplier_alternative && (
                <tr>
                  <td>Suggested preferred supplier</td>
                  <td className="num">{result.validation.preferred_supplier_alternative}</td>
                </tr>
              )}
              <tr>
                <td>Budget check</td>
                <td className="num">
                  {result.validation.budget_check_passed ? "Passed" : "Review needed"} —{" "}
                  {result.validation.budget_note}
                </td>
              </tr>
              <tr>
                <td>Similar prior requisitions</td>
                <td className="num">{result.validation.similar_previous_requisitions}</td>
              </tr>
              <tr>
                <td>Recommendation</td>
                <td className="num">{result.validation.recommendation}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
