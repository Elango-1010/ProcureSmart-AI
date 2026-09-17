const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export const api = {
  health: () => fetch("/health").then((r) => r.json()),
  spendSummary: () => request("/analytics/spend"),
  supplierAnalytics: () => request("/analytics/suppliers"),
  kpis: () => request("/analytics/kpis"),
  budgetUtilisation: () => request("/analytics/budget-utilisation"),
  maverickSpend: (topN = 15) => request(`/ai/maverick-spend?top_n=${topN}`),
  consolidation: () => request("/ai/consolidation"),
  savings: () => request("/ai/savings"),
  narrative: () => request("/ai/narrative"),
  requisitions: (status) =>
    request(`/requisitions${status ? `?status=${status}` : ""}`),
  validateRequisition: (id) => request(`/requisitions/${id}/validate`),
  createRequisition: (payload) =>
    request("/requisitions", { method: "POST", body: JSON.stringify(payload) }),
  decideRequisition: (id, payload) =>
    request(`/requisitions/${id}/decide`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  catalogue: () => request("/governance/catalogue"),
  auditLog: (limit = 30) => request(`/governance/audit-log?limit=${limit}`),
};
