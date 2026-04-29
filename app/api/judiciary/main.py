"""
PILLAR 3 — JUDICIARY (Microservice)
Separate FastAPI application deployed as judiciary-svc.
Network-isolated: workers cannot call LLM providers without routing through here.
Architectural recommendation #1: judiciary as network-isolated sidecar.
"""
from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app

from .models import JudiciaryStamp, StampVerdict
from .service import JudiciaryService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
judiciary_reviews_total = Counter(
    "judiciary_reviews_total",
    "Total Judiciary reviews",
    ["verdict"],
)
judiciary_review_latency = Histogram(
    "judiciary_review_latency_seconds",
    "Latency of Judiciary review calls",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="EduBoost Judiciary Service",
    description="Constitutional compliance firewall for all ExecutiveActions",
    version="1.0.0",
    docs_url="/docs" if os.environ.get("APP_ENV") != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],  # No browser access — worker-to-worker only
    allow_methods=["POST", "GET"],
    allow_headers=["X-Judiciary-API-Key", "Content-Type"],
)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------
JUDICIARY_API_KEY = os.environ.get("JUDICIARY_API_KEY", "")


def verify_api_key(x_judiciary_api_key: str = Header(...)) -> None:
    if not JUDICIARY_API_KEY:
        raise RuntimeError("JUDICIARY_API_KEY is not configured.")
    if x_judiciary_api_key != JUDICIARY_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Judiciary API key.",
        )


# ---------------------------------------------------------------------------
# Dependency: JudiciaryService
# ---------------------------------------------------------------------------
async def get_judiciary_service() -> JudiciaryService:
    """Create a JudiciaryService instance with its own DB session."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine(os.environ["JUDICIARY_DATABASE_URL"], echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield JudiciaryService(session=session)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
from .models import ExecutiveActionIn  # noqa: E402 — after app creation


@app.post(
    "/review",
    response_model=JudiciaryStamp,
    summary="Review an ExecutiveAction and return a stamp",
    dependencies=[Depends(verify_api_key)],
)
async def review_action(
    action: ExecutiveActionIn,
    service: JudiciaryService = Depends(get_judiciary_service),
) -> JudiciaryStamp:
    import time

    start = time.perf_counter()
    try:
        stamp = await service.review(action)
        verdict_label = stamp.verdict.value
        judiciary_reviews_total.labels(verdict=verdict_label).inc()
        return stamp
    except Exception as exc:
        logger.error("Judiciary review error: %s", exc)
        judiciary_reviews_total.labels(verdict="ERROR").inc()
        raise HTTPException(status_code=500, detail="Internal judiciary error") from exc
    finally:
        judiciary_review_latency.observe(time.perf_counter() - start)


@app.get("/health", summary="Health check")
async def health() -> dict:
    return {"status": "ok", "service": "judiciary-svc"}


@app.get(
    "/stamps/{action_id}",
    response_model=JudiciaryStamp,
    summary="Retrieve stamp for a given action_id",
    dependencies=[Depends(verify_api_key)],
)
async def get_stamp(
    action_id: str,
    service: JudiciaryService = Depends(get_judiciary_service),
) -> JudiciaryStamp:
    stamp = await service.get_stamp(action_id)
    if stamp is None:
        raise HTTPException(status_code=404, detail="Stamp not found")
    return stamp
