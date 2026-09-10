from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


def normalize_source_text(value: str) -> str:
    """Normalize layout whitespace only; never alter words or punctuation."""
    return " ".join(value.replace("\r\n", "\n").replace("\r", "\n").split())


def validate_source_excerpt(
    excerpt: str | None,
    evidence_text: str,
    *,
    resource_id: int | None = None,
) -> str | None:
    if not excerpt or not excerpt.strip():
        return None
    if excerpt in evidence_text:
        return excerpt
    normalized_excerpt = normalize_source_text(excerpt)
    normalized_source = normalize_source_text(evidence_text)
    if normalized_excerpt and normalized_excerpt in normalized_source:
        return excerpt
    logger.warning(
        "Research source excerpt rejected resource_id=%s validation=NOT_VERBATIM "
        "action=DROP_EXCERPT excerpt_chars=%s source_chars=%s "
        "analysis_generation_status=READY",
        resource_id,
        len(excerpt),
        len(evidence_text),
    )
    return None
