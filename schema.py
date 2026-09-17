"""Unified Procurement Schema (Deliverable D-01).

All three procurement domains - spend, requisitions and supplier contracts -
are normalised into this common model so that analytics and AI layers read
from a single consistent structure regardless of source system.
"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Boolean, Text, create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

Base = declarative_base()


class Supplier(Base):
    """Supplier master data."""
    __tablename__ = "suppliers"

    supplier_id = Column(String(20), primary_key=True)
    supplier_name = Column(String(200), nullable=False)
    normalised_name = Column(String(200), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    is_preferred = Column(Boolean, default=False)
    onboarded_date = Column(Date)
    country = Column(String(100), default="India")


class Contract(Base):
    """Supplier contract domain."""
    __tablename__ = "contracts"

    contract_id = Column(String(20), primary_key=True)
    supplier_id = Column(String(20), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    contracted_value = Column(Float, nullable=False)
    negotiated_discount_pct = Column(Float, default=0.0)
    status = Column(String(20), default="ACTIVE")


class SpendTransaction(Base):
    """Unified spend fact table - the common model.

    Schema: [source, supplier, category, department, amount,
             contract_status, requisition_id, timestamp]
    """
    __tablename__ = "spend_transactions"

    transaction_id = Column(String(30), primary_key=True)
    source_system = Column(String(50), nullable=False, index=True)
    supplier_id = Column(String(20), index=True)
    supplier_name = Column(String(200))
    category = Column(String(100), index=True)
    department = Column(String(100), index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR")
    contract_id = Column(String(20))
    contract_status = Column(String(30), index=True)  # ON_CONTRACT / OFF_CONTRACT / NO_CONTRACT
    requisition_id = Column(String(20))
    transaction_date = Column(Date, nullable=False, index=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)


class Requisition(Base):
    """Requisition domain."""
    __tablename__ = "requisitions"

    requisition_id = Column(String(20), primary_key=True)
    requester = Column(String(120), nullable=False)
    department = Column(String(100), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    requested_supplier_id = Column(String(20))
    estimated_amount = Column(Float, nullable=False)
    justification = Column(Text)
    status = Column(String(30), default="PENDING", index=True)
    approver = Column(String(120))
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime)


class DepartmentBudget(Base):
    """Budget allocations used for consumption tracking."""
    __tablename__ = "department_budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    department = Column(String(100), nullable=False, index=True)
    fiscal_year = Column(String(10), nullable=False)
    allocated_budget = Column(Float, nullable=False)


class DataAsset(Base):
    """Governance catalogue - registers every spend data asset with lineage."""
    __tablename__ = "data_assets"

    asset_id = Column(String(40), primary_key=True)
    asset_name = Column(String(200), nullable=False)
    asset_type = Column(String(50))          # SOURCE_FILE / TABLE / DERIVED_VIEW
    source_system = Column(String(100))
    owner = Column(String(120))
    row_count = Column(Integer, default=0)
    upstream_assets = Column(Text)           # comma-separated asset_ids
    transformation = Column(Text)            # what was applied
    classification = Column(String(50), default="INTERNAL")
    registered_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Audit tracking for procurement actions."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(40), nullable=False)
    action = Column(String(50), nullable=False)
    actor = Column(String(120))
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# Column contract used by ETL validation
UNIFIED_SPEND_COLUMNS = [
    "transaction_id", "source_system", "supplier_id", "supplier_name",
    "category", "department", "amount", "currency", "contract_id",
    "contract_status", "requisition_id", "transaction_date",
]


def get_engine(url: str | None = None):
    """Create a SQLAlchemy engine."""
    return create_engine(url or DATABASE_URL, future=True)


def get_session_factory(engine=None):
    return sessionmaker(bind=engine or get_engine(), future=True)


def init_db(engine=None) -> None:
    """Create all tables."""
    Base.metadata.create_all(engine or get_engine())
