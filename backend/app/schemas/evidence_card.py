from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class EvidenceCardSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class EvidenceCardSource(EvidenceCardSchema):
    source_type: Literal["UPLOADED_RESOURCE", "KNOWLEDGE_BASE"] = "UPLOADED_RESOURCE"
    source_label: str = ""
    verification_note: str | None = None
    citations: list[str] = Field(default_factory=list)
    resource_id: int | None = Field(default=None, gt=0)
    project_id: int = Field(gt=0)
    original_filename: str | None = None
    media_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    # Parser v1 has no reliable page locator.  A retrieval card therefore
    # exposes chunk provenance instead of inventing a page number.
    file_id: int | None = Field(default=None, gt=0)
    chunk_id: str | None = None
    original_text: str | None = None
    retrieval_score: float | None = None
    source_message_id: int | None = Field(default=None, gt=0)


class EvidenceCardDraft(EvidenceCardSchema):
    evidence_card_id: int | None = None
    research_analysis_id: int = Field(gt=0)
    research_finding: str
    applicable_audience: str
    recommended_strategies: list[str] = Field(default_factory=list)
    implementation_conditions: list[str] = Field(default_factory=list)
    teaching_implications: str = ""
    limitations: str = ""
    source: EvidenceCardSource
    card_status: Literal["DRAFT", "CONFIRMED"] = "DRAFT"
    confirmed_by: int | None = None
    confirmed_at: datetime | None = None


class EvidenceCardUpdateRequest(EvidenceCardSchema):
    research_finding: str = ""
    applicable_audience: str = ""
    recommended_strategies: list[str] = Field(default_factory=list)
    implementation_conditions: list[str] = Field(default_factory=list)
    teaching_implications: str = ""
    limitations: str = ""
