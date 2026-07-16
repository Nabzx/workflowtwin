"""Persistence state for auditable and idempotent synthetic generation runs."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from workflowtwin.infrastructure.database import Base


class GenerationRunStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class SyntheticGenerationRunRecord(Base):
    """Small run ledger; not a general background-job model."""

    __tablename__ = "synthetic_generation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="valid_status",
        ),
        CheckConstraint("requested_case_count > 0", name="positive_requested_case_count"),
        CheckConstraint("generated_case_count >= 0", name="nonnegative_generated_case_count"),
        CheckConstraint("generated_event_count >= 0", name="nonnegative_generated_event_count"),
        Index("ix_synthetic_generation_runs_status", "status"),
        Index("ix_synthetic_generation_runs_started_at", "started_at"),
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    generator_version: Mapped[str] = mapped_column(String(20), nullable=False)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    manifest_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dataset_fingerprint: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_summary: Mapped[str | None] = mapped_column(Text)
