"""
PILLAR 1 — LEGISLATURE
LegislatureAgent: ingests CAPS/POPIA/SASA PDFs, embeds chunks, stores
ConstitutionalRule rows. Runs ONLY on policy-update events — never per request.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import AsyncGenerator, List, Optional

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ConstitutionalRule, ConstitutionalRuleORM, RuleSetSignatureORM, ScopeModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported source documents
# ---------------------------------------------------------------------------
KNOWN_SOURCES = {
    "POPIA": "Protection of Personal Information Act (4/2013)",
    "CAPS": "Curriculum and Assessment Policy Statement",
    "SASA": "South African Schools Act (84/1996)",
    "DBE-POLICY": "DBE Policy Documents",
}


# ---------------------------------------------------------------------------
# Simple chunker — replace with LangChain/LlamaIndex in production
# ---------------------------------------------------------------------------
def _chunk_text(text_: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    words = text_.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Embedding stub — wire to OpenAI text-embedding-3-small or sentence-transformers
# ---------------------------------------------------------------------------
async def _embed(texts: List[str]) -> List[List[float]]:
    """
    Production: replace with:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        resp = await client.embeddings.create(model="text-embedding-3-small", input=texts)
        return [d.embedding for d in resp.data]
    """
    import random
    return [[random.random() for _ in range(1536)] for _ in texts]


# ---------------------------------------------------------------------------
# Vector store stub — wire to pgvector / Qdrant / Weaviate
# ---------------------------------------------------------------------------
async def _upsert_vectors(
    source: str, chunks: List[str], embeddings: List[List[float]]
) -> None:
    """Upsert chunk embeddings into the vector store."""
    logger.info("Upserted %d vectors for source=%s (stub)", len(chunks), source)


# ---------------------------------------------------------------------------
# Hash-based change detection
# ---------------------------------------------------------------------------
def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Rule extraction stub — wire to an LLM extraction pipeline in production
# ---------------------------------------------------------------------------
async def _extract_rules_from_chunks(
    source_key: str, chunks: List[str], effective_date: date
) -> List[ConstitutionalRule]:
    """
    Production: send each chunk to an LLM with a structured extraction prompt.
    Returns ConstitutionalRule objects.  Stub returns one placeholder rule.
    """
    rules = []
    for i, chunk in enumerate(chunks[:5]):  # limit stub output
        rule_id = f"{source_key}-AUTO-{i:04d}"
        rules.append(
            ConstitutionalRule(
                rule_id=rule_id,
                source_document=KNOWN_SOURCES.get(source_key, source_key),
                rule_text=chunk[:500],
                scope=ScopeModel(subjects=[], grade_min=0, grade_max=12),
                effective_date=effective_date,
            )
        )
    return rules


# ---------------------------------------------------------------------------
# LegislatureAgent
# ---------------------------------------------------------------------------
@dataclass
class IngestionResult:
    source: str
    rules_inserted: int
    rules_skipped: int
    errors: List[str] = field(default_factory=list)


class LegislatureAgent:
    """
    Orchestrates policy-document ingestion into the constitutional_rules table.
    Must only be triggered by an admin or a hash-change detection event.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def refresh_source(
        self,
        source_key: str,
        document_path: Path,
        effective_date: date,
    ) -> IngestionResult:
        """
        Ingest a single policy document.
        1. Hash the file; skip if unchanged.
        2. Chunk and embed.
        3. Extract ConstitutionalRule objects.
        4. Persist only new rules (hash-deduplicated).
        """
        result = IngestionResult(source=source_key, rules_inserted=0, rules_skipped=0)

        if not document_path.exists():
            result.errors.append(f"Document not found: {document_path}")
            return result

        file_hash = _file_hash(document_path)
        if await self._is_unchanged(source_key, file_hash):
            logger.info("Source %s unchanged (hash=%s). Skipping.", source_key, file_hash[:12])
            return result

        text_content = document_path.read_text(errors="replace")
        chunks = _chunk_text(text_content)
        embeddings = await _embed(chunks)
        await _upsert_vectors(source_key, chunks, embeddings)

        rules = await _extract_rules_from_chunks(source_key, chunks, effective_date)
        for rule in rules:
            inserted = await self._persist_rule(rule)
            if inserted:
                result.rules_inserted += 1
            else:
                result.rules_skipped += 1

        await self._record_source_hash(source_key, file_hash)
        logger.info(
            "Legislature refresh: source=%s inserted=%d skipped=%d",
            source_key, result.rules_inserted, result.rules_skipped,
        )
        return result

    async def get_active_rules(
        self, grade: Optional[int] = None, subject: Optional[str] = None
    ) -> List[ConstitutionalRule]:
        """
        Retrieve the latest effective version of each rule, optionally filtered.
        Uses a window function so each rule_id returns only its most recent row.
        """
        stmt = text(
            """
            SELECT DISTINCT ON (rule_id)
                rule_id, source_document, rule_text,
                scope_subjects, scope_grade_min, scope_grade_max,
                effective_date, immutable_hash
            FROM constitutional_rules
            WHERE effective_date <= CURRENT_DATE
            ORDER BY rule_id, effective_date DESC
            """
        )
        rows = (await self._session.execute(stmt)).mappings().all()
        rules = []
        for row in rows:
            orm = ConstitutionalRuleORM(
                rule_id=row["rule_id"],
                source_document=row["source_document"],
                rule_text=row["rule_text"],
                scope_subjects=row["scope_subjects"],
                scope_grade_min=row["scope_grade_min"],
                scope_grade_max=row["scope_grade_max"],
                effective_date=row["effective_date"],
                immutable_hash=row["immutable_hash"],
            )
            rule = ConstitutionalRule.from_orm(orm)
            if grade is not None:
                scope = rule.scope
                if not (scope.grade_min <= grade <= scope.grade_max):
                    continue
            if subject is not None:
                if rule.scope.subjects and subject not in rule.scope.subjects:
                    continue
            rules.append(rule)
        return rules

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _is_unchanged(self, source_key: str, file_hash: str) -> bool:
        stmt = text(
            "SELECT 1 FROM legislature_source_hashes WHERE source_key = :sk AND file_hash = :fh"
        )
        row = (await self._session.execute(stmt, {"sk": source_key, "fh": file_hash})).first()
        return row is not None

    async def _record_source_hash(self, source_key: str, file_hash: str) -> None:
        stmt = text(
            """
            INSERT INTO legislature_source_hashes (source_key, file_hash, updated_at)
            VALUES (:sk, :fh, now())
            ON CONFLICT (source_key) DO UPDATE
              SET file_hash = EXCLUDED.file_hash, updated_at = EXCLUDED.updated_at
            """
        )
        await self._session.execute(stmt, {"sk": source_key, "fh": file_hash})
        await self._session.commit()

    async def _persist_rule(self, rule: ConstitutionalRule) -> bool:
        """Returns True if the rule was inserted, False if it already existed."""
        stmt = text(
            "SELECT 1 FROM constitutional_rules WHERE immutable_hash = :h"
        )
        exists = (await self._session.execute(stmt, {"h": rule.immutable_hash})).first()
        if exists:
            return False

        orm = ConstitutionalRuleORM(
            rule_id=rule.rule_id,
            source_document=rule.source_document,
            rule_text=rule.rule_text,
            scope_subjects=rule.scope.subjects or None,
            scope_grade_min=rule.scope.grade_min,
            scope_grade_max=rule.scope.grade_max,
            effective_date=rule.effective_date,
            immutable_hash=rule.immutable_hash,
        )
        self._session.add(orm)
        await self._session.commit()
        return True
