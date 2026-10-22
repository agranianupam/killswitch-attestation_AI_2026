"""
tests/test_iam_failure.py
"""

import pytest
import config
from services.agent_service import seed_demo_agent
from services.orchestrator import run_shutdown

@pytest.mark.asyncio
async def test_iam_failure_escalates_risk(db_session):
    agent = await seed_demo_agent(db_session)

    config.IAM_FAILURE_PROB = 1.0

    res = await run_shutdown(db_session, agent.id, "A", "manual")

    assert res["final_state"] == "CONTAINMENT_FAILED"
    assert res["residual_risk"] > 0.0
    assert res["partial_failure"] is True

    config.IAM_FAILURE_PROB = 0.0
