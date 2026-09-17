# ProcureSmart AI

Smart Procurement Management Platform — IMPACT pSiddhi 3.0, Topic **S4-I-22**
Semester 4 · Integration Mastery (Capstone)

Consolidates fragmented procurement spend data, processes it through an analytics
engine, governs it with a lineage catalogue, and applies AI to surface savings
opportunities, detect maverick spend, and generate procurement intelligence.

---

## Architecture

```
Procurement Sources (ERP export · Corporate card · Invoice system · Contracts · Requisitions)
        ↓
Python ETL Pipeline  (extract → transform → validate → load)
        ↓
Unified Procurement Database  (SQLite local / Azure SQL · PostgreSQL cloud)
        ↓
Analytics Engine + AI Layer  (Pandas · Scikit-learn Isolation Forest · LLM narratives)
        ↓
FastAPI Backend Services
        ↓
React Requisition Portal + Analytics Dashboards
```

### Procurement domains managed (3)
| Domain | Source | Table |
|---|---|---|
| Spend | ERP export, corporate card, invoice system | `spend_transactions` |
| Requisitions | Requisition tool | `requisitions` |
| Supplier contracts | Contract repository | `contracts`, `suppliers` |

### Unified spend schema
`[transaction_id, source_system, supplier_id, supplier_name, category, department,
amount, currency, contract_id, contract_status, requisition_id, transaction_date]`

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then add your OpenAI key
```

## Running the pipeline

```bash
python -m src.generate_data        # generate synthetic procurement datasets
python -m src.etl.pipeline         # run the full ETL + governance pipeline
```

Expected output: 5,200 spend transactions loaded across 3 source systems,
data completeness ≥99%, governance catalogue populated with lineage.

## Testing

```bash
pytest --cov=src --cov-report=term-missing --cov-report=html
```

---

## Project layout

```
src/
  config.py              central configuration and business rules
  schema.py              unified procurement schema (SQLAlchemy models)
  generate_data.py       synthetic dataset generator with seeded patterns
  etl/
    extract.py           reads fragmented source files
    transform.py         cleaning, standardisation, validation rules
    load.py              database load helpers
    pipeline.py          end-to-end orchestration
  governance/
    catalogue.py         data asset registry with lineage + audit log
  analytics/             spend, supplier and budget analytics
  ai/                    maverick detection, consolidation, savings, narratives
  api/                   FastAPI backend services
tests/                   pytest suite
```

## Status

| Layer | Status |
|---|---|
| Unified schema | Complete |
| Synthetic data generation | Complete |
| ETL pipeline + validation | Complete |
| Governance catalogue + lineage | Complete |
| Analytics engine | In progress |
| AI intelligence layer | In progress |
| FastAPI backend | In progress |
| React requisition portal | In progress |
| QA test suite | In progress |
