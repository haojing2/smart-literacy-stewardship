from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


def build_json_messages(task: str, request: BaseModel, result_type: type[ModelT]) -> list[dict[str, str]]:
    payload = {
        "task": task,
        "rules": [
            "Return JSON only. Do not use Markdown or add explanatory prose.",
            "Use camelCase keys matching resultSchema exactly.",
            "Do not invent evidence, source facts, or database IDs.",
            "Return null only when resultSchema explicitly allows null; required fields and array minimums must satisfy resultSchema.",
            "For pedagogical interpretation tasks, reason only from the supplied teaching context.",
        ],
        "request": request.model_dump(mode="json", by_alias=True),
        "resultSchema": result_type.model_json_schema(by_alias=True),
    }
    return [
        {"role": "system", "content": "You are a cautious education-research assistant. Follow the JSON contract exactly."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
