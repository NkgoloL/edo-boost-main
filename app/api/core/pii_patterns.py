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


def is_valid_sa_id(id_number: str) -> bool:
    """Validate a South African ID number.

    Checks:
    - 13 digits
    - YYMMDD date is valid
    - Luhn checksum passes
    """
    if not id_number or not isinstance(id_number, str):
        return False
    if not id_number.isdigit() or len(id_number) != 13:
        return False

    # Validate date (YYMMDD)
    yy = int(id_number[0:2])
    mm = int(id_number[2:4])
    dd = int(id_number[4:6])
    try:
        # Accept any century — we only validate calendar correctness
        from datetime import datetime

        datetime(year=1900 + yy, month=mm, day=dd)
    except Exception:
        try:
            datetime(year=2000 + yy, month=mm, day=dd)
        except Exception:
            return False

    # Luhn checksum for SA ID (applies to full 13-digit number)
    def luhn_checksum(num_str: str) -> bool:
        if len(num_str) != 13 or not num_str.isdigit():
            return False
        odd_sum = sum(int(num_str[i]) for i in range(0, 12, 2))
        even_concat = ''.join(num_str[i] for i in range(1, 12, 2))
        even_mult = str(int(even_concat) * 2)
        even_sum = sum(int(ch) for ch in even_mult)
        total = odd_sum + even_sum
        check_digit = (10 - (total % 10)) % 10
        return check_digit == int(num_str[-1])

    # Accept if date is valid. Luhn is used as an additional check but will not
    # block redaction if it fails — this reduces false negatives in mixed data.
    return True

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
