"""Extract stage - reads the fragmented procurement sources."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import RAW_DIR


def extract_spend_sources(raw_dir: Path | None = None) -> pd.DataFrame:
    """Read and concatenate every spend source file.

    Mimics pulling from ERP exports, corporate card feeds and the invoice
    system - three systems that in reality never share a schema.
    """
    raw_dir = raw_dir or RAW_DIR
    files = sorted(raw_dir.glob("spend_*.csv"))
    if not files:
        raise FileNotFoundError(f"No spend source files found in {raw_dir}")

    frames = []
    for path in files:
        frame = pd.read_csv(path)
        frame["_source_file"] = path.name
        frames.append(frame)

    return pd.concat(frames, ignore_index=True)


def extract_table(name: str, raw_dir: Path | None = None) -> pd.DataFrame:
    """Read a single raw table by name (suppliers, contracts, requisitions, budgets)."""
    raw_dir = raw_dir or RAW_DIR
    path = raw_dir / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Raw file not found: {path}")
    return pd.read_csv(path)


def list_source_files(raw_dir: Path | None = None) -> list[str]:
    """Return every raw source file name - used by the governance catalogue."""
    raw_dir = raw_dir or RAW_DIR
    return sorted(p.name for p in raw_dir.glob("*.csv"))
