import uuid
from typing import List, Optional
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

import models.database
from models.alert import Alert, utcnow
from services.agent_llm import sanitize_log_message
from api.websocket import manager

async def create_alert(
    severity: str,
    category: str,
    title: str,
    message: str,
    recommended_action: Optional[str] = None,
    experiment_id: Optional[str] = None,
    channel_or_op_id: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> dict:
    clean_msg = sanitize_log_message(message)
    clean_title = sanitize_log_message(title)
    clean_rec = sanitize_log_message(recommended_action) if recommended_action else None

    alert_id = uuid.uuid4().hex
    alert = Alert(
        id=alert_id,
        severity=severity.lower(),
        category=category.lower(),
        title=clean_title,
        message=clean_msg,
        recommended_action=clean_rec,
        experiment_id=experiment_id,
        channel_or_op_id=channel_or_op_id,
        acknowledged=False,
        created_at=utcnow()
    )

    if db is not None:
        db.add(alert)
        await db.commit()
    else:
        async with models.database.AsyncSessionLocal() as session:
            session.add(alert)
            await session.commit()

    alert_dict = alert.to_dict()

    try:
        await manager.broadcast({
            "type": "new_alert",
            "data": alert_dict
        })
    except Exception:
        pass

    return alert_dict

async def get_alerts(
    limit: int = 50,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    unacknowledged_only: bool = False
) -> List[dict]:
    async with models.database.AsyncSessionLocal() as session:
        query = select(Alert)
        if severity:
            query = query.where(Alert.severity == severity.lower())
        if category:
            query = query.where(Alert.category == category.lower())
        if unacknowledged_only:
            query = query.where(Alert.acknowledged == False)

        query = query.order_by(Alert.created_at.desc()).limit(limit)
        res = await session.execute(query)
        alerts = res.scalars().all()
        return [a.to_dict() for a in alerts]

async def acknowledge_alert(alert_id: str) -> bool:
    async with models.database.AsyncSessionLocal() as session:
        res = await session.execute(select(Alert).where(Alert.id == alert_id))
        alert = res.scalar_one_or_none()
        if not alert:
            return False
        alert.acknowledged = True
        await session.commit()

        try:
            await manager.broadcast({
                "type": "alert_acknowledged",
                "data": {"id": alert_id}
            })
        except Exception:
            pass
        return True

async def clear_all_alerts() -> int:
    async with models.database.AsyncSessionLocal() as session:
        stmt = update(Alert).where(Alert.acknowledged == False).values(acknowledged=True)
        res = await session.execute(stmt)
        await session.commit()
        try:
            await manager.broadcast({
                "type": "alerts_cleared",
                "data": {"count": res.rowcount}
            })
        except Exception:
            pass
        return res.rowcount or 0

async def get_alerts_summary() -> dict:
    async with models.database.AsyncSessionLocal() as session:
        res = await session.execute(
            select(Alert.severity, func.count(Alert.id))
            .where(Alert.acknowledged == False)
            .group_by(Alert.severity)
        )
        counts = {row[0]: row[1] for row in res.all()}
        total = sum(counts.values())
        return {
            "total": total,
            "unacknowledged_total": total,
            "critical": counts.get("critical", 0),
            "error": counts.get("error", 0),
            "warning": counts.get("warning", 0),
            "info": counts.get("info", 0)
        }
