from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class EvidenceSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class EvidenceSourceMetadata(EvidenceSchema):
    source_type: Literal["UPLOADED_RESOURCE", "KNOWLEDGE_BASE"] = "UPLOADED_RESOURCE"
    resource_id: int | None = None
    original_filename: str | None = None
    media_type: str | None = None
    sha256: str | None = None
    citations: list[str] = Field(default_factory=list)


class EvidenceReadinessResult(EvidenceSchema):
    ready: bool
    readiness_score: int = Field(ge=0, le=100)
    readiness_status: Literal["INCOMPLETE", "READY"]
    missing_required_fields: list[str] = Field(default_factory=list)
    missing_recommended_fields: list[str] = Field(default_factory=list)
