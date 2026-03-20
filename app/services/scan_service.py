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
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_or_raise(self, scan_id: int) -> Scan:
        scan = await self.get_scan(scan_id)
        if scan is None:
            raise ValueError(f"Scan {scan_id} not found")
        return scan
