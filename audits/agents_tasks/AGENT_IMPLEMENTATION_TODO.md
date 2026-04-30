# Agent Implementation TODO

## 🏁 Current Milestone: Durable Audit & System Hardening (COMPLETED)
All 10 recommendations from System Status Report #2 have been implemented.

- [x] **Alembic Baseline**: Consolidated all schema management.
- [x] **Consent Gating**: Backend-enforced POPIA checkpoints.
- [x] **Fourth Estate**: Migrated to durable RabbitMQ audit trail.
- [x] **CI/CD**: Semantic versioning and release automation.
- [x] **Observability**: Expanded Grafana dashboards.
- [x] **E2E Testing**: Playwright suite implemented.

## 🚀 Next Milestone: Pilot Readiness & Scaling
The following tasks are targeted for the next phase of development.

### 1. Production Deployment & Reliability
- [ ] Execute trial production deployment using `docker-compose.prod.yml`.
- [ ] Implement database backup and automated restore drills.
- [ ] Stress-test RabbitMQ and Celery under concurrent learner load.

### 2. Pedagogy & Content Hardening
- [ ] Formalize CAPS-alignment validation rules for Grade 4-7.
- [ ] Implement multi-language lesson generation for Zulu and Xhosa.
- [ ] Expand the IRT Item Bank with calibrated CAPS items.

### 3. Frontend UX & Accessibility
- [ ] Conduct WCAG 2.1 accessibility audit for the Learner Dashboard.
- [ ] Implement "Offline First" lesson synchronization.
- [ ] Enhance Parent Portal with downloadable progress PDF reports.

### 4. AI Governance
- [ ] Implement prompt versioning and A/B testing framework.
- [ ] Add RLHF (Reinforcement Learning from Human Feedback) loop for lesson quality.
- [ ] Integrate real-time content moderation for LLM outputs.