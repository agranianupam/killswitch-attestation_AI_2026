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
    scenario_id: Optional[str] = None,
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
        scenario_id=scenario_id,
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

        if alert.experiment_id:
            related_res = await session.execute(
                select(Alert).where(
                    Alert.experiment_id == alert.experiment_id,
                    Alert.acknowledged == False
                )
            )
            for rel in related_res.scalars().all():
                rel.acknowledged = True

        await session.commit()

        try:
            await manager.broadcast({
                "type": "alert_acknowledged",
                "data": {"id": alert_id, "experiment_id": alert.experiment_id}
            })
        except Exception:
            pass
        return True

async def acknowledge_alerts_by_experiment(experiment_id: str) -> bool:
    async with models.database.AsyncSessionLocal() as session:
        res = await session.execute(select(Alert).where(Alert.experiment_id == experiment_id))
        alerts = res.scalars().all()
        if not alerts:
            return False
        for a in alerts:
            a.acknowledged = True
        await session.commit()
        try:
            await manager.broadcast({
                "type": "alert_acknowledged",
                "data": {"experiment_id": experiment_id}
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

async def get_active_critical_incident() -> Optional[dict]:
    """
    Finds the latest unacknowledged critical incident, enriched with
    associated shutdown event metadata (agent mode, scenario, verification, residual risk).
    """
    from models.shutdown_event import ShutdownEvent
    async with models.database.AsyncSessionLocal() as session:
        query = (
            select(Alert)
            .where(
                Alert.severity == "critical",
                Alert.category == "critical_emergency",
                Alert.acknowledged == False
            )
            .order_by(Alert.created_at.desc())
            .limit(1)
        )
        res = await session.execute(query)
        alert = res.scalar_one_or_none()
        if not alert:
            query_fb = (
                select(Alert)
                .where(Alert.severity == "critical", Alert.acknowledged == False)
                .order_by(Alert.created_at.desc())
                .limit(1)
            )
            res_fb = await session.execute(query_fb)
            alert = res_fb.scalar_one_or_none()
            if not alert:
                return None

        alert_data = alert.to_dict()
        sh_event = None
        if alert.experiment_id:
            sh_res = await session.execute(select(ShutdownEvent).where(ShutdownEvent.id == alert.experiment_id))
            sh_event = sh_res.scalar_one_or_none()

        mode_str = sh_event.agent_mode if sh_event else "gemini"
        is_sim = str(mode_str).lower() in ("scripted", "agent_xyz", "offline")
        agent_name = "Agent XYZ (Simulation)" if is_sim else "Gemini Live Agent"

        scenario_name = getattr(sh_event, "scenario_name", None) or getattr(alert, "scenario_id", None) or "Deterministic Simulation Scenario"
        run_id = alert.experiment_id or alert.id
        incident_id = f"incident_{run_id}"

        verif_status = "Access remains available"
        if sh_event:
            if (sh_event.leaked_channels or 0) > 0 and (sh_event.in_flight_failures or 0) > 0:
                verif_status = "Access remains available & In-Flight Cutoff Violated"
            elif (sh_event.leaked_channels or 0) > 0:
                verif_status = "Access remains available (Liveness Probe Confirmed)"
            elif (sh_event.in_flight_failures or 0) > 0:
                verif_status = "Cutoff Violated (Operation Completed After Shutdown)"
            elif sh_event.partial_failure:
                verif_status = "Revocation Attempt Failed"

        return {
            "id": alert.id,
            "incident_id": incident_id,
            "alert_id": alert.id,
            "run_id": run_id,
            "event_id": run_id,
            "agent_name": agent_name,
            "agent_mode": mode_str,
            "scenario_id": getattr(sh_event, "scenario_id", None) or getattr(alert, "scenario_id", None),
            "scenario_name": scenario_name,
            "severity": "CRITICAL",
            "title": alert.title,
            "failure_reason": alert.message,
            "affected_channel": alert.channel_or_op_id or "Revocation Subsystem",
            "verification_status": verif_status,
            "final_state": sh_event.final_state if sh_event else "CONTAINMENT_FAILED",
            "residual_risk": sh_event.residual_risk if sh_event else 0.70,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "recommended_action": alert.recommended_action
        }

