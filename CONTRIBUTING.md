# Contributing to EduBoost SA 🦁

Thank you for your interest in contributing to EduBoost SA — an AI-powered adaptive learning platform for South African learners (Grade R–7). Every contribution, large or small, directly supports equal access to quality education.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Project Overview for Contributors](#project-overview-for-contributors)
- [Development Setup](#development-setup)
- [Contribution Workflow](#contribution-workflow)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Commit Message Convention](#commit-message-convention)
- [Pull Request Process](#pull-request-process)
- [Priority Areas](#priority-areas)
- [Getting Help](#getting-help)

---

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold a welcoming, respectful environment for everyone. Please read it before engaging.

---

## Project Overview for Contributors

EduBoost SA is a **full-stack monorepo** with the following key layers:

| Layer | Location | Technology |
|-------|----------|------------|
| Backend API | `app/api/` | FastAPI 0.111, Python 3.11, SQLAlchemy 2.0 |
| Frontend | `app/frontend/` | Next.js 14 (App Router) |
| Adaptive Engine | `app/api/ml/` | IRT via scikit-learn, numpy, scipy |
| AI / LLM Layer | `app/api/services/` | Groq (primary), Anthropic, HuggingFace |
| Background Tasks | `app/api/core/celery_app.py` | Celery 5.4 + Redis 7 |
| Database | `app/api/models/` + `alembic/` | PostgreSQL 16, Alembic |
| Governance | `app/api/judiciary.py` | Policy validation layer |
| Audit | `app/api/fourth_estate.py` | Redis stream-backed audit trail |
| Tests | `tests/unit/`, `tests/integration/` | pytest, pytest-asyncio |

**Current hardening focus:** test coverage, E2E validation, POPIA compliance, and CI/CD.  
Please **prioritise these areas** over adding new surface area.

---

## Development Setup

### Prerequisites

| Tool | Minimum Version |
|------|----------------|
| Python | 3.11 (pinned via `.python-version`) |
| Node.js | 18+ |
| Docker | 24+ |
| Docker Compose | v2 (plugin, not standalone) |
| Git | 2.40+ |

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/edo-boost-main.git
cd edo-boost-main
```

### 2. Configure environment

```bash
cp env.example .env
# Edit .env and populate at minimum:
# DATABASE_URL, REDIS_URL, GROQ_API_KEY or ANTHROPIC_API_KEY, JWT_SECRET, ENCRYPTION_KEY
```

> **Security note:** Never commit `.env`. The `.gitignore` excludes it, but double-check before every push.

### 3. Start the full stack

```bash
docker compose up --build
```

Services will be available at:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3002 |
| API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Grafana | http://localhost:3001 |
| Prometheus | http://localhost:9090 |
| Flower (Celery) | http://localhost:5555 |

### 4. Run without Docker (backend only)

```bash
cd app/api
python -m venv ../../.venv
source ../../.venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r ../../requirements.txt
alembic upgrade head                 # Apply all migrations
uvicorn main:app --reload --port 8000
```

### 5. Run frontend standalone

```bash
cd app/frontend
npm install
npm run dev       # http://localhost:3000
```

### 6. Install pre-commit hooks

Pre-commit hooks enforce code quality before every commit. **This is mandatory.**

```bash
pip install pre-commit
pre-commit install
```

---

## Contribution Workflow

We use the **TDD loop** described in `AGENT_INSTRUCTIONS.md`:

```
1. Create feature branch
2. Write failing tests first
3. Implement the feature/fix
4. Run the full test suite — all tests must pass
5. Open a Pull Request
```

### Branch Naming

| Type | Pattern | Example |
|---|---|---|
| Feature | `feat/<pillar>/<description>` | `feat/judiciary/stamp-caching` |
| Bug fix | `fix/<pillar>/<description>` | `fix/ether/decay-scheduler` |
| Compliance | `popia/<description>` | `popia/erasure-cascade` |
| Docs | `docs/<description>` | `docs/ether-archetype-map` |
| Chore | `chore/<description>` | `chore/update-requirements` |

---

## Pull Request Requirements

All PRs must satisfy **all** of the following before merge to `main`:

### Automated gates (CI must be green)
- [ ] `ruff check` passes
- [ ] `mypy` type check passes
- [ ] Unit test coverage ≥ 80% for modified modules
- [ ] `alembic check` passes (no schema drift)
- [ ] POPIA compliance tests pass

### Manual review requirements

| Changed path | Required reviewers |
|---|---|
| `app/api/judiciary/` | 2 senior engineers |
| `app/api/constitutional_schema/` | 1 senior engineer + Information Officer |
| `app/api/audits/` | 1 senior engineer |
| `popia/` | Information Officer |
| Any migration in `alembic/versions/` | 1 senior engineer |

### PR description checklist
- [ ] Describe what changed and why
- [ ] List the `ConstitutionalRule` rule IDs that apply to this change (if touching learner data)
- [ ] Confirm no PII appears in any test fixture, log sample, or seed data
- [ ] Update `CHANGELOG.md`
- [ ] Add/update tests for new behaviour

---

## Coding Standards

### Python (Backend)

- **Python version:** 3.11 (enforced by `.python-version`)
- **Type hints required** on all public functions and methods
- **Docstrings required** on all classes and public methods (Google-style)
- **Async-first:** use `async def` for all I/O-bound functions
- **No direct database writes** outside of service or model layer
- **PII handling:** any code touching learner data **must** go through the `judiciary.py` policy layer and emit an event to `fourth_estate.py`

```python
# ✅ Good
async def get_learner_profile(learner_id: str, db: AsyncSession) -> LearnerProfile:
    """Retrieve a learner profile by pseudonymous ID.
    
    Args:
        learner_id: Pseudonymous learner identifier (never a real name).
        db: Async database session.
        
    Returns:
        LearnerProfile model instance.
        
    Raises:
        HTTPException: 404 if learner not found.
    """
    ...

# ❌ Bad — no type hints, no docstring, sync in async context
def get_learner(id):
    ...
```

### JavaScript / TypeScript (Frontend)

- **TypeScript strict mode** is enabled; no `any` types without explicit justification
- **Component naming:** PascalCase for components, camelCase for hooks and utilities
- **API calls** must go through `src/lib/api/` — no direct `fetch()` in page components
- **No secrets** in frontend code; use `NEXT_PUBLIC_` env vars for client-side config only

### SQL / Migrations

- **All schema changes through Alembic** — runtime `create_all()` is disabled
- **Name migrations descriptively:** `alembic revision --autogenerate -m "add_consent_timestamp_to_learners"`
- **Down migrations required** for all `upgrade()` functions
- **Indexes:** add an index for any foreign key or frequently-queried column

---

## Testing Requirements

> All PRs must maintain or improve test coverage. PRs that reduce coverage will be blocked.

### Running tests

```bash
# Full suite
pytest

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# With coverage report (HTML)
pytest --cov=app --cov-report=html

# Fast mode (skip slow integration tests)
pytest -m "not slow" -v
```

### What to test

| Change type | Required tests |
|-------------|----------------|
| New API endpoint | Integration test for happy path + validation errors + auth |
| New service method | Unit test with mocked dependencies |
| New ML model change | Unit test with fixed input → expected output |
| Database model change | Test migration up and down |
| LLM prompt change | Unit test with mocked LLM response |
| Frontend component | Component render test (if applicable) |

### Test file conventions

```
tests/
  unit/
    test_<module_name>.py         # mirrors app/api/<module_name>.py
  integration/
    test_<feature>_flow.py        # end-to-end feature flows
```

Use `factory-boy` factories (in `tests/factories/`) for test data. Never hardcode PII in tests.

---

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer: refs #issue]
```

**Types:** `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `perf`, `ci`

**Scopes** (match directory names): `api`, `frontend`, `ml`, `celery`, `db`, `auth`, `popia`, `monitoring`

**Examples:**

```
feat(ml): add 3PL IRT model for Grade 4-7 diagnostics

Extends the adaptive engine beyond 2PL to capture guessing
behaviour in older learners. Improves diagnostic precision
by 12% on validation set.

refs #48

---

fix(api): return 404 not 500 when learner not found

Judiciary layer was raising an unhandled AttributeError.
Added explicit check before policy validation.

refs #61
```

---

## Pull Request Process

1. **Branch from `main`** — keep your branch short-lived (< 2 weeks)
2. **Fill in the PR template completely** — incomplete PRs will not be reviewed
3. **Link the issue** your PR addresses (e.g., `Closes #42`)
4. **All CI checks must pass** — tests, lint, type-check
5. **At least one review approval** required before merge
6. **Squash-merge preferred** to keep the `main` history clean
7. **Update docs** if you change any public interface, environment variable, or infrastructure component
8. **Update `CHANGELOG.md`** under `## Unreleased`

### PR checklist (from template)

- [ ] Tests written and passing
- [ ] Coverage maintained or improved
- [ ] Pre-commit hooks pass
- [ ] Docs updated (if needed)
- [ ] CHANGELOG.md updated
- [ ] No secrets or PII in code or tests
- [ ] POPIA implications considered (does this change touch learner data?)

---

## Priority Areas

The following areas are actively blocked on contributions. They have the most impact and will receive the fastest review:

1. **Test coverage** — pick any file under `app/api/` with missing tests and add them
2. **POPIA E2E validation** — right-to-erasure, consent flows, audit trail completeness
3. **CI/CD pipeline** — GitHub Actions workflow for test, lint, build, and deploy
4. **Frontend E2E tests** — Playwright or Cypress tests for critical user journeys
5. **Accessibility** — WCAG 2.1 AA audit and remediation on all frontend pages
6. **Documentation** — keep docs in sync with code reality

Low-priority right now (defer unless assigned):
- New AI features
- New gamification mechanics
- UI redesign

---

## Getting Help

- **Bug or unexpected behaviour?** [Open a bug report](https://github.com/NkgoloL/edo-boost-main/issues/new?template=bug_report.md)
- **New feature idea?** [Open a feature request](https://github.com/NkgoloL/edo-boost-main/issues/new?template=feature_request.md)
- **Questions about a specific module?** Add a comment to the relevant file or open a Discussion

---

_Built with Ubuntu — "I am because we are." Every contribution matters._ 🇿🇦
