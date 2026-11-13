"""Cheap, deterministic guards around retrieved text. They reduce, not eliminate, injection risk."""

import re

from src.models import SearchHit

# Data-borne instruction patterns. A pattern list is easy to evade; it is one layer next to
# source trust ratings, store-side ACLs, read-only tools and human approval of any change.
INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) (instructions|rules)",
    r"disregard (the )?(system|previous) (prompt|instructions)",
    r"\bbypass\b.{0,40}\b(approval|policy|review|control)",
    r"\b(disclose|reveal|print|leak)\b.{0,60}\b(restricted|secret|password|phrase|credential)",
    r"you are now\b",
    r"\bsystem prompt\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in INJECTION_PATTERNS]


def injection_findings(text: str) -> list[str]:
    return [p.pattern for p in _COMPILED if p.search(text)]


def screen_hits(hits: list[SearchHit]) -> tuple[list[SearchHit], list[dict]]:
    """Quarantine untrusted sources that contain instruction-like text before prompting.

    Trusted, catalog-approved sources are kept even if they match (e.g. a policy that says
    'do not bypass approval'), because dropping them would silently remove real policy.
    """
    kept, quarantined = [], []
    for hit in hits:
        findings = injection_findings(hit.text)
        if hit.metadata.get("trust", "trusted") != "trusted" and findings:
            quarantined.append({"doc_id": hit.metadata.get("doc_id"), "chunk_id": hit.id,
                                "trust": hit.metadata.get("trust"), "findings": findings})
        else:
            kept.append(hit)
    return kept, quarantined


APPROVAL_BYPASS_CLAIMS = re.compile(
    r"(no|without|skip|bypass\w*)\s+(the\s+)?(need for\s+)?(approval|change approver|change record)"
    r"|vendor ticket (authori[sz]es|permits|allows)"
    r"|self-approv(e|al) (is|are) (allowed|permitted|fine)",
    re.IGNORECASE,
)


def answer_policy_violations(answer: str, forbidden_strings: tuple[str, ...] = ()) -> list[str]:
    """Output-side check for an answer: approval-bypass claims and known canary leaks."""
    issues = []
    for match in APPROVAL_BYPASS_CLAIMS.finditer(answer):
        # "without approval" inside an explicit prohibition is fine: "must not ... without approval".
        window = answer[max(0, match.start() - 40): match.start()].lower()
        if not any(neg in window for neg in ("not ", "never ", "cannot ", "no one ", "must not")):
            issues.append(f"Possible approval-bypass claim: '{match.group(0)}'")
    for secret in forbidden_strings:
        if secret and secret.lower() in answer.lower():
            issues.append("Restricted canary string leaked into answer")
    return issues
