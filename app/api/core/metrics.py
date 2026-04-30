"""
EduBoost SA — Custom Prometheus Metrics

Defines application-specific counters, histograms, and gauges
for observability beyond the default HTTP instrumentation.
"""

try:
    from prometheus_client import Counter, Histogram, Gauge

    # ── Lesson Generation ──────────────────────────────────────────────────
    LESSON_GENERATION_DURATION = Histogram(
        "eduboost_lesson_generation_duration_seconds",
        "Time taken to generate a lesson via LLM",
        ["model", "grade_level", "subject"],
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    )

    LESSON_GENERATION_TOTAL = Counter(
        "eduboost_lesson_generation_total",
        "Total lesson generation requests",
        ["model", "status"],  # status: success, error, fallback
    )

    # ── Diagnostic Engine ──────────────────────────────────────────────────
    DIAGNOSTIC_SESSION_TOTAL = Counter(
        "eduboost_diagnostic_session_total",
        "Total diagnostic sessions started",
        ["subject", "grade_level"],
    )

    DIAGNOSTIC_DURATION = Histogram(
        "eduboost_diagnostic_duration_seconds",
        "Time taken for a full diagnostic session",
        ["subject"],
        buckets=[10, 30, 60, 120, 300, 600],
    )

    # ── Celery Task Queue ──────────────────────────────────────────────────
    CELERY_TASK_TOTAL = Counter(
        "eduboost_celery_task_total",
        "Total Celery tasks executed",
        ["task_name", "status"],  # status: success, failure, retry
    )

    CELERY_TASK_DURATION = Histogram(
        "eduboost_celery_task_duration_seconds",
        "Celery task execution duration",
        ["task_name"],
        buckets=[1, 5, 10, 30, 60, 120, 300],
    )

    CELERY_QUEUE_DEPTH = Gauge(
        "eduboost_celery_queue_depth",
        "Number of tasks waiting in Celery queue",
        ["queue_name"],
    )

    # ── Gamification ───────────────────────────────────────────────────────
    XP_AWARDED_TOTAL = Counter(
        "eduboost_xp_awarded_total",
        "Total XP awarded to learners",
        ["xp_type"],
    )

    BADGE_AWARDED_TOTAL = Counter(
        "eduboost_badge_awarded_total",
        "Total badges awarded",
        ["badge_type"],
    )

    # ── Auth / Sessions ────────────────────────────────────────────────────
    AUTH_EVENTS_TOTAL = Counter(
        "eduboost_auth_events_total",
        "Authentication events",
        ["event_type"],  # login, register, link_learner, failed_login
    )

    ACTIVE_LEARNER_SESSIONS = Gauge(
        "eduboost_active_learner_sessions",
        "Number of active learner sessions (approximate)",
    )

    # ── API Error Rates ────────────────────────────────────────────────────
    API_ERRORS_TOTAL = Counter(
        "eduboost_api_errors_total",
        "API errors by endpoint and status code",
        ["endpoint", "status_code"],
    )

    # ── LLM Inference & Governance ───────────────────────────────────────────
    LLM_INFERENCE_DURATION = Histogram(
        "eduboost_llm_inference_duration_seconds",
        "Latency of LLM inference requests",
        ["provider", "model"],
        buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0],
    )

    LLM_INFERENCE_TOTAL = Counter(
        "eduboost_llm_inference_total",
        "Total LLM inference requests",
        ["provider", "model", "status"],  # status: success, error
    )

    LLM_COST_TOTAL = Counter(
        "eduboost_llm_cost_usd_total",
        "Estimated total cost of LLM inference in USD",
        ["provider", "model"],
    )

    LLM_SCHEMA_VALIDATION_ERRORS = Counter(
        "eduboost_llm_schema_validation_errors_total",
        "Total failures of LLM output to match Pydantic schema",
        ["template_type"],
    )

    # ── RLHF / Feedback ───────────────────────────────────────────────────────
    LESSON_FEEDBACK_TOTAL = Counter(
        "eduboost_lesson_feedback_total",
        "Learner feedback submissions on lessons",
        ["rating_bucket", "subject", "grade_level"],  # rating_bucket: 1-2, 3, 4-5
    )

    RLHF_EXPORT_TOTAL = Counter(
        "eduboost_rlhf_export_total",
        "Total RLHF feedback records exported for fine-tuning",
        ["status"],  # success, error
    )

    # ── Learner Journey SLO Counters (referenced by Grafana dashboards) ───────
    LESSONS_DELIVERED_TOTAL = Counter(
        "eduboost_lessons_delivered_total",
        "Total lessons delivered to learners",
        ["subject", "grade_level", "language"],
    )

    LESSONS_COMPLETED_TOTAL = Counter(
        "eduboost_lessons_completed_total",
        "Total lessons completed by learners (full engagement)",
        ["subject", "grade_level", "language"],
    )

    DIAGNOSTIC_SESSIONS_COMPLETED_TOTAL = Counter(
        "eduboost_diagnostic_sessions_completed_total",
        "Total diagnostic sessions completed",
        ["subject", "grade_level"],
    )

    STUDY_PLANS_GENERATED_TOTAL = Counter(
        "eduboost_study_plans_generated_total",
        "Total study plans generated",
        ["grade_level"],
    )

    CONSENT_GRANTED_TOTAL = Counter(
        "eduboost_consent_granted_total",
        "Total parental consents granted",
        [],
    )

    CONSENT_REVOKED_TOTAL = Counter(
        "eduboost_consent_revoked_total",
        "Total parental consents revoked",
        [],
    )

    ERASURE_REQUESTED_TOTAL = Counter(
        "eduboost_erasure_requested_total",
        "Total right-to-erasure requests",
        [],
    )

    CONSENT_EXPIRED_TOTAL = Counter(
        "eduboost_consent_expired_total",
        "Consents invalidated due to policy version change",
        [],
    )

    ACTIVE_CONSENTS_TOTAL = Gauge(
        "eduboost_active_consents_total",
        "Total currently active parental consents",
    )

    # ── Multilingual ──────────────────────────────────────────────────────────
    LESSON_LANGUAGE_TOTAL = Counter(
        "eduboost_lesson_language_total",
        "Lessons generated per language",
        ["language_code"],  # en, zu, af, xh
    )

    METRICS_AVAILABLE = True

except ImportError:
    # Prometheus client not installed — provide no-op stubs
    class _NoOp:
        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def dec(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

        def time(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    LESSON_GENERATION_DURATION = _NoOp()
    LESSON_GENERATION_TOTAL = _NoOp()
    DIAGNOSTIC_SESSION_TOTAL = _NoOp()
    DIAGNOSTIC_DURATION = _NoOp()
    CELERY_TASK_TOTAL = _NoOp()
    CELERY_TASK_DURATION = _NoOp()
    CELERY_QUEUE_DEPTH = _NoOp()
    XP_AWARDED_TOTAL = _NoOp()
    BADGE_AWARDED_TOTAL = _NoOp()
    AUTH_EVENTS_TOTAL = _NoOp()
    ACTIVE_LEARNER_SESSIONS = _NoOp()
    API_ERRORS_TOTAL = _NoOp()
    LLM_INFERENCE_DURATION = _NoOp()
    LLM_INFERENCE_TOTAL = _NoOp()
    LLM_COST_TOTAL = _NoOp()
    LLM_SCHEMA_VALIDATION_ERRORS = _NoOp()
    LESSON_FEEDBACK_TOTAL = _NoOp()
    RLHF_EXPORT_TOTAL = _NoOp()
    LESSONS_DELIVERED_TOTAL = _NoOp()
    LESSONS_COMPLETED_TOTAL = _NoOp()
    DIAGNOSTIC_SESSIONS_COMPLETED_TOTAL = _NoOp()
    STUDY_PLANS_GENERATED_TOTAL = _NoOp()
    CONSENT_GRANTED_TOTAL = _NoOp()
    CONSENT_REVOKED_TOTAL = _NoOp()
    ERASURE_REQUESTED_TOTAL = _NoOp()
    CONSENT_EXPIRED_TOTAL = _NoOp()
    ACTIVE_CONSENTS_TOTAL = _NoOp()
    LESSON_LANGUAGE_TOTAL = _NoOp()

    METRICS_AVAILABLE = False
