"""PaymentService — data layer for all payment state transitions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment
from app.models.scan import Scan


class PaymentService:
    """Service for creating and confirming Payment records.

    All ORM mutations go through this service so that bot handlers never
    touch Payment or payment-related Scan fields directly.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_payment(
        self,
        user_id: int,
        scan_id: int,
        amount_stars: int,
        product_type: str,
    ) -> Payment:
        """Insert a new Payment with status=pending and return it.

        Args:
            user_id: ID of the user initiating payment.
            scan_id: ID of the Scan this payment is for.
            amount_stars: Price in Telegram Stars.
            product_type: "personal" or "business".

        Returns:
            The newly created and refreshed Payment instance.
        """
        payment = Payment(
            user_id=user_id,
            scan_id=scan_id,
            amount_stars=amount_stars,
            product_type=product_type,
            status="pending",
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def confirm_payment(
        self,
        telegram_charge_id: str,
        scan_id: int,
    ) -> Payment:
        """Confirm a pending payment for the given scan.

        Sets Payment.status=paid, Payment.telegram_payment_charge_id,
        Payment.paid_at, and atomically updates Scan.is_paid=True and
        Scan.payment_id in the same commit.

        If the payment is already paid (idempotent call), returns it
        unchanged without writing to the database.

        Args:
            telegram_charge_id: The charge ID from Telegram's pre_checkout callback.
            scan_id: ID of the Scan whose pending payment to confirm.

        Returns:
            The Payment instance (paid or already-paid).

        Raises:
            ValueError: if no Payment is found for the given scan_id.
        """
        result = await self.session.execute(
            select(Payment)
            .where(Payment.scan_id == scan_id)
            .order_by(Payment.created_at.desc())
            .limit(1)
        )
        payment = result.scalar_one_or_none()

        if payment is None:
            raise ValueError(f"No payment found for scan_id={scan_id}")

        if payment.status == "paid":
            return payment  # idempotent — already confirmed

        payment.status = "paid"
        payment.telegram_payment_charge_id = telegram_charge_id
        payment.paid_at = datetime.now(timezone.utc)

        scan_result = await self.session.execute(
            select(Scan).where(Scan.id == scan_id)
        )
        scan = scan_result.scalar_one_or_none()
        if scan is not None:
            scan.is_paid = True
            scan.payment_id = payment.id

        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_pending_payment(
        self,
        user_id: int,
        scan_type: str,
    ) -> Optional[Payment]:
        """Return the most recent pending Payment for a user + scan_type.

        Joins Payment with Scan to filter by scan_type. Returns None if
        no pending payment exists.

        Args:
            user_id: ID of the user to query for.
            scan_type: "personal" or "business".

        Returns:
            Most recent pending Payment, or None.
        """
        result = await self.session.execute(
            select(Payment)
            .join(Scan, Payment.scan_id == Scan.id)
            .where(
                Payment.user_id == user_id,
                Payment.status == "pending",
                Scan.scan_type == scan_type,
            )
            .order_by(Payment.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
