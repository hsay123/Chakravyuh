"""Technique classification — maps raw honeypot payloads to technique categories."""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Patterns: each entry is (compiled regex, technique tag).
# Order matters — first match wins, so most specific patterns come first.
# ---------------------------------------------------------------------------

_LONG_INPUT = re.compile(r"(.)\1{30,}", re.DOTALL)
_OVERFLOW_NUM = re.compile(r"(?:\d+\s*,\s*){20,}")
_SHELL_META = re.compile(r"[;&|`$!<>]")
_SQL_KEYWORDS = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|WHERE|FROM|EXEC|xp_cmdshell)\b",
    re.IGNORECASE,
)
_BRUTE_FORCE_INDICATORS = re.compile(
    r"(?:login|password|passwd|auth|ssh|ftp|telnet)\s*(?:attempt|fail|error)",
    re.IGNORECASE,
)
_LONG_LOGIN_STRINGS = re.compile(r"^[a-zA-Z0-9!@#$%^&*()]{40,}$")

# Maps technique tag → vulnerability class(es) the CRS watches
TECHNIQUE_TO_VULN_CLASS: dict[str, list[str]] = {
    "buffer_overflow_probe": ["buffer_overflow"],
    "command_injection": ["command_injection"],
    "sql_injection": [],  # not in CRS memory-safety scope, but logged
    "credential_bruteforce": [],  # not in CRS scope
}

__all__ = ["classify", "TECHNIQUE_TO_VULN_CLASS"]


def classify(technique_hint: str | None, raw_payload: str | None) -> Optional[str]:
    """Return a technique tag, or None if unrecognised.

    The ``technique_hint`` from the honeypot is used first; if it already
    encodes a known technique we return it directly.  Otherwise we fall back
    to regex-based heuristics over ``raw_payload``.
    """
    if technique_hint and technique_hint in TECHNIQUE_TO_VULN_CLASS:
        return technique_hint

    if not raw_payload:
        return technique_hint  # may be None

    # --- heuristic classification over raw payload -----------------------
    if _LONG_INPUT.search(raw_payload) or _OVERFLOW_NUM.search(raw_payload):
        return "buffer_overflow_probe"

    if _SHELL_META.search(raw_payload):
        return "command_injection"

    if _SQL_KEYWORDS.search(raw_payload):
        return "sql_injection"

    if _BRUTE_FORCE_INDICATORS.search(raw_payload) or _LONG_LOGIN_STRINGS.match(raw_payload):
        return "credential_bruteforce"

    # Fall through: return whatever the honeypot gave us (may be None)
    return technique_hint
