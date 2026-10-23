from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class ScenarioDefinition(BaseModel):
    id: str
    code: str
    name: str
    category: str
    description: str
    expected_behavior: str
    target_channels: List[str] = Field(default_factory=list)
    inject_revocation_failure: bool = False
    failed_channels: List[str] = Field(default_factory=list)
    inject_delay_retry: bool = False
    delayed_channels: List[str] = Field(default_factory=list)
    inject_in_flight_leak: bool = False
    inject_probe_failure: bool = False
    expected_critical_alert: bool = False
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = self.model_dump()
        data["expected_containment"] = self.expected_behavior
        return data

SCENARIOS: Dict[str, ScenarioDefinition] = {
    "clean_shutdown": ScenarioDefinition(
        id="clean_shutdown",
        code="A",
        name="Scenario A: Clean Shutdown",
        category="Baseline",
        description="Demonstrates the expected successful shutdown path. Active credentials and channels are revoked cleanly, in-flight tasks are contained per policy, and post-shutdown verification passes.",
        expected_behavior="Normal revocation, containment per strategy policy, all verification checks pass, low residual risk, no emergency alert.",
        target_channels=["api_key", "session_token", "iam_role", "network"],
        inject_revocation_failure=False,
        inject_delay_retry=False,
        inject_in_flight_leak=False,
        inject_probe_failure=False,
        expected_critical_alert=False,
        notes="Clean shutdown is confirmed via actual verification checks. Success is not hardcoded."
    ),
    "credential_revocation_failure": ScenarioDefinition(
        id="credential_revocation_failure",
        code="B",
        name="Scenario B: Credential Revocation Failure",
        category="Revocation Defect",
        description="Simulates an API key or access token remaining active after normal revocation attempts. Exercises retry logic to exhaustion and flags persistent channel exposure.",
        expected_behavior="Revocation retry attempts fail on target credential, post-shutdown challenge probe confirms channel liveness, containment fails, critical emergency alert is raised.",
        target_channels=["api_key"],
        inject_revocation_failure=True,
        failed_channels=["api_key"],
        inject_delay_retry=False,
        inject_in_flight_leak=False,
        inject_probe_failure=True,
        expected_critical_alert=True,
        notes="Exercises retry backoff logic before recording definitive channel revocation failure."
    ),
    "in_flight_leak": ScenarioDefinition(
        id="in_flight_leak",
        code="C",
        name="Scenario C: In-Flight Operation Leak",
        category="Containment Defect",
        description="Simulates an operation starting prior to shutdown that crosses the shutdown cutoff and completes post-termination, testing containment enforcement.",
        expected_behavior="In-flight operation confirmed completed past shutdown cutoff (COMPLETED_AFTER_SHUTDOWN), classified as post-shutdown leak, residual risk elevated, critical alert raised.",
        target_channels=[],
        inject_revocation_failure=False,
        inject_delay_retry=False,
        inject_in_flight_leak=True,
        inject_probe_failure=False,
        expected_critical_alert=True,
        notes="Operation completion time strictly evaluated against shutdown kill cutoff."
    ),
    "iam_role_accessible": ScenarioDefinition(
        id="iam_role_accessible",
        code="D",
        name="Scenario D: IAM Role Remains Accessible",
        category="Cloud Identity Defect",
        description="Simulates IAM role access remaining usable after shutdown initiation due to propagation failure or policy detaching failure. Stays strictly within simulation.",
        expected_behavior="IAM role revocation attempt fails, independent liveness probe confirms IAM channel remains accessible, critical emergency alert triggered.",
        target_channels=["iam_role"],
        inject_revocation_failure=True,
        failed_channels=["iam_role"],
        inject_delay_retry=False,
        inject_in_flight_leak=False,
        inject_probe_failure=True,
        expected_critical_alert=True,
        notes="Strict simulation boundary: does not touch real AWS or cloud IAM roles."
    ),
    "multiple_failures": ScenarioDefinition(
        id="multiple_failures",
        code="E",
        name="Scenario E: Multiple Simultaneous Failures",
        category="Compound Catastrophic",
        description="Simulates concurrent failure conditions: an access credential failure, an IAM role remaining accessible, and an in-flight operation completing past cutoff.",
        expected_behavior="Multiple failures processed concurrently, each failure recorded separately, risk calculated without double-counting, consolidated critical emergency alert raised.",
        target_channels=["api_key", "iam_role"],
        inject_revocation_failure=True,
        failed_channels=["api_key", "iam_role"],
        inject_delay_retry=False,
        inject_in_flight_leak=True,
        inject_probe_failure=True,
        expected_critical_alert=True,
        notes="Consolidated incident alert while preserving individual event telemetry."
    ),
    "delayed_revocation": ScenarioDefinition(
        id="delayed_revocation",
        code="F",
        name="Scenario F: Delayed but Successful Revocation",
        category="Transient Delay Recovery",
        description="Simulates an access channel experiencing transient latency or first-attempt retry, but successfully revoking on subsequent retry before deadline.",
        expected_behavior="Delay and retries recorded, channel status successfully reaches REVOKED, verification confirms zero persistent access, NO critical persistent-access alert raised.",
        target_channels=["session_token", "iam_role"],
        inject_revocation_failure=False,
        inject_delay_retry=True,
        delayed_channels=["session_token", "iam_role"],
        inject_in_flight_leak=False,
        inject_probe_failure=False,
        expected_critical_alert=False,
        notes="Distinguishes temporary recoverable delay from confirmed security failure."
    ),
}

def get_scenario(scenario_id: Optional[str]) -> Optional[ScenarioDefinition]:
    if not scenario_id:
        return None
    key = str(scenario_id).strip().lower()
    return SCENARIOS.get(key)

def validate_scenario_id(scenario_id: Optional[str]) -> tuple[bool, Optional[str]]:
    if not scenario_id:
        return True, None
    key = str(scenario_id).strip().lower()
    if key in SCENARIOS:
        return True, None
    valid_ids = ", ".join(SCENARIOS.keys())
    return False, f"Invalid scenario '{scenario_id}'. Must be one of: {valid_ids}"

def list_scenarios() -> List[Dict[str, Any]]:
    return [s.model_dump() for s in SCENARIOS.values()]
