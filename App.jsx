import React, { useEffect, useState } from "react";
import Dashboard from "./screens/Dashboard.jsx";
import SubmitRequisition from "./screens/SubmitRequisition.jsx";
import Approvals from "./screens/Approvals.jsx";
import Governance from "./screens/Governance.jsx";
import { api } from "./api.js";

const SCREENS = [
  { key: "dashboard", label: "Spend Dashboard", component: Dashboard,
    title: "Spend dashboard", sub: "Real-time procurement visibility and AI-flagged risk" },
  { key: "submit", label: "Submit Requisition", component: SubmitRequisition,
    title: "Submit a requisition", sub: "Validated instantly against contracts and budget" },
  { key: "approvals", label: "Approval Queue", component: Approvals,
    title: "Approval queue", sub: "Review requisitions with system-generated recommendations" },
  { key: "governance", label: "Governance & Savings", component: Governance,
    title: "Governance & savings", sub: "Data lineage, consolidation and renewal opportunities" },
];

export default function App() {
  const [active, setActive] = useState("dashboard");
  const [apiOk, setApiOk] = useState(null);

  useEffect(() => {
    api.health().then(() => setApiOk(true)).catch(() => setApiOk(false));
  }, []);

  const screen = SCREENS.find((s) => s.key === active);
  const Screen = screen.component;

  return (
    <div className="app">
      <aside className="sidebar">
        <div>
          <div className="brand">ProcureSmart AI</div>
          <div className="brand-sub">S4-I-22 · Requisition Portal</div>
        </div>
        <nav className="nav">
          {SCREENS.map((s) => (
            <button
              key={s.key}
              className={`nav-item ${active === s.key ? "active" : ""}`}
              onClick={() => setActive(s.key)}
            >
              {s.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">IMPACT pSiddhi 3.0 — Semester 4</div>
      </aside>

      <main className="main">
        <h1 className="page-title">{screen.title}</h1>
        <p className="page-sub">
          {screen.sub}{" "}
          <span className="status-pill">
            <span className={`status-dot ${apiOk === false ? "err" : ""}`} />
            {apiOk === null ? "checking API…" : apiOk ? "API connected" : "API unreachable"}
          </span>
        </p>
        <Screen />
      </main>
    </div>
  );
}
