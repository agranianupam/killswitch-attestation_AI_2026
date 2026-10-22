import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.evaluation import EvaluationRecord
from models.shutdown_event import ShutdownEvent
import models.database

RELEVANT_SECURITY_CATEGORIES = {"security", "revocation", "leak", "tamper", "critical"}
UNRELATED_ALERT_CATEGORIES = {"quota", "provider", "scheduler", "system", "info"}

async def filter_relevant_security_alerts(
    db: Optional[AsyncSession],
    alert_ids: List[str],
    raw_alerts: Optional[List[Any]] = None
) -> List[str]:
    """
    Filters alert IDs to return only those corresponding to genuine security detections
    (e.g., leaks, revocation failures, probe liveness, tampering).
    Excludes unrelated alerts like quota warnings, provider notices, scheduler status, or informational logs.
    """
    relevant_ids = []

    if raw_alerts:
        for a in raw_alerts:
            aid = getattr(a, "id", None) or (a.get("id") if isinstance(a, dict) else str(a))
            cat = str(getattr(a, "category", None) or (a.get("category") if isinstance(a, dict) else "")).lower()
            sev = str(getattr(a, "severity", None) or (a.get("severity") if isinstance(a, dict) else "")).lower()

            if cat in UNRELATED_ALERT_CATEGORIES or sev == "info":
                continue
            if cat in RELEVANT_SECURITY_CATEGORIES or sev in ("critical", "warning", "high", "error"):
                relevant_ids.append(aid)
        return relevant_ids

    if not alert_ids:
        return []

    if db is not None:
        try:
            from models.alert import Alert
            result = await db.execute(select(Alert).where(Alert.id.in_(alert_ids)))
            alerts = result.scalars().all()
            if alerts:
                for al in alerts:
                    cat = (al.category or "").lower()
                    sev = (al.severity or "").lower()
                    if cat in UNRELATED_ALERT_CATEGORIES or sev == "info":
                        continue
                    if cat in RELEVANT_SECURITY_CATEGORIES or sev in ("critical", "warning", "high", "error"):
                        relevant_ids.append(al.id)
                return relevant_ids
        except Exception:
            pass

    for aid in alert_ids:
        aid_lower = aid.lower()
        if any(unrel in aid_lower for unrel in ("quota", "provider", "scheduler", "info", "unrelated")):
            continue
        relevant_ids.append(aid)

    return relevant_ids

async def record_evaluation(
    db: AsyncSession,
    shutdown_event_id: str,
    agent_profile: str,
    strategy: str,
    execution_mode: str,
    expected_condition: str,
    actual_leak_count: int = 0,
    actual_channel_leak_count: int = 0,
    actual_failed_revocations: int = 0,
    monitor_alert_ids: Optional[List[str]] = None,
    monitor_alerts: Optional[List[Any]] = None,
    attestation_id: Optional[str] = None,
    observed_outcome: Optional[str] = None,
    monitor_detected: Optional[bool] = None,
    monitor_classification: Optional[str] = None,
    ground_truth_override: Optional[str] = None,
) -> EvaluationRecord:
    monitor_alert_ids = monitor_alert_ids or []

    if observed_outcome is None:
        if actual_leak_count > 0:
            observed_outcome = f"LEAK_OBSERVED({actual_leak_count}_ops)"
        elif actual_channel_leak_count > 0:
            observed_outcome = f"CHANNEL_LEAK_OBSERVED({actual_channel_leak_count}_channels)"
        elif actual_failed_revocations > 0:
            observed_outcome = f"REVOCATION_FAILED({actual_failed_revocations}_failed)"
        else:
            observed_outcome = "CLEAN_CONTAINMENT"

    if ground_truth_override in ("ANOMALY", "NORMAL", "UNRESOLVED"):
        gt_label = ground_truth_override
    elif observed_outcome in ("UNRESOLVED", "SKIPPED", "INDETERMINATE") or actual_leak_count is None:
        gt_label = "UNRESOLVED"
    elif (
        actual_leak_count > 0
        or actual_channel_leak_count > 0
        or actual_failed_revocations > 0
        or any(k in observed_outcome.upper() for k in ("LEAK", "REVOCATION_FAILED", "PROBE_FAILED", "TAMPER_DETECTED"))
    ):
        gt_label = "ANOMALY"
    else:
        gt_label = "NORMAL"

    relevant_security_alert_ids = await filter_relevant_security_alerts(
        db=db,
        alert_ids=monitor_alert_ids,
        raw_alerts=monitor_alerts
    )

    if monitor_detected is not None:
        has_monitor_detection = bool(monitor_detected)
    else:
        has_monitor_detection = len(relevant_security_alert_ids) > 0

    if monitor_classification is None:
        monitor_class = "ANOMALY_DETECTED" if has_monitor_detection else "CLEAN_CONTAINMENT"
    else:
        monitor_class = monitor_classification

    if gt_label == "ANOMALY" and has_monitor_detection:
        verdict = "TRUE_POSITIVE"
        disagreement = None
    elif gt_label == "NORMAL" and not has_monitor_detection:
        verdict = "TRUE_NEGATIVE"
        disagreement = None
    elif gt_label == "NORMAL" and has_monitor_detection:
        verdict = "FALSE_POSITIVE"
        disagreement = "Monitor raised security alert or flagged anomaly despite verified normal containment."
    elif gt_label == "ANOMALY" and not has_monitor_detection:
        verdict = "FALSE_NEGATIVE"
        disagreement = "Security anomaly occurred (ground-truth leak, revocation failure, or probe liveness) but monitor failed to report it or emit an alert."
    else:
        verdict = "UNRESOLVED"
        disagreement = "Indeterminate or unobservable experimental outcome; excluded from performance rates."

    rec = EvaluationRecord(
        id=uuid.uuid4().hex,
        shutdown_event_id=shutdown_event_id,
        agent_profile=agent_profile,
        strategy=strategy,
        execution_mode=execution_mode,
        expected_condition=expected_condition,
        ground_truth_label=gt_label,
        observed_outcome=observed_outcome,
        monitor_detected=has_monitor_detection,
        monitor_classification=monitor_class,
        verdict=verdict,
        alert_generated=len(relevant_security_alert_ids) > 0,
        alert_id=relevant_security_alert_ids[0] if relevant_security_alert_ids else None,
        attestation_id=attestation_id,
        detection_latency_ms=None,
        disagreement_notes=disagreement
    )
    db.add(rec)
    await db.commit()
    return rec

async def get_monitor_metrics(db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    async def _query(session: AsyncSession) -> Dict[str, Any]:
        stmt = select(EvaluationRecord)
        res = await session.execute(stmt)
        records: List[EvaluationRecord] = res.scalars().all()

        tp = sum(1 for r in records if r.verdict == "TRUE_POSITIVE" and r.ground_truth_label != "UNRESOLVED")
        fp = sum(1 for r in records if r.verdict == "FALSE_POSITIVE" and r.ground_truth_label != "UNRESOLVED")
        tn = sum(1 for r in records if r.verdict == "TRUE_NEGATIVE" and r.ground_truth_label != "UNRESOLVED")
        fn = sum(1 for r in records if r.verdict == "FALSE_NEGATIVE" and r.ground_truth_label != "UNRESOLVED")
        unresolved = sum(1 for r in records if r.ground_truth_label == "UNRESOLVED" or r.verdict not in ("TRUE_POSITIVE", "FALSE_POSITIVE", "TRUE_NEGATIVE", "FALSE_NEGATIVE"))
        total = len(records)
        evaluated_total = tp + fp + tn + fn

        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else None
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else None
        fpr = round(fp / (fp + tn), 4) if (fp + tn) > 0 else None

        if evaluated_total == 0:
            accuracy = None
            accuracy_display = "N/A (no evaluated records)"
        elif (tn + fp) == 0:
            accuracy = None
            accuracy_display = "N/A (no negative examples in evaluation set)"
        elif (tp + fn) == 0:
            accuracy = None
            accuracy_display = "N/A (no positive examples in evaluation set)"
        else:
            accuracy = round((tp + tn) / evaluated_total, 4)
            accuracy_display = f"{accuracy * 100:.1f}%"

        by_profile: Dict[str, Dict[str, int]] = {}
        for r in records:
            p = r.agent_profile or "unknown"
            if p not in by_profile:
                by_profile[p] = {"TP": 0, "FP": 0, "TN": 0, "FN": 0, "UNRESOLVED": 0, "total": 0}
            if r.ground_truth_label != "UNRESOLVED" and r.verdict in ("TRUE_POSITIVE", "FALSE_POSITIVE", "TRUE_NEGATIVE", "FALSE_NEGATIVE"):
                k = "TP" if r.verdict == "TRUE_POSITIVE" else ("FP" if r.verdict == "FALSE_POSITIVE" else ("TN" if r.verdict == "TRUE_NEGATIVE" else "FN"))
                by_profile[p][k] += 1
            else:
                by_profile[p]["UNRESOLVED"] += 1
            by_profile[p]["total"] += 1

        by_strategy: Dict[str, Dict[str, int]] = {}
        for r in records:
            s = r.strategy or "unknown"
            if s not in by_strategy:
                by_strategy[s] = {"TP": 0, "FP": 0, "TN": 0, "FN": 0, "UNRESOLVED": 0, "total": 0}
            if r.ground_truth_label != "UNRESOLVED" and r.verdict in ("TRUE_POSITIVE", "FALSE_POSITIVE", "TRUE_NEGATIVE", "FALSE_NEGATIVE"):
                k = "TP" if r.verdict == "TRUE_POSITIVE" else ("FP" if r.verdict == "FALSE_POSITIVE" else ("TN" if r.verdict == "TRUE_NEGATIVE" else "FN"))
                by_strategy[s][k] += 1
            else:
                by_strategy[s]["UNRESOLVED"] += 1
            by_strategy[s]["total"] += 1
        def _normalize_dt(dt):
            if dt is None:
                return datetime.min
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt

        recent = [r.to_dict() for r in sorted(records, key=lambda x: _normalize_dt(x.created_at), reverse=True)[:15]]

        return {
            "total_evaluations": total,
            "sample_size": total,
            "unresolved_cases": unresolved,
            "confusion_matrix": {
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
                "unresolved": unresolved
            },
            "metrics": {
                "precision": precision,
                "recall": recall,
                "false_positive_rate": fpr,
                "accuracy": accuracy,
                "precision_display": f"{precision * 100:.1f}%" if precision is not None else "N/A (no positive predictions)",
                "recall_display": f"{recall * 100:.1f}%" if recall is not None else "N/A (no positive conditions)",
                "fpr_display": f"{fpr * 100:.1f}%" if fpr is not None else "N/A (no negative conditions)",
                "accuracy_display": accuracy_display
            },
            "by_profile": by_profile,
            "by_strategy": by_strategy,
            "recent_records": recent
        }

    if db is not None:
        return await _query(db)
    async with models.database.AsyncSessionLocal() as session:
        return await _query(session)
