from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    scan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scans.id"), nullable=True, index=True)
    amount_stars: Mapped[int] = mapped_column(Integer, nullable=False)  # Telegram Stars
    product_type: Mapped[str] = mapped_column(String(64), nullable=False)  # personal/business/practices
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    telegram_payment_charge_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Payment id={self.id} user_id={self.user_id} stars={self.amount_stars}>"
