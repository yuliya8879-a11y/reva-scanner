"""Scan CRUD service for mini-scan persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import Scan, ScanStatus, ScanType


class ScanService:
    """Service for creating and updating Scan records in the database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_mini_scan(self, user_id: int) -> Scan:
        """Create a new mini Scan in collecting status and return it."""
        scan = Scan(
            user_id=user_id,
            scan_type=ScanType.mini.value,
            status=ScanStatus.collecting.value,
        )
        self.session.add(scan)
        await self.session.commit()
        await self.session.refresh(scan)
        return scan

    async def update_answers(self, scan_id: int, answers: dict) -> Scan:
        """Store the user's answers and advance status to in_progress."""
        scan = await self._get_or_raise(scan_id)
        scan.answers = answers
        scan.status = ScanStatus.in_progress.value
        await self.session.commit()
        await self.session.refresh(scan)
        return scan

    async def complete_mini_scan(
        self,
        scan_id: int,
        mini_report: str,
        numerology: dict,
        token_usage: dict,
    ) -> Scan:
        """Finalise the mini scan with report, numerology, and token usage."""
        scan = await self._get_or_raise(scan_id)
        scan.mini_report = mini_report
        scan.numerology = {**numerology, "token_usage": token_usage}
        scan.status = ScanStatus.completed.value
        scan.completed_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(scan)
        return scan

    async def get_scan(self, scan_id: int) -> Optional[Scan]:
        """Return a Scan by primary key, or None if not found."""
        result = await self.session.execute(select(Scan).where(Scan.id == scan_id))
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Full scan methods
    # ------------------------------------------------------------------

    async def create_full_scan(self, user_id: int, scan_type: str) -> Scan:
        """Create a new full scan (personal or business) in collecting status.

        Args:
            user_id: ID of the user starting the scan.
            scan_type: "personal" or "business".

        Returns:
            The newly created and refreshed Scan instance.

        Raises:
            ValueError: if scan_type is not "personal" or "business".
        """
        if scan_type not in (ScanType.personal.value, ScanType.business.value):
            raise ValueError(
                f"Invalid scan_type {scan_type!r}. Expected 'personal' or 'business'."
            )
        scan = Scan(
            user_id=user_id,
            scan_type=scan_type,
            status=ScanStatus.collecting.value,
            answers={},
        )
        self.session.add(scan)
        await self.session.commit()
        await self.session.refresh(scan)
        return scan

    async def save_answer(self, scan_id: int, key: str, value: str) -> Scan:
        """Merge a single answer into scan.answers without losing prior answers.

        Status remains unchanged (collecting) so the scan can be resumed.

        Args:
            scan_id: Primary key of the Scan to update.
            key: Answer key (matches QuestionDef.key).
            value: String value for the answer.

        Returns:
            The updated and refreshed Scan instance.
        """
        scan = await self._get_or_raise(scan_id)
        # Assign a new dict to ensure SQLAlchemy JSONB mutation is detected.
        scan.answers = {**(scan.answers or {}), key: value}
        await self.session.commit()
        await self.session.refresh(scan)
        return scan

    async def get_incomplete_scan(self, user_id: int) -> Optional[Scan]:
        """Find an in-progress full scan for the given user.

        Looks for a Scan with status=collecting and scan_type in (personal, business),
        ordered by created_at descending so the most recent is returned.

        Args:
            user_id: ID of the user to query for.

        Returns:
            Scan instance if found, or None.
        """
        result = await self.session.execute(
            select(Scan)
            .where(
                Scan.user_id == user_id,
                Scan.status == ScanStatus.collecting.value,
                Scan.scan_type.in_([ScanType.personal.value, ScanType.business.value]),
            )
            .order_by(Scan.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def complete_questionnaire(self, scan_id: int) -> Scan:
        """Mark all questions as answered by setting status=questionnaire_complete.

        Args:
            scan_id: Primary key of the Scan to finalize.

        Returns:
            The updated and refreshed Scan instance.
        """
        scan = await self._get_or_raise(scan_id)
        scan.status = ScanStatus.questionnaire_complete.value
        await self.session.commit()
        await self.session.refresh(scan)
        return scan

    async def get_answer_count(self, scan_id: int) -> int:
        """Return the number of answers collected so far for a scan.

        Args:
            scan_id: Primary key of the Scan to inspect.

        Returns:
            Number of keys in scan.answers, or 0 if answers is None.
        """
        scan = await self._get_or_raise(scan_id)
        return len(scan.answers) if scan.answers is not None else 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_or_raise(self, scan_id: int) -> Scan:
        scan = await self.get_scan(scan_id)
        if scan is None:
            raise ValueError(f"Scan {scan_id} not found")
        return scan
