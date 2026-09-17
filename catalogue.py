"""Governance catalogue - registers every spend data asset with lineage.

Satisfies the RFP requirement: "Governance catalogue - all spend data assets
registered with lineage."
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

import pandas as pd

from ..schema import get_engine, init_db


def make_asset_id(name: str) -> str:
    """Deterministic asset id so re-running the pipeline does not duplicate entries."""
    return "AST-" + hashlib.sha1(name.encode()).hexdigest()[:10].upper()


class GovernanceCatalogue:
    """In-memory catalogue that persists to the data_assets table."""

    def __init__(self, engine=None):
        self.engine = engine or get_engine()
        init_db(self.engine)
        self._assets: dict[str, dict] = {}
        self._audit: list[dict] = []

    # ---------------- registration ----------------

    def register(
        self,
        name: str,
        asset_type: str,
        source_system: str = "",
        owner: str = "Procurement Data Team",
        row_count: int = 0,
        upstream: list[str] | None = None,
        transformation: str = "",
        classification: str = "INTERNAL",
    ) -> str:
        asset_id = make_asset_id(name)
        self._assets[asset_id] = {
            "asset_id": asset_id,
            "asset_name": name,
            "asset_type": asset_type,
            "source_system": source_system,
            "owner": owner,
            "row_count": int(row_count),
            "upstream_assets": ",".join(upstream or []),
            "transformation": transformation,
            "classification": classification,
            "registered_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        return asset_id

    def log_action(self, entity_type: str, entity_id: str, action: str,
                   actor: str = "system", details: str = "") -> None:
        self._audit.append({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "actor": actor,
            "details": details,
            "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        })

    # ---------------- lineage ----------------

    def lineage_for(self, asset_id: str) -> dict:
        """Walk upstream recursively and return the full lineage tree."""
        asset = self._assets.get(asset_id)
        if not asset:
            return {}
        upstream_ids = [a for a in asset["upstream_assets"].split(",") if a]
        return {
            "asset_id": asset_id,
            "asset_name": asset["asset_name"],
            "asset_type": asset["asset_type"],
            "transformation": asset["transformation"],
            "row_count": asset["row_count"],
            "upstream": [self.lineage_for(u) for u in upstream_ids],
        }

    def lineage_edges(self) -> list[dict]:
        """Flat edge list for rendering a lineage graph in the portal."""
        edges = []
        for asset in self._assets.values():
            for upstream in asset["upstream_assets"].split(","):
                if upstream:
                    edges.append({"from": upstream, "to": asset["asset_id"]})
        return edges

    # ---------------- output ----------------

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(list(self._assets.values()))

    def audit_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self._audit)

    def coverage_report(self, expected_assets: int) -> dict:
        registered = len(self._assets)
        with_lineage = sum(1 for a in self._assets.values() if a["upstream_assets"])
        return {
            "registered_assets": registered,
            "expected_assets": expected_assets,
            "registration_coverage_pct": round(100 * registered / max(expected_assets, 1), 2),
            "assets_with_lineage": with_lineage,
            "lineage_coverage_pct": round(100 * with_lineage / max(registered, 1), 2),
        }

    def persist(self) -> int:
        frame = self.to_frame()
        if not frame.empty:
            frame.to_sql("data_assets", self.engine, if_exists="replace", index=False)
        audit = self.audit_frame()
        if not audit.empty:
            audit.to_sql("audit_log", self.engine, if_exists="replace", index=False)
        return len(frame)

    def export_json(self, path) -> None:
        payload = {
            "assets": list(self._assets.values()),
            "lineage_edges": self.lineage_edges(),
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
