"""EduBoost SA — Auth Router"""
from datetime import datetime, timedelta
import hashlib
import uuid

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.hash import bcrypt
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, text

from app.api.core.config import settings
from app.api.core.database import AsyncSessionFactory
from app.api.models.api_models import (
    ErrorResponse,
    GuardianLoginRequest,
    LearnerSessionRequest,
    LearnerSessionResponse,
    TokenResponse,
)
from app.api.models.db_models import ParentAccount, ParentLearnerLink

log = structlog.get_logger()
router = APIRouter()

# Rate limiter for auth endpoints (stricter: 10 req/min)
limiter = Limiter(key_func=get_remote_address)
bearer_scheme = HTTPBearer(auto_error=False)


# ── Shared JWT helpers ─────────────────────────────────────────────────────────

def _create_token(data: dict) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRY_HOURS)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """FastAPI dependency: extract and validate the current user from Bearer token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _decode_token(credentials.credentials)


async def require_role(role: str):
    """Factory for role-specific dependencies."""
    async def _guard(user: dict = Depends(get_current_user)):
        if user.get("role") != role:
            raise HTTPException(
                status_code=403,
                detail=f"This endpoint requires the '{role}' role",
            )
        return user
    return _guard


# ── Guardian verification (legacy email-hash check) ───────────────────────────

async def _verify_guardian(email: str, learner_pseudonym_id: str) -> bool:
    email_hash = hashlib.sha256(email.lower().strip().encode()).hexdigest()
    try:
        async with AsyncSessionFactory() as session:
            # 1. Find parent account by email hash
            result = await session.execute(
                select(ParentAccount).where(ParentAccount.email_encrypted == email_hash)
            )
            parent = result.scalar_one_or_none()
            if not parent:
                log.warning("auth.guardian.account_not_found", email_hash=email_hash)
                return False
            
            # 2. Check for direct link to this learner
            link_result = await session.execute(
                select(ParentLearnerLink).where(
                    ParentLearnerLink.parent_id == parent.parent_id,
                    ParentLearnerLink.learner_id == uuid.UUID(learner_pseudonym_id)
                )
            )
            if link_result.first() is None:
                log.warning("auth.guardian.no_link_found", parent_id=str(parent.parent_id), learner_id=learner_pseudonym_id)
                return False
            
        return True
    except Exception as e:
        log.error("auth.guardian.db_error", error=str(e))
        return False


# ── Request Models ─────────────────────────────────────────────────────────────

class GuardianRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)


class LinkLearnerRequest(BaseModel):
    learner_id: str
    relationship: str = Field(default="guardian", pattern="^(guardian|parent|grandparent)$")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post(
    "/guardian/register",
    status_code=status.HTTP_201_CREATED,
    response_model=TokenResponse,
    responses={409: {"model": ErrorResponse}},
)
@limiter.limit("5/minute")
async def register_guardian(request: Request, body: GuardianRegisterRequest):
    """Register a new guardian account. Returns a JWT immediately."""
    email_lower = body.email.lower().strip()
    email_encrypted = hashlib.sha256(email_lower.encode()).hexdigest()  # Placeholder for real encryption

    async with AsyncSessionFactory() as session:
        # Check for duplicate
        existing = await session.execute(
            select(ParentAccount).where(ParentAccount.email_encrypted == email_encrypted)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error="A guardian account with this email already exists",
                    code="GUARDIAN_EXISTS",
                ).model_dump(),
            )

        parent = ParentAccount(
            parent_id=uuid.uuid4(),
            email_encrypted=email_encrypted,
            password_hash=bcrypt.hash(body.password),
            full_name_encrypted=body.full_name,  # Placeholder for real encryption
            is_verified=False,
        )
        session.add(parent)
        await session.commit()
        log.info("auth.guardian.registered", parent_id=str(parent.parent_id))

    token = _create_token({
        "sub": str(parent.parent_id),
        "email_hash": email_encrypted,
        "role": "guardian",
    })
    return TokenResponse(access_token=token, expires_in=settings.JWT_EXPIRY_HOURS * 3600)


@router.post(
    "/guardian/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
@limiter.limit("10/minute")
async def guardian_login(request: Request, request_body: GuardianLoginRequest):
    """Login with email + optional learner pseudonym verification."""
    email_lower = request_body.email.lower().strip()
    email_encrypted = hashlib.sha256(email_lower.encode()).hexdigest()

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(ParentAccount).where(ParentAccount.email_encrypted == email_encrypted)
        )
        parent = result.scalar_one_or_none()

    if parent and hasattr(request_body, "password") and request_body.password:
        # Full password-based login
        if not bcrypt.verify(request_body.password, parent.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = _create_token({
            "sub": str(parent.parent_id),
            "email_hash": email_encrypted,
            "role": "guardian",
        })
        return TokenResponse(access_token=token, expires_in=settings.JWT_EXPIRY_HOURS * 3600)

    # Fallback: legacy pseudonym-based verification
    if not await _verify_guardian(request_body.email, request_body.learner_pseudonym_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(error="Invalid guardian credentials", code="INVALID_GUARDIAN_CREDENTIALS").model_dump(),
        )

    email_hash = hashlib.sha256(request_body.email.lower().strip().encode()).hexdigest()
    token = _create_token({"sub": email_hash, "learner_id": request_body.learner_pseudonym_id, "role": "guardian"})
    return TokenResponse(access_token=token, expires_in=settings.JWT_EXPIRY_HOURS * 3600)


@router.post("/guardian/link-learner", status_code=status.HTTP_201_CREATED)
async def link_learner(
    body: LinkLearnerRequest,
    user: dict = Depends(get_current_user),
):
    """Link a guardian account to a learner profile."""
    if user.get("role") != "guardian":
        raise HTTPException(status_code=403, detail="Only guardians can link learners")

    parent_id = user.get("sub")
    async with AsyncSessionFactory() as session:
        # Check for existing link
        existing = await session.execute(
            select(ParentLearnerLink).where(
                ParentLearnerLink.parent_id == uuid.UUID(parent_id),
                ParentLearnerLink.learner_id == uuid.UUID(body.learner_id),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Learner already linked to this guardian")

        link = ParentLearnerLink(
            link_id=uuid.uuid4(),
            parent_id=uuid.UUID(parent_id),
            learner_id=uuid.UUID(body.learner_id),
            relationship=body.relationship,
            is_verified=False,
        )
        session.add(link)
        await session.commit()
        log.info("auth.guardian.linked", parent_id=parent_id, learner_id=body.learner_id)

    return {
        "success": True,
        "link_id": str(link.link_id),
        "message": f"Learner {body.learner_id} linked. Pending verification.",
    }


@router.get("/guardian/linked-learners")
async def get_linked_learners(user: dict = Depends(get_current_user)):
    """List all learners linked to the authenticated guardian."""
    if user.get("role") != "guardian":
        raise HTTPException(status_code=403, detail="Only guardians can view linked learners")

    parent_id = user.get("sub")
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("""
                SELECT pll.link_id, pll.learner_id, pll.relationship,
                       pll.is_verified, pll.created_at,
                       l.grade, l.total_xp, l.streak_days
                FROM parent_learner_links pll
                JOIN learners l ON pll.learner_id = l.learner_id
                WHERE pll.parent_id = :parent_id
                ORDER BY pll.created_at DESC
            """),
            {"parent_id": parent_id},
        )
        rows = [dict(r) for r in result.mappings().all()]

    return {"parent_id": parent_id, "linked_learners": rows, "count": len(rows)}


@router.post("/learner/session", response_model=LearnerSessionResponse)
@limiter.limit("10/minute")
async def create_learner_session(request: Request, request_body: LearnerSessionRequest):
    token = _create_token({"sub": request_body.learner_id, "role": "learner"})
    return LearnerSessionResponse(session_token=token, expires_in=settings.JWT_EXPIRY_HOURS * 3600)

