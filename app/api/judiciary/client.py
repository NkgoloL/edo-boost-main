"""
Judiciary HTTP client used by WorkerAgents to call the remote judiciary-svc.
Workers never review actions themselves — all reviews route through this client.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

from app.api.pillar_2_executive.base import ExecutiveAction, JudiciaryStampRef


class JudiciaryClient:
    """
    Thin HTTP client for the judiciary-svc microservice.
    Injects JUDICIARY_API_KEY header on every request.
    """

    BASE_URL = os.environ.get("JUDICIARY_SERVICE_URL", "http://judiciary-svc:8001")
    API_KEY = os.environ.get("JUDICIARY_API_KEY", "")
    TIMEOUT = float(os.environ.get("JUDICIARY_TIMEOUT_SECONDS", "10"))

    async def review(self, action: ExecutiveAction) -> JudiciaryStampRef:
        payload = action.model_dump(mode="json")
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.post(
                f"{self.BASE_URL}/review",
                json=payload,
                headers={"X-Judiciary-API-Key": self.API_KEY},
            )
        if response.status_code == 403:
            raise PermissionError("Invalid Judiciary API key.")
        response.raise_for_status()
        data = response.json()
        return JudiciaryStampRef(
            stamp_id=data["stamp_id"],
            action_id=data["action_id"],
            verdict=data["verdict"],
            rules_checked=data.get("rules_checked", []),
            reason=data.get("reason", ""),
            reviewer_model_version=data.get("reviewer_model_version", ""),
        )

    async def get_stamp(self, action_id: str) -> Optional[JudiciaryStampRef]:
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            response = await client.get(
                f"{self.BASE_URL}/stamps/{action_id}",
                headers={"X-Judiciary-API-Key": self.API_KEY},
            )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return JudiciaryStampRef(**data)
