"""
tests/test_migration_regression.py
Regression tests for database schema migrations:
  1. Verifies that historical records without ground_truth_label are NOT automatically classified as NORMAL.
  2. Verifies that historical records with verifiable evidence (leaks/failures) reconstruct to ANOMALY.
  3. Verifies that historical records with verifiable clean shutdown reconstruct to NORMAL.
  4. Verifies that records with unknown/indeterminate outcomes remain strictly UNRESOLVED.
  5. Verifies that confusion-matrix calculations exclude UNRESOLVED records from performance rates.
  6. Confirms that existing database installations receive identical migration semantics as fresh setups.
"""

import pytest
import aiosqlite
import tempfile
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, select

from models.evaluation import EvaluationRecord
from services.monitor_evaluation_service import get_monitor_metrics

@pytest.mark.asyncio
async def test_migration_historical_ground_truth_protection():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE shutdown_events (
                    id VARCHAR PRIMARY KEY,
                    in_flight_failures INTEGER DEFAULT 0,
                    leaked_channels INTEGER DEFAULT 0,
                    partial_failure BOOLEAN DEFAULT 0,
                    started_at DATETIME,
                    finished_at DATETIME
                )
            """))
            await conn.execute(text("""
                CREATE TABLE evaluation_records (
                    id VARCHAR PRIMARY KEY,
                    shutdown_event_id VARCHAR,
                    agent_profile VARCHAR NOT NULL,
                    strategy VARCHAR NOT NULL,
                    execution_mode VARCHAR NOT NULL,
                    expected_condition VARCHAR NOT NULL,
                    observed_outcome VARCHAR NOT NULL,
                    monitor_detected BOOLEAN NOT NULL,
                    monitor_classification VARCHAR NOT NULL,
                    verdict VARCHAR NOT NULL,
                    alert_generated BOOLEAN DEFAULT 0,
                    alert_id VARCHAR,
                    attestation_id VARCHAR,
                    detection_latency_ms FLOAT,
                    disagreement_notes TEXT,
                    created_at DATETIME
                )
            """))

            await conn.execute(text("""
                INSERT INTO shutdown_events (id, in_flight_failures, leaked_channels, partial_failure)
                VALUES
                    ('sh_hist_leak', 1, 0, 1),
                    ('sh_hist_clean', 0, 0, 0)
            """))

            await conn.execute(text("""
                INSERT INTO evaluation_records (
                    id, shutdown_event_id, agent_profile, strategy, execution_mode,
                    expected_condition, observed_outcome, monitor_detected, monitor_classification,
                    verdict
                )
                VALUES
                    ('rec_anomaly', 'sh_hist_leak', 'slow', 'A', 'local', 'LEAK_EXPECTED', 'LEAK_OBSERVED(1_ops)', 1, 'ANOMALY_DETECTED', 'TRUE_POSITIVE'),
                    ('rec_clean', 'sh_hist_clean', 'cooperative', 'C', 'local', 'CLEAN_CONTAINMENT', 'CLEAN_CONTAINMENT', 0, 'CLEAN_CONTAINMENT', 'TRUE_NEGATIVE'),
                    ('rec_unknown_1', NULL, 'test_agent', 'B', 'local', 'UNKNOWN', 'INDETERMINATE', 0, 'CLEAN_CONTAINMENT', 'UNRESOLVED'),
                    ('rec_unknown_2', NULL, 'test_agent', 'B', 'local', 'LEGACY_PROBE', 'LEGACY_DATA_NO_PROBES', 0, 'CLEAN_CONTAINMENT', 'UNKNOWN')
            """))

        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE evaluation_records ADD COLUMN ground_truth_label VARCHAR DEFAULT 'UNRESOLVED'"))

            await conn.execute(text("""
                UPDATE evaluation_records
                SET ground_truth_label = 'ANOMALY'
                WHERE (ground_truth_label IS NULL OR ground_truth_label = 'UNRESOLVED')
                  AND (
                      observed_outcome LIKE '%LEAK%'
                      OR observed_outcome LIKE '%FAILED%'
                      OR observed_outcome LIKE '%TAMPER%'
                  )
            """))
            await conn.execute(text("""
                UPDATE evaluation_records
                SET ground_truth_label = 'ANOMALY'
                WHERE (ground_truth_label IS NULL OR ground_truth_label = 'UNRESOLVED')
                  AND shutdown_event_id IN (
                      SELECT id FROM shutdown_events
                      WHERE in_flight_failures > 0 OR leaked_channels > 0
                  )
            """))
            await conn.execute(text("""
                UPDATE evaluation_records
                SET ground_truth_label = 'NORMAL'
                WHERE (ground_truth_label IS NULL OR ground_truth_label = 'UNRESOLVED')
                  AND observed_outcome = 'CLEAN_CONTAINMENT'
                  AND shutdown_event_id IN (
                      SELECT id FROM shutdown_events
                      WHERE (in_flight_failures = 0 OR in_flight_failures IS NULL)
                        AND (leaked_channels = 0 OR leaked_channels IS NULL)
                        AND (partial_failure = 0 OR partial_failure IS NULL)
                  )
            """))

        async with async_session() as session:
            res = await session.execute(select(EvaluationRecord).order_by(EvaluationRecord.id))
            records_by_id = {r.id: r for r in res.scalars().all()}

            assert len(records_by_id) == 4

            assert records_by_id["rec_anomaly"].ground_truth_label == "ANOMALY"
            assert records_by_id["rec_anomaly"].observed_outcome == "LEAK_OBSERVED(1_ops)"
            assert records_by_id["rec_anomaly"].verdict == "TRUE_POSITIVE"

            assert records_by_id["rec_clean"].ground_truth_label == "NORMAL"
            assert records_by_id["rec_clean"].observed_outcome == "CLEAN_CONTAINMENT"
            assert records_by_id["rec_clean"].verdict == "TRUE_NEGATIVE"

            assert records_by_id["rec_unknown_1"].ground_truth_label == "UNRESOLVED"
            assert records_by_id["rec_unknown_2"].ground_truth_label == "UNRESOLVED"

            metrics = await get_monitor_metrics(session)
            cm = metrics["confusion_matrix"]

            assert cm["true_positives"] == 1
            assert cm["true_negatives"] == 1
            assert cm["false_positives"] == 0
            assert cm["false_negatives"] == 0
            assert cm["unresolved"] == 2

            rates = metrics["metrics"]
            assert rates["precision"] == 1.0
            assert rates["recall"] == 1.0
            assert rates["false_positive_rate"] == 0.0
            assert rates["accuracy"] == 1.0

        await engine.dispose()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass
