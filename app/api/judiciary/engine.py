"""
IRT ENGINE — Drift Monitoring & Model Versioning
Architectural recommendation #8:
  - Per-item parameters stored with version numbers (never mutate in place)
  - Celery beat drift detection task
  - joblib serialisation → R2 with content-hash naming
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
irt_theta_drift = Gauge(
    "irt_theta_drift_std", "Standard deviation of learner theta distribution shift"
)
irt_item_params_updated = Counter(
    "irt_item_params_updated_total", "IRT item parameter update events", ["item_id"]
)
irt_scoring_latency = Histogram(
    "irt_scoring_latency_seconds", "IRT response scoring latency"
)

# Drift alert thresholds
THETA_DRIFT_ALERT_STD = float(os.environ.get("IRT_THETA_DRIFT_ALERT_STD", "0.5"))
DRIFT_LOOKBACK_DAYS = int(os.environ.get("IRT_DRIFT_LOOKBACK_DAYS", "7"))


# ---------------------------------------------------------------------------
# IRT 3PL Model
# ---------------------------------------------------------------------------
class IRTItem:
    """3-Parameter Logistic item model."""

    def __init__(self, item_id: str, a: float = 1.0, b: float = 0.0, c: float = 0.25):
        self.item_id = item_id
        self.a = a   # discrimination
        self.b = b   # difficulty
        self.c = c   # guessing

    def probability(self, theta: float) -> float:
        """P(correct | theta) using 3PL model."""
        exponent = -1.702 * self.a * (theta - self.b)
        return self.c + (1.0 - self.c) / (1.0 + np.exp(exponent))


class IRTEngine:
    """
    IRT-based adaptive scoring engine.
    All parameter updates create new versioned rows — never mutate existing rows.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    async def score_response(
        self,
        learner_pseudonym: str,
        item_id: str,
        correct: bool,
        response_time_ms: int,
    ) -> float:
        """
        Update learner theta estimate using EAP (Expected A Posteriori).
        Returns updated theta.
        """
        import time
        t0 = time.perf_counter()

        params = await self._get_item_params(item_id)
        item = IRTItem(item_id=item_id, a=params["a"], b=params["b"], c=params["c"])

        current_theta = await self._get_learner_theta(learner_pseudonym)
        updated_theta = self._eap_update(current_theta, item, correct)

        await self._persist_response(learner_pseudonym, item_id, correct, updated_theta, response_time_ms)

        irt_scoring_latency.observe(time.perf_counter() - t0)
        return updated_theta

    def _eap_update(
        self, theta: float, item: IRTItem, correct: bool, step: float = 0.3
    ) -> float:
        """Simple gradient-step approximation of EAP update."""
        p = item.probability(theta)
        residual = (1.0 if correct else 0.0) - p
        return round(theta + step * residual * item.a, 4)

    # ------------------------------------------------------------------
    # Parameter versioning
    # ------------------------------------------------------------------
    async def update_item_params(
        self,
        item_id: str,
        a: float,
        b: float,
        c: float,
        calibration_source: str = "auto",
    ) -> int:
        """
        Insert a new parameter row (increments version). Never updates existing rows.
        Returns the new version number.
        """
        row = (
            await self._session.execute(
                text(
                    "SELECT COALESCE(MAX(version), 0) AS v FROM irt_item_parameters WHERE item_id = :id"
                ),
                {"id": item_id},
            )
        ).first()
        new_version = (row[0] or 0) + 1

        await self._session.execute(
            text(
                """
                INSERT INTO irt_item_parameters
                    (item_id, version, a, b, c, calibration_source, created_at)
                VALUES (:item_id, :v, :a, :b, :c, :src, now())
                """
            ),
            {
                "item_id": item_id,
                "v": new_version,
                "a": a,
                "b": b,
                "c": c,
                "src": calibration_source,
            },
        )
        await self._session.commit()
        irt_item_params_updated.labels(item_id=item_id).inc()
        return new_version

    async def _get_item_params(self, item_id: str) -> Dict[str, float]:
        row = (
            await self._session.execute(
                text(
                    """
                    SELECT a, b, c FROM irt_item_parameters
                    WHERE item_id = :id ORDER BY version DESC LIMIT 1
                    """
                ),
                {"id": item_id},
            )
        ).first()
        return {"a": row[0], "b": row[1], "c": row[2]} if row else {"a": 1.0, "b": 0.0, "c": 0.25}

    async def _get_learner_theta(self, learner_pseudonym: str) -> float:
        row = (
            await self._session.execute(
                text(
                    "SELECT theta FROM irt_learner_estimates WHERE learner_pseudonym = :p "
                    "ORDER BY updated_at DESC LIMIT 1"
                ),
                {"p": learner_pseudonym},
            )
        ).first()
        return float(row[0]) if row else 0.0

    async def _persist_response(
        self,
        pseudonym: str,
        item_id: str,
        correct: bool,
        updated_theta: float,
        response_time_ms: int,
    ) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO irt_responses
                    (learner_pseudonym, item_id, correct, updated_theta, response_time_ms, responded_at)
                VALUES (:p, :item, :correct, :theta, :rt, now())
                """
            ),
            {
                "p": pseudonym,
                "item": item_id,
                "correct": correct,
                "theta": updated_theta,
                "rt": response_time_ms,
            },
        )
        await self._session.execute(
            text(
                """
                INSERT INTO irt_learner_estimates (learner_pseudonym, theta, updated_at)
                VALUES (:p, :theta, now())
                ON CONFLICT (learner_pseudonym) DO UPDATE
                SET theta = EXCLUDED.theta, updated_at = now()
                """
            ),
            {"p": pseudonym, "theta": updated_theta},
        )
        await self._session.commit()


# ---------------------------------------------------------------------------
# Drift Detection — run as Celery beat task, nightly
# ---------------------------------------------------------------------------
class IRTDriftMonitor:
    """
    Nightly drift detection over the learner theta and item parameter distributions.
    Publishes metrics to Prometheus and alerts if drift exceeds thresholds.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(self) -> Dict[str, Any]:
        theta_report = await self._check_theta_drift()
        param_report = await self._check_item_param_drift()
        await self._serialise_model_snapshot()
        return {"theta": theta_report, "items": param_report}

    async def _check_theta_drift(self) -> Dict[str, Any]:
        rows = (
            await self._session.execute(
                text(
                    f"""
                    SELECT theta FROM irt_learner_estimates
                    WHERE updated_at > now() - interval '{DRIFT_LOOKBACK_DAYS} days'
                    """
                )
            )
        ).scalars().all()

        if len(rows) < 10:
            return {"status": "insufficient_data", "count": len(rows)}

        thetas = np.array(rows, dtype=float)
        mean = float(np.mean(thetas))
        std = float(np.std(thetas))
        irt_theta_drift.set(std)

        if std > THETA_DRIFT_ALERT_STD:
            logger.warning(
                "IRT THETA DRIFT ALERT: std=%.3f (threshold=%.3f) mean=%.3f n=%d",
                std, THETA_DRIFT_ALERT_STD, mean, len(rows)
            )

        return {"mean": round(mean, 4), "std": round(std, 4), "n": len(rows), "alert": std > THETA_DRIFT_ALERT_STD}

    async def _check_item_param_drift(self) -> Dict[str, Any]:
        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT item_id, AVG(a) AS avg_a, STDDEV(b) AS std_b
                    FROM irt_item_parameters
                    WHERE created_at > now() - interval '30 days'
                    GROUP BY item_id
                    HAVING COUNT(*) > 1
                    """
                )
            )
        ).mappings().all()

        drifting = []
        for row in rows:
            if row["std_b"] and float(row["std_b"]) > 1.0:
                drifting.append({"item_id": row["item_id"], "std_b": round(float(row["std_b"]), 3)})

        return {"drifting_items": drifting, "total_monitored": len(rows)}

    async def _serialise_model_snapshot(self) -> Optional[str]:
        """Serialise current item parameters to joblib, upload to R2 with content hash."""
        try:
            rows = (
                await self._session.execute(
                    text(
                        """
                        SELECT DISTINCT ON (item_id)
                            item_id, version, a, b, c
                        FROM irt_item_parameters
                        ORDER BY item_id, version DESC
                        """
                    )
                )
            ).mappings().all()

            snapshot = {row["item_id"]: {"a": row["a"], "b": row["b"], "c": row["c"], "version": row["version"]} for row in rows}
            buf = io.BytesIO()
            joblib.dump(snapshot, buf)
            buf.seek(0)
            content = buf.read()
            content_hash = hashlib.sha256(content).hexdigest()[:16]
            key = f"irt_snapshots/params_{content_hash}.joblib"

            import boto3
            s3 = boto3.client(
                "s3",
                endpoint_url=os.environ.get("R2_ENDPOINT_URL"),
                aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
            )
            s3.put_object(Bucket=os.environ.get("R2_BUCKET", "eduboost-assets"), Key=key, Body=content)
            logger.info("IRT model snapshot uploaded: %s", key)
            return key
        except Exception as exc:
            logger.error("IRT snapshot serialisation failed: %s", exc)
            return None
