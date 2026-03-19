from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScanType(str, Enum):
    mini = "mini"
    personal = "personal"
    business = "business"


class ScanStatus(str, Enum):
    pending = "pending"
    collecting = "collecting"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    scan_type: Mapped[str] = mapped_column(String(32), nullable=False)  # mini / personal / business
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ScanStatus.pending)
    answers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    numerology: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mini_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_paid: Mapped[bool] = mapped_column(default=False, nullable=False)
    # FK back to Payment; use_alter avoids circular FK dependency at DDL time
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payments.id", use_alter=True, name="fk_scans_payment_id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Scan id={self.id} user_id={self.user_id} type={self.scan_type}>"
