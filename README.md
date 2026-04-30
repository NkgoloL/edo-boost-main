# 🦁 EduBoost SA

**AI-powered adaptive learning platform for South African learners — Grade R to Grade 7**

[![CAPS Aligned](https://img.shields.io/badge/CAPS-Aligned-green)](https://www.education.gov.za)
[![POPIA Compliant](https://img.shields.io/badge/POPIA-Compliant-blue)](https://popia.co.za)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)

---

## 📋 Overview

EduBoost SA is an adaptive learning platform built on a "Five Pillar" architecture to ensure pedagogical alignment, operational excellence, and strict POPIA compliance. The platform provides personalized learning journeys for South African students while maintaining high standards for data privacy and educational quality.

### Key Features
- 🧠 **Adaptive Diagnostic Engine** — IRT-based (Item Response Theory) assessments that find the exact grade level of each knowledge gap.
- 🤖 **AI Lesson Generation** — Claude/Llama 3 powered lessons with authentic South African context (ubuntu, braai, rands, local fauna).
- 📅 **Dynamic Study Plans** — CAPS-aligned weekly schedules that prioritise foundation gaps while keeping pace with grade-level work.
- 🏆 **Gamification** — XP, badges, streaks for Grade R–3; discovery-based engagement for Grade 4–7.
- 🔒 **POPIA-Grade Privacy** — Backend-enforced parental consent, pseudonymous learner IDs, and a durable audit trail.
- 📊 **Parent Portal** — AI-generated progress reports, right-to-access exports, and granular consent management.

---

## 🗂️ Project Structure

```
eduboost-sa/
├── app/
│   ├── api/                          # FastAPI backend
│   │   ├── constitutional_schema/    # Schema and typing helpers
│   │   ├── core/                     # Config, DB, Celery
│   │   ├── ml/                       # IRT engine
│   │   ├── models/                   # SQLAlchemy models (Alembic-managed)
│   │   ├── routers/                  # API routes (including Consent/Auth)
│   │   ├── services/                 # LLM / lesson / consent services
│   │   ├── main.py                   # FastAPI entrypoint
│   │   ├── orchestrator.py           # Workflow orchestration
│   │   ├── judiciary.py              # Policy / validation layer (Pillar 3)
│   │   ├── fourth_estate.py          # Durable RabbitMQ Audit Trail (Pillar 4)
│   │   └── profiler.py               # Profiling helpers (Pillar 5 - Ether)
│   └── frontend/                     # Next.js frontend (App Router)
│       ├── src/app/                  # Feature pages (dashboard, lesson, diagnostic, etc.)
│       ├── src/components/eduboost/   # Specialized UI components
│       ├── src/lib/api/              # Production-grade service layer
│       └── package.json
├── docker/                           # Dockerfiles and Nginx configs
├── grafana/                          # Grafana provisioning & dashboards
├── k8s/                              # Kubernetes manifests
├── scripts/                          # DB migrations, seeds, and maintenance
├── tests/                            # E2E (Playwright), Unit, and Integration tests
├── docker-compose.yml                # Local development stack
├── docker-compose.prod.yml           # Production deployment stack
├── prometheus.yml                    # Prometheus scrape config
├── requirements.txt                  # Python dependencies
└── README.md
```

---

## ⚠️ Current State

EduBoost SA is currently in its **Beta** phase, with core architectural pillars fully implemented:

- ✅ **Pillar 2 (Executive)**: Backend-mediated lesson generation and study plan workflows.
- ✅ **Pillar 3 (Judiciary)**: Constitutional policy enforcement via the Judiciary Stamp gate.
- ✅ **Pillar 4 (Fourth Estate)**: Durable, RabbitMQ-backed audit trail for POPIA compliance.
- ✅ **Pillar 5 (Ether)**: Psychological archetype profiling and adaptive prompt modification.
- ✅ **Infrastructure**: Alembic-driven migrations, RabbitMQ messaging, and Prometheus/Grafana observability.
- ✅ **Compliance**: Backend-enforced parental consent and right-to-erasure workflows.

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### 1. Clone & Configure
```bash
git clone <your-github-repo-url>
cd eduboost-sa
cp env.example .env
```

### 2. Start the Full Stack (Docker)
```bash
docker compose up --build
```

Services will be available at:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Grafana | http://localhost:3001 |
| RabbitMQ UI | http://localhost:15672 (guest/guest) |

---

## 🔑 Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy connection string (Postgres) |
| `REDIS_URL` | Redis connection string (Cache/Celery) |
| `RABBITMQ_URL` | RabbitMQ connection string (Audit Trail/Broker) |
| `GROQ_API_KEY` | Primary LLM inference key |
| `ANTHROPIC_API_KEY` | Secondary LLM provider key |
| `JWT_SECRET` | JWT signing secret |
| `ENCRYPTION_KEY` | AES-256 key for PII at rest |

---

## 🧪 Testing

```bash
# Unit & Integration tests
pytest

# E2E tests (Playwright)
npx playwright test
```

---

## 🔐 POPIA & Privacy

EduBoost SA implements privacy-by-design through:

1. **Consent Gating**: All learner data access requires a valid, non-expired `ParentalConsent` record.
2. **Pseudonymisation**: Real learner identities are never passed to LLM providers; opaque `pseudonym_id`s are used instead.
3. **Durable Audit**: Every sensitive action and constitutional review is logged to a persistent RabbitMQ exchange.
4. **Right to Erasure**: Guardian-initiated deletion workflows atomically revoke consent and soft-delete personal data.
5. **PII Scrubbing**: Prompt paths are audited via the "Chaos Sweep" scripts to prevent leakage.

---

## 📈 Monitoring

The stack includes pre-configured Grafana dashboards covering:
*   **Learner Journey SLOs**: Tracking diagnostic completion and lesson efficacy.
*   **LLM Provider Health**: Latency and success rates across providers.
*   **Constitutional Health**: Approval rates and violation trends.

---

## 🤝 Contributing

We welcome contributions! Please refer to [CONTRIBUTING.md](CONTRIBUTING.md) for our engineering standards and [CHANGELOG.md](CHANGELOG.md) for version history.

1. Fork the repo and create a feature branch.
2. Ensure all tests pass (`pytest` and `playwright`).
3. Follow the 5-pillar architectural patterns.
4. Submit a PR for review.

---

## 📜 License

MIT License — see `LICENSE` file.

---

## 🇿🇦 About

Built with Ubuntu — *"I am because we are."* Every South African child deserves access to quality, personalised education.
