import asyncio
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.credential import Credential, utcnow
import config
async def get_credentials(db: AsyncSession, agent_id: str):
    result = await db.execute(select(Credential).where(Credential.agent_id == agent_id))
    return result.scalars().all()

async def revoke_credential(
    db: AsyncSession,
    credential_id: str,
    rng=None,
    failure_prob: float | None = None,
    delay_min: int | None = None,
    delay_max: int | None = None
) -> dict:
    """
    Simulates credential channel revocation with realistic latency and failure probabilities.
    For iam_role, this models cloud IAM propagation delays and permission constraints.
    """
    t0 = time.perf_counter()
    try:
        result = await db.execute(select(Credential).where(Credential.id == credential_id))
        cred = result.scalar_one_or_none()

        if not cred:
            return {"success": False, "latency_ms": 0.0, "retries": 0, "error": "Not found"}

        if cred.status in ("REVOKED", "EXPIRED"):
            return {"success": True, "latency_ms": 0.0, "retries": 0, "error": None}

        cred.status = "REVOKING"
        await db.commit()

        rng = rng if rng is not None else config.get_rng()
        cfg_dmin = delay_min if delay_min is not None else config.NET_DELAY_MIN
        cfg_dmax = delay_max if delay_max is not None else config.NET_DELAY_MAX
        d_min = max(0, min(cfg_dmin, cfg_dmax))
        d_max = max(d_min, max(cfg_dmin, cfg_dmax))
        delay_ms = rng.randint(d_min, d_max) if d_max > 0 else 0

        if cred.channel_type == "iam_role":
            delay_ms = int(delay_ms * config.IAM_DELAY_MULT)

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latency_ms = max(round(elapsed_ms, 2), 0.1)

        failed = False
        error_msg = None

        effective_prob = failure_prob if failure_prob is not None else config.REVOKE_FAILURE_PROB
        if cred.channel_type == "iam_role":
            iam_prob = failure_prob if failure_prob is not None else config.IAM_FAILURE_PROB
            if rng.random() < iam_prob:
                failed = True
                error_msg = "IAM propagation timeout or permission denied"
        else:
            if rng.random() < effective_prob:
                failed = True
                error_msg = "Generic revocation failure"

        if failed:
            cred.status = "REVOCATION_FAILED"
            await db.commit()
            return {"success": False, "latency_ms": latency_ms, "retries": 0, "error": error_msg}

        cred.status = "REVOKED"
        cred.revoked_at = utcnow()
        await db.commit()

        return {"success": True, "latency_ms": latency_ms, "retries": 0, "error": None}
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latency_ms = max(round(elapsed_ms, 2), 0.1)
        return {"success": False, "latency_ms": latency_ms, "retries": 0, "error": f"Revocation error: {str(e)}"}
