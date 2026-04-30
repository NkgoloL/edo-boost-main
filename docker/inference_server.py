"""
docker/inference_server.py
──────────────────────────
[IMMEDIATE FIX 3] Lightweight FastAPI micro-service that exposes offline
HuggingFace / PyTorch inference over HTTP.

The main EduBoost API calls this service via INFERENCE_SERVICE_URL when
the primary (Groq) and secondary (Anthropic) LLM providers are unavailable,
or when a fully-offline deployment is required (e.g. school servers with no
internet access).

Endpoints
─────────
GET  /health          — liveness probe
POST /generate        — text generation (lesson content)
POST /classify        — zero-shot classification (topic / grade tagging)
POST /embed           — sentence embeddings (semantic similarity for IRT)
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
log = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
MODEL_NAME: str = os.getenv("OFFLINE_MODEL_NAME", "google/flan-t5-base")
DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"
MAX_NEW_TOKENS: int = int(os.getenv("MAX_NEW_TOKENS", "512"))

# ─────────────────────────────────────────────────────────────────────────────
# Model registry — loaded once at startup, kept in memory
# ─────────────────────────────────────────────────────────────────────────────
_models: dict[str, Any] = {}


def _load_models() -> None:
    log.info("inference.loading_models", model=MODEL_NAME, device=DEVICE)
    t0 = time.perf_counter()

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        MODEL_NAME,
        device_map="auto" if DEVICE == "cuda" else None,
        torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
    )
    if DEVICE == "cpu":
        model = model.to(DEVICE)
    model.eval()

    _models["tokenizer"] = tokenizer
    _models["model"] = model
    _models["generator"] = pipeline(
        "text2text-generation",
        model=model,
        tokenizer=tokenizer,
        device=0 if DEVICE == "cuda" else -1,
    )

    elapsed = time.perf_counter() - t0
    log.info("inference.models_ready", elapsed_s=round(elapsed, 2))


# ─────────────────────────────────────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_models()
    yield
    _models.clear()
    log.info("inference.shutdown")


app = FastAPI(
    title="EduBoost Inference Service",
    version="0.1.0",
    description="Offline HuggingFace inference for EduBoost SA",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# Request / response schemas
# ─────────────────────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4096)
    max_new_tokens: int = Field(default=256, ge=16, le=1024)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    grade: str | None = Field(default=None, description="SA grade level (R–7)")
    subject: str | None = Field(default=None, description="CAPS subject area")


class GenerateResponse(BaseModel):
    text: str
    model: str
    device: str
    latency_ms: float


class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2048)
    candidate_labels: list[str] = Field(..., min_length=2, max_length=20)


class ClassifyResponse(BaseModel):
    label: str
    score: float
    all_scores: dict[str, float]


class EmbedRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=64)


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]
    dimension: int


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "device": DEVICE,
        "models_loaded": bool(_models),
    }


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    """Generate lesson text using the offline model."""
    if not _models:
        raise HTTPException(status_code=503, detail="Models not yet loaded")

    # Enrich prompt with CAPS context when grade/subject provided
    prompt = req.prompt
    if req.grade or req.subject:
        ctx_parts = []
        if req.grade:
            ctx_parts.append(f"Grade: {req.grade}")
        if req.subject:
            ctx_parts.append(f"Subject: {req.subject}")
        prompt = f"[Context: South African CAPS curriculum. {', '.join(ctx_parts)}]\n\n{prompt}"

    t0 = time.perf_counter()
    try:
        outputs = _models["generator"](
            prompt,
            max_new_tokens=req.max_new_tokens,
            do_sample=req.temperature > 0,
            temperature=req.temperature if req.temperature > 0 else None,
        )
        result_text: str = outputs[0]["generated_text"]
    except Exception as exc:
        log.error("inference.generate_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}") from exc

    latency_ms = (time.perf_counter() - t0) * 1000
    log.info("inference.generated", latency_ms=round(latency_ms, 1), tokens=req.max_new_tokens)

    return GenerateResponse(
        text=result_text,
        model=MODEL_NAME,
        device=DEVICE,
        latency_ms=round(latency_ms, 1),
    )


@app.post("/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest) -> ClassifyResponse:
    """Zero-shot classification — used for topic/grade tagging."""
    if not _models:
        raise HTTPException(status_code=503, detail="Models not yet loaded")

    # Build a simple entailment-style prompt for seq2seq models
    scores: dict[str, float] = {}
    tokenizer = _models["tokenizer"]
    model = _models["model"]

    for label in req.candidate_labels:
        prompt = f"Does the following text relate to '{label}'? Answer yes or no.\n\nText: {req.text}"
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=4)
        answer = tokenizer.decode(out[0], skip_special_tokens=True).lower().strip()
        scores[label] = 1.0 if answer.startswith("yes") else 0.0

    # Softmax-style normalisation
    total = sum(scores.values()) or 1.0
    normalised = {k: round(v / total, 4) for k, v in scores.items()}
    best_label = max(normalised, key=lambda k: normalised[k])

    return ClassifyResponse(label=best_label, score=normalised[best_label], all_scores=normalised)


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    """Generate sentence embeddings for semantic similarity (IRT feature extraction)."""
    if not _models:
        raise HTTPException(status_code=503, detail="Models not yet loaded")

    tokenizer = _models["tokenizer"]
    model = _models["model"]
    embeddings = []

    for text in req.texts:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256, padding=True)
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        with torch.no_grad():
            encoder_out = model.encoder(**inputs)
            # Mean-pool over token dimension
            hidden = encoder_out.last_hidden_state  # (1, seq_len, hidden)
            emb = hidden.mean(dim=1).squeeze(0).cpu().tolist()
        embeddings.append(emb)

    return EmbedResponse(embeddings=embeddings, dimension=len(embeddings[0]) if embeddings else 0)
