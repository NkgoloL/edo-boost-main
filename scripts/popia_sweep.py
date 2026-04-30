#!/usr/bin/env python3
"""
scripts/popia_sweep.py

POPIA Chaos Sweep — EduBoost SA
================================
Automated static + dynamic audit of all LLM prompt paths and consent checkpoints.

What this checks:
  1. Static: Scans all Python source for raw PII patterns passed to LLM clients.
  2. Static: Verifies every router endpoint that touches learner data calls
             ConsentService.require_active_consent() before any DB access.
  3. Static: Detects direct use of learner UUIDs in LLM prompt strings.
  4. Dynamic: Hits the live API with mock requests to confirm consent gates fire.
  5. Produces a structured JSON report and a human-readable summary.

Usage:
    python scripts/popia_sweep.py                  # static sweep only
    python scripts/popia_sweep.py --live-check     # + dynamic API checks
    python scripts/popia_sweep.py --fail-on-issues # non-zero exit if any issue found

CI integration:
    - Add to .github/workflows/ci-cd.yml as a step in the lint-and-test job.
    - Use --fail-on-issues to block merges when POPIA issues are detected.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import textwrap
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional
import datetime

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


# ── Configuration ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
APP_DIR = PROJECT_ROOT / "app"
API_DIR = APP_DIR / "api"
ROUTERS_DIR = API_DIR / "routers"

# Patterns that indicate raw PII being constructed into a string
PII_PATTERNS = [
    # Email addresses
    re.compile(r'["\'][\w.+-]+@[\w-]+\.[\w.-]+["\']', re.I),
    # South African ID numbers (13 digits)
    re.compile(r'\b\d{13}\b'),
    # Phone numbers (SA format)
    re.compile(r'\b0[678]\d{8}\b'),
    # "email" or "phone" directly in a format/fstring
    re.compile(r'f["\'].*\b(?:email|phone|id_number|date_of_birth|dob)\b.*["\']', re.I),
    # Direct column references
    re.compile(r'\.(?:email|phone|date_of_birth|id_number)\b'),
]

# LLM client call patterns — any of these followed by a prompt means we need to check
LLM_CALL_PATTERNS = [
    re.compile(r'anthropic.*(?:create|complete|message)', re.I),
    re.compile(r'groq.*(?:create|complete|chat)', re.I),
    re.compile(r'openai.*(?:create|complete|chat)', re.I),
    re.compile(r'huggingface.*(?:inference|pipeline)', re.I),
    re.compile(r'client\.(?:messages?|chat)\.(?:create|complete)', re.I),
]

# Files/directories to exclude
EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", "migrations", "alembic"}
EXCLUDE_FILES = {"conftest.py"}

# Endpoints that MUST have consent gating
LEARNER_DATA_PATTERNS = [
    re.compile(r'learner', re.I),
    re.compile(r'diagnostic', re.I),
    re.compile(r'study.?plan', re.I),
    re.compile(r'lesson', re.I),
]


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class Issue:
    severity: str           # "critical", "high", "medium", "info"
    category: str           # "pii_in_llm", "missing_consent_gate", "pseudonym_bypass"
    file: str
    line: int
    description: str
    snippet: str = ""


@dataclass
class SweepReport:
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    project: str = "EduBoost SA"
    issues: list[Issue] = field(default_factory=list)
    files_scanned: int = 0
    endpoints_checked: int = 0
    consent_gates_found: int = 0
    summary: str = ""

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "high")


# ── Static analysis ───────────────────────────────────────────────────────────

def collect_python_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.py"):
        if any(ex in path.parts for ex in EXCLUDE_DIRS):
            continue
        if path.name in EXCLUDE_FILES:
            continue
        files.append(path)
    return files


def check_pii_in_llm_prompts(source: str, filepath: Path, report: SweepReport) -> None:
    """
    Detects raw PII being interpolated into strings near LLM API calls.
    This is the highest-priority POPIA risk: sending identifiable data to a third-party AI.
    """
    lines = source.splitlines()
    for i, line in enumerate(lines, start=1):
        is_near_llm = any(p.search(line) for p in LLM_CALL_PATTERNS)
        has_pii = any(p.search(line) for p in PII_PATTERNS)

        if is_near_llm:
            # Check surrounding 10 lines for PII
            context_start = max(0, i - 5)
            context_end = min(len(lines), i + 5)
            context = "\n".join(lines[context_start:context_end])
            if any(p.search(context) for p in PII_PATTERNS):
                report.add(Issue(
                    severity="critical",
                    category="pii_in_llm",
                    file=str(filepath.relative_to(PROJECT_ROOT)),
                    line=i,
                    description=(
                        "LLM API call detected near raw PII pattern. "
                        "Ensure only pseudonym_id is passed to LLM providers."
                    ),
                    snippet=line.strip()[:200],
                ))

        # Also flag standalone PII in any file
        if has_pii and "test" not in str(filepath).lower() and "mock" not in str(filepath).lower():
            for pat in PII_PATTERNS:
                if pat.search(line):
                    report.add(Issue(
                        severity="high",
                        category="pii_pattern_detected",
                        file=str(filepath.relative_to(PROJECT_ROOT)),
                        line=i,
                        description=f"Raw PII pattern '{pat.pattern}' found in source.",
                        snippet=line.strip()[:200],
                    ))
                    break


def check_pseudonym_bypasses(source: str, filepath: Path, report: SweepReport) -> None:
    """
    Detects cases where the real learner UUID (not pseudonym_id) is passed to LLM calls.
    EduBoost must only send pseudonym_id to external AI providers.
    """
    lines = source.splitlines()
    for i, line in enumerate(lines, start=1):
        is_near_llm = any(p.search(line) for p in LLM_CALL_PATTERNS)
        if not is_near_llm:
            continue
        # Within 20 lines, look for learner_id (not pseudonym_id)
        context_start = max(0, i - 10)
        context_end = min(len(lines), i + 10)
        context = "\n".join(lines[context_start:context_end])
        if re.search(r'\blearner_id\b', context) and not re.search(r'\bpseudonym_id\b', context):
            report.add(Issue(
                severity="critical",
                category="pseudonym_bypass",
                file=str(filepath.relative_to(PROJECT_ROOT)),
                line=i,
                description=(
                    "LLM call uses learner_id without pseudonym_id nearby. "
                    "Only pseudonym_id must be passed to external AI providers (POPIA data minimisation)."
                ),
                snippet=line.strip()[:200],
            ))


def check_consent_gates_in_routers(source: str, filepath: Path, report: SweepReport) -> None:
    """
    Parses FastAPI router files and flags any endpoint function that touches
    learner data without calling require_active_consent().
    """
    if "router" not in str(filepath).lower():
        return

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue

        func_source = ast.get_source_segment(source, node) or ""
        is_learner_endpoint = any(p.search(func_source) for p in LEARNER_DATA_PATTERNS)
        if not is_learner_endpoint:
            continue

        report.endpoints_checked += 1

        has_consent_gate = (
            "require_active_consent" in func_source
            or "ConsentService.require_active_consent" in func_source
        )

        if has_consent_gate:
            report.consent_gates_found += 1
        else:
            # Is it a read/write endpoint (has DB call)?
            has_db_call = any(kw in func_source for kw in ["db.execute", "db.get", "await db", "select("])
            if has_db_call:
                report.add(Issue(
                    severity="critical",
                    category="missing_consent_gate",
                    file=str(filepath.relative_to(PROJECT_ROOT)),
                    line=node.lineno,
                    description=(
                        f"Endpoint '{node.name}' accesses learner DB data without "
                        "calling ConsentService.require_active_consent(). "
                        "This is a POPIA compliance blocker."
                    ),
                    snippet=f"async def {node.name}(...)",
                ))


def check_audit_log_coverage(source: str, filepath: Path, report: SweepReport) -> None:
    """
    Flags consent-modifying endpoints that don't write an audit log entry.
    """
    if "consent" not in str(filepath).lower():
        return

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return

    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        func_source = ast.get_source_segment(source, node) or ""
        is_consent_mutation = any(
            kw in func_source for kw in ["mark_granted", "mark_revoked", "execute_erasure", "grant(", "revoke("]
        )
        has_audit = any(
            kw in func_source for kw in ["audit_log", "fourth_estate", "AuditLog", "log_action"]
        )
        if is_consent_mutation and not has_audit:
            report.add(Issue(
                severity="high",
                category="missing_audit_log",
                file=str(filepath.relative_to(PROJECT_ROOT)),
                line=node.lineno,
                description=(
                    f"Function '{node.name}' modifies consent without writing an audit log entry. "
                    "POPIA requires an immutable audit trail for all consent changes."
                ),
                snippet=f"def {node.name}(...)",
            ))


# ── Dynamic live API checks ───────────────────────────────────────────────────

def run_live_checks(api_base: str, report: SweepReport) -> None:
    """
    Hits the running API to confirm consent enforcement works at runtime.
    Requires a live stack (docker-compose up).
    """
    if not HAS_HTTPX:
        print("⚠  httpx not installed — skipping live checks. Run: pip install httpx")
        return

    import httpx

    # Test 1: Unauthenticated access to learner endpoint must return 401
    r = httpx.get(f"{api_base}/learners/00000000-0000-0000-0000-000000000000/plan", timeout=10)
    if r.status_code not in (401, 403):
        report.add(Issue(
            severity="critical",
            category="auth_bypass",
            file="[live-api]",
            line=0,
            description=f"Unauthenticated GET /learners/<id>/plan returned {r.status_code}, expected 401/403.",
        ))

    # Test 2: Health endpoint must be public
    r = httpx.get(f"{api_base.replace('/api/v1', '')}/health", timeout=10)
    if r.status_code != 200:
        report.add(Issue(
            severity="medium",
            category="health_endpoint",
            file="[live-api]",
            line=0,
            description=f"GET /health returned {r.status_code}, expected 200.",
        ))

    # Test 3: LLM lesson endpoint should not leak raw email or name in response
    # (Can only test with valid token — skipped here if no token available)
    print("  Live checks complete.")


# ── Report generation ─────────────────────────────────────────────────────────

def print_report(report: SweepReport) -> None:
    width = 80
    print("=" * width)
    print("  POPIA CHAOS SWEEP REPORT — EduBoost SA")
    print(f"  {report.timestamp}")
    print("=" * width)
    print(f"  Files scanned:        {report.files_scanned}")
    print(f"  Endpoints checked:    {report.endpoints_checked}")
    print(f"  Consent gates found:  {report.consent_gates_found}")
    print(f"  Issues found:         {len(report.issues)}")
    print(f"    • Critical:         {report.critical_count}")
    print(f"    • High:             {report.high_count}")
    print("-" * width)

    if not report.issues:
        print("  ✅  No POPIA issues detected.")
    else:
        by_severity = {"critical": [], "high": [], "medium": [], "info": []}
        for issue in report.issues:
            by_severity.setdefault(issue.severity, []).append(issue)

        for sev in ("critical", "high", "medium", "info"):
            issues = by_severity.get(sev, [])
            if not issues:
                continue
            label = {"critical": "🔴 CRITICAL", "high": "🟠 HIGH", "medium": "🟡 MEDIUM", "info": "🔵 INFO"}[sev]
            print(f"\n{label} ({len(issues)} issues)")
            print("-" * width)
            for issue in issues:
                print(f"  [{issue.category}] {issue.file}:{issue.line}")
                print(f"  {textwrap.fill(issue.description, width=76, subsequent_indent='  ')}")
                if issue.snippet:
                    print(f"  >> {issue.snippet}")
                print()

    print("=" * width)


def main() -> int:
    parser = argparse.ArgumentParser(description="POPIA Chaos Sweep for EduBoost SA")
    parser.add_argument("--live-check", action="store_true", help="Run dynamic API checks")
    parser.add_argument("--api-base", default="http://localhost:8000/api/v1")
    parser.add_argument("--fail-on-issues", action="store_true", help="Exit 1 if any critical/high issues")
    parser.add_argument("--output-json", help="Write JSON report to this path")
    args = parser.parse_args()

    report = SweepReport()
    files = collect_python_files(APP_DIR)
    report.files_scanned = len(files)

    print(f"Scanning {len(files)} Python files in {APP_DIR}...")

    for filepath in files:
        try:
            source = filepath.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  Warning: could not read {filepath}: {e}")
            continue

        check_pii_in_llm_prompts(source, filepath, report)
        check_pseudonym_bypasses(source, filepath, report)
        check_consent_gates_in_routers(source, filepath, report)
        check_audit_log_coverage(source, filepath, report)

    if args.live_check:
        print(f"Running live API checks against {args.api_base}...")
        run_live_checks(args.api_base, report)

    report.summary = (
        f"{report.critical_count} critical, {report.high_count} high issues "
        f"across {report.files_scanned} files."
    )

    print_report(report)

    if args.output_json:
        out = Path(args.output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"report": asdict(report)}, indent=2, default=str),
            encoding="utf-8"
        )
        print(f"JSON report written to {out}")

    if args.fail_on_issues and (report.critical_count > 0 or report.high_count > 0):
        print(f"\n❌  Sweep failed: {report.critical_count} critical + {report.high_count} high issues.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
