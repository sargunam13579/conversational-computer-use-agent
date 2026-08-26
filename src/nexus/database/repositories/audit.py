"""
NEXUS Audit Repository.

Data access layer for security audit logs.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.database.models import AuditLog


class AuditRepository:
    """Repository for audit log database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log_action(
        self,
        action_type: str,
        tool_name: str | None = None,
        parameters: dict | None = None,
        result_status: str | None = None,
        risk_level: str = "low",
        session_id: str | None = None,
    ) -> AuditLog:
        """Record an action in the audit log."""
        entry = AuditLog(
            session_id=session_id,
            action_type=action_type,
            tool_name=tool_name,
            parameters=parameters,
            result_status=result_status,
            risk_level=risk_level,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def get_recent_logs(
        self,
        limit: int = 50,
        risk_level: str | None = None,
    ) -> list[AuditLog]:
        """Get recent audit log entries."""
        query = select(AuditLog).order_by(AuditLog.timestamp.desc())
        if risk_level:
            query = query.where(AuditLog.risk_level == risk_level)
        query = query.limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_high_risk_actions(
        self,
        since: datetime | None = None,
        session_id: str | None = None,
    ) -> int:
        """Count high/critical risk actions since a given time."""
        from sqlalchemy import func

        query = (
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.risk_level.in_(["high", "critical"]))
        )
        if since:
            query = query.where(AuditLog.timestamp >= since)
        if session_id:
            query = query.where(AuditLog.session_id == session_id)
        result = await self._session.execute(query)
        return result.scalar() or 0
