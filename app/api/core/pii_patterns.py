import re
from typing import List, Tuple

# ── South African PII Patterns ───────────────────────────────────────────────

# UUID Pattern
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# Email Pattern
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# SA mobile: 06 / 07 / 08 / 09 + 8 digits (10 digits total)
PHONE_RE = re.compile(r"\b0[6789]\d{8}\b")

# SA ID Number (13 digits)
SA_ID_RE = re.compile(r"\b\d{13}\b")

# Name Pattern (Simplistic: Firstname Lastname)
NAME_RE = re.compile(r"\b[A-Z][a-z]{2,}\s[A-Z][a-z]{2,}\b")

# Generic long number pattern
GENERIC_NUMBER_RE = re.compile(r"\b\d{10,}\b")

# ── Scrubber Patterns ────────────────────────────────────────────────────────

# List of (compiled regex, replacement token)
PII_SCRUBBER_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (NAME_RE, "[NAME]"),
    (SA_ID_RE, "[SA_ID]"),
    (EMAIL_RE, "[EMAIL]"),
    (PHONE_RE, "[PHONE]"),
    (GENERIC_NUMBER_RE, "[NUMBER]"),
]
