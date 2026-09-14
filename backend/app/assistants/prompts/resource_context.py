from __future__ import annotations

import json

from app.schemas.resource_creation import (
    ResourceContextCompressionResult,
    ResourceType,
    TeachingResourceGenerationRequest,
)


_CONTEXT_FIELDS: dict[ResourceType, tuple[str, ...]] = {
    ResourceType.TEACHER_GUIDE: ("objectives", "pedagogy", "activities", "assessments"),
    ResourceType.WORKSHEET: ("objectives", "activities"),
    ResourceType.TASK_CARD: ("objectives", "activities"),
    ResourceType.AI_CASE: ("objectives", "pedagogy", "activities"),
    ResourceType.DISCUSSION: ("objectives", "pedagogy", "activities"),
    ResourceType.ASSESSMENT: ("objectives", "activities", "assessments"),
    ResourceType.REFLECTION: ("objectives", "activities", "assessments"),
}


def build_resource_context_messages(
    request: TeachingResourceGenerationRequest,
) -> list[dict[str, str]]:
    if request.resource_type == ResourceType.PPT:
        raise ValueError("PPT is reserved for a dedicated model/API")
    confirmed_design = {
        field: getattr(request, field)
        for field in _CONTEXT_FIELDS[request.resource_type]
        if getattr(request, field)
    }
    payload = {
        "resourceType": request.resource_type.value,
        "projectContext": request.project.model_dump(mode="json", by_alias=True, exclude_none=True),
        "confirmedCourseDesign": confirmed_design,
        "rules": [
            "Preserve every referenced database ID.",
            "Preserve activity sequence and duration.",
            "Do not add activities or objectives.",
            "Do not infer missing information.",
            "Remove duplicated explanations and condense long prose.",
            "Retain only information necessary to generate the requested resource.",
            "Do not generate the final teaching resource or rewrite resource settings.",
            "Return JSON only and follow the supplied output schema exactly.",
        ],
        "outputSchema": ResourceContextCompressionResult.model_json_schema(by_alias=True),
    }
    return [
        {
            "role": "system",
            "content": (
                "You are a context normalization layer for teaching-resource generation. "
                "You do not design or generate teaching resources. Compress and normalize only "
                "the supplied context. Never invent, reinterpret, or change authoritative "
                "course-design facts."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
