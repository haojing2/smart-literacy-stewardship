from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ResearchSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class ResearchResourceUploadResponse(ResearchSchema):
    resource_id: int
    file_name: str
    mime_type: str
    file_size: int
    processing_status: str
    index_status: str


class ResearchResourceResponse(ResearchResourceUploadResponse):
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ResearchTextExtractionResponse(ResearchSchema):
    resource_id: int
    project_id: int
    processing_status: str
    index_status: str
    extracted_text: str


class ResearchStructuredAnalysis(BaseModel):
    """Validated shape for future research-analysis writes."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    research_subjects: list[str] = Field(default_factory=list)
    research_topics: list[str] = Field(default_factory=list)
    ai_literacy_dimensions: list[str] = Field(default_factory=list)
    teaching_strategies: list[str] = Field(default_factory=list)
    intervention_duration: str | None = None
    assessment_tools: list[str] = Field(default_factory=list)
    main_findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
