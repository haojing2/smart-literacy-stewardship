from __future__ import annotations

import json

from app.schemas.resource_creation import (
    ResourceDraftContent,
    ResourceType,
    TeachingResourceGenerationRequest,
)


RESOURCE_PROMPT_TEMPLATES: dict[ResourceType, str] = {
    ResourceType.TEACHER_GUIDE: """生成教师上课时可快速查看的教师流程卡。严格按 activities 的顺序，每个活动单独成块，包含环节名称、时间、教学目标、教师行为、学生行为、AI支持、教师提示/追问、观察重点、可能困难及简短处理建议；另含 overview、assessment_reminder、closing。活动总时间必须与课程蓝图一致，不得新增教学环节。""",
    ResourceType.WORKSHEET: """生成符合当前年级和学生水平、可直接填写的学生学习单。任务必须对应课堂活动且有明确记录要求，可按实际需要包含 learning_goal、before_thinking、task_N、evidence_record、ai_interaction_record、reflection、final_output。仅当课程设计涉及 AI 互动时，才要求学生记录初始观点、AI贡献、接受/修改/拒绝及理由和观点变化。""",
    ResourceType.TASK_CARD: """生成可直接发给学生的课堂任务卡，数量、组织形式、时间提示和标准遵循 resourceSettings。每张卡包含任务名称、目标、情境/问题、步骤、时间、个人/小组方式、材料或AI、最终产出、完成标准；小组任务给出简洁分工。任务时间不得超过对应活动时间。""",
    ResourceType.AI_CASE: """生成用于分析、讨论和评价的人—AI对话案例，而不是让AI直接给答案。包含案例情境、人的初始问题/观点、遵循 turns 的多轮 Human-AI dialogue、关键判断节点、应接受/修改/拒绝的AI贡献及分析问题。errorAnswer=true 时加入一处不完整、片面、需核查或推理有问题但不荒谬的回答，训练判断、核查、比较、修订和解释理由。""",
    ResourceType.DISCUSSION: """根据 quantity、thinkingLevel、groupPrompt 生成紧扣课程内容的讨论问题，形成适当的理解、解释、比较、分析、评价或迁移层次。每题包含 question、purpose、expectedThinking、followUpPrompt、groupOrWholeClass，禁止泛泛的“你怎么看”。""",
    ResourceType.ASSESSMENT: """依据已确认 learning objectives、assessment design 和 activities 生成课堂评价工具，并遵循 type、evaluator、rubric、levels、observable indicators。每个评价指标必须明确对齐一个 objective，且可观察、可判断；避免模糊表述。Rubric 包含指标、指定数量的等级描述和表现证据。""",
    ResourceType.REFLECTION: """依据 objectives、activities、assessment、studentLevel 生成课后反思单，受 audience、questionCount、actionPlan 控制。学生版关注学习所得、判断证据、困难、观点变化和下一步；教师版关注目标达成、学生表现、课堂证据、困难、支架与AI支持及下次调整。问题数量接近并遵循 questionCount。""",
}


_RESOURCE_BLOCK_KEYS: dict[ResourceType, tuple[str, ...]] = {
    ResourceType.WORKSHEET: ("learning_goal", "task_1", "task_2", "task_3", "reflection"),
    ResourceType.TASK_CARD: ("task_1", "task_2", "task_3"),
    ResourceType.AI_CASE: ("scenario", "dialogue", "judgement", "discussion"),
    ResourceType.DISCUSSION: ("question_1", "question_2", "question_3"),
    ResourceType.ASSESSMENT: ("criteria", "rubric", "evidence"),
    ResourceType.REFLECTION: ("learning_gain", "evidence_and_difficulty", "next_action"),
    ResourceType.TEACHER_GUIDE: ("overview", "lesson_flow", "assessment_reminder"),
}

def _output_template(resource_type: ResourceType) -> dict[str, object]:
    if resource_type == ResourceType.ASSESSMENT:
        list_content = {
            "type": "list",
            "items": [
                {"title": "填写标题", "description": "填写说明"}
                for _ in range(3)
            ],
        }
        return {
            "title": "填写资源标题",
            "content": {
                "title": "填写资源标题",
                "blocks": [
                    {"key": "criteria", "title": "评价标准", "content": list_content},
                    {
                        "key": "rubric",
                        "title": "评价量规",
                        "content": {
                            "type": "table",
                            "columns": [
                                {"key": "criterion", "label": "核心指标"},
                                {"key": "description", "label": "表现描述"},
                                {"key": "evidence", "label": "观察证据"},
                            ],
                            "rows": [
                                {
                                    "criterion": "填写指标",
                                    "description": "填写表现描述",
                                    "evidence": "填写观察证据",
                                }
                                for _ in range(3)
                            ],
                        },
                    },
                    {"key": "evidence", "title": "表现证据", "content": list_content},
                ],
                "metadata": {},
            },
            "changeSummary": "填写生成说明",
        }
    return {
        "title": "填写资源标题",
        "content": {
            "title": "填写资源标题",
            "blocks": [
                {"key": key, "title": "填写区块标题", "content": "填写区块内容"}
                for key in _RESOURCE_BLOCK_KEYS[resource_type]
            ],
            "metadata": {},
        },
        "changeSummary": "填写生成说明",
    }


RESOURCE_OUTPUT_TEMPLATES: dict[ResourceType, dict[str, object]] = {
    resource_type: _output_template(resource_type)
    for resource_type in _RESOURCE_BLOCK_KEYS
}


def normalize_assessment_content(content: dict[str, object]) -> dict[str, object]:
    """Normalize only unambiguous assessment table/list variants."""
    normalized = dict(content)
    blocks = normalized.get("blocks")
    if not isinstance(blocks, list):
        return normalized
    normalized_blocks: list[object] = []
    for raw_block in blocks:
        if not isinstance(raw_block, dict):
            normalized_blocks.append(raw_block)
            continue
        block = dict(raw_block)
        key = block.get("key")
        value = block.get("content")
        if key == "rubric" and isinstance(value, dict):
            table = dict(value)
            columns = table.get("columns", table.get("headers"))
            rows = table.get("rows", table.get("data"))
            if isinstance(columns, list) and columns and all(isinstance(column, str) and column.strip() for column in columns):
                if len(set(columns)) == len(columns):
                    columns = [{"key": column, "label": column} for column in columns]
            if (
                isinstance(columns, list)
                and all(isinstance(column, dict) and isinstance(column.get("key"), str) for column in columns)
                and isinstance(rows, list)
                and all(isinstance(row, list) and len(row) == len(columns) for row in rows)
            ):
                column_keys = [column["key"] for column in columns]
                rows = [dict(zip(column_keys, row, strict=True)) for row in rows]
            if isinstance(columns, list) and isinstance(rows, list):
                table = {"type": "table", "columns": columns, "rows": rows[:3]}
            block["content"] = table
        elif key in {"criteria", "evidence"} and isinstance(value, dict):
            items = value.get("items")
            if isinstance(items, list):
                block["content"] = {"type": "list", "items": items[:3]}
        normalized_blocks.append(block)
    normalized["blocks"] = normalized_blocks
    return normalized


def validate_assessment_content(content: ResourceDraftContent | dict[str, object]) -> None:
    value = content.model_dump(mode="python", by_alias=True) if isinstance(content, ResourceDraftContent) else content
    blocks = value.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("Assessment blocks must be an array")
    by_key = {block.get("key"): block for block in blocks if isinstance(block, dict)}
    for key in ("criteria", "evidence"):
        block_content = by_key.get(key, {}).get("content")
        if not isinstance(block_content, dict) or block_content.get("type") != "list":
            raise ValueError(f"Assessment {key} content.type must equal list")
        items = block_content.get("items")
        if not isinstance(items, list) or len(items) > 3:
            raise ValueError(f"Assessment {key} items must be an array with at most 3 entries")
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("title"), str)
            or not item["title"].strip()
            or not isinstance(item.get("description"), str)
            or not item["description"].strip()
            for item in items
        ):
            raise ValueError(f"Every Assessment {key} item requires title and description")

    rubric = by_key.get("rubric", {}).get("content")
    if not isinstance(rubric, dict) or rubric.get("type") != "table":
        raise ValueError("Assessment rubric content.type must equal table")
    columns = rubric.get("columns")
    rows = rubric.get("rows")
    if not isinstance(columns, list) or not columns:
        raise ValueError("Assessment rubric columns must be a non-empty array")
    if any(
        not isinstance(column, dict)
        or not isinstance(column.get("key"), str)
        or not column["key"].strip()
        or not isinstance(column.get("label"), str)
        or not column["label"].strip()
        for column in columns
    ):
        raise ValueError("Every rubric column requires non-empty key and label")
    column_keys = [column["key"] for column in columns]
    if len(column_keys) != len(set(column_keys)):
        raise ValueError("Rubric column keys must be unique")
    if not isinstance(rows, list) or len(rows) > 3:
        raise ValueError("Assessment rubric rows must be an array with at most 3 entries")
    if any(
        not isinstance(row, dict)
        or any(column_key not in row or row[column_key] is None for column_key in column_keys)
        for row in rows
    ):
        raise ValueError("Every rubric row must contain a non-null value for every column key")

TEACHING_RESOURCE_STRUCTURE_RULES = [
    "The top-level object must contain only title, content, and changeSummary.",
    "content must be an object containing title, blocks, and metadata; content must never be a string.",
    "Block fields such as key, title, and content may appear only inside content.blocks[].",
    "Never return a ResourceDraftBlock directly as the root object.",
    "Copy the outputTemplate exactly and fill only title/content text values; do not add, remove, or rename fields, block keys, or change the JSON hierarchy.",
]


def build_teaching_resource_messages(
    request: TeachingResourceGenerationRequest,
) -> list[dict[str, str]]:
    if request.resource_type == ResourceType.PPT:
        raise ValueError("PPT is reserved for a dedicated model/API")
    task = RESOURCE_PROMPT_TEMPLATES[request.resource_type]
    confirmed_design: dict[str, object] = {}
    for name in ("objectives", "pedagogy", "activities", "assessments"):
        value = getattr(request, name)
        if value:
            confirmed_design[name] = value
    context = {
        "projectContext": request.project.model_dump(mode="json", by_alias=True, exclude_none=True),
        "confirmedCourseDesign": confirmed_design,
        "resourceSettings": {
            "commonSettings": request.common_settings,
            "currentTypeSettings": request.resource_settings,
        },
    }
    payload = {
        "contextPriority": [
            "confirmedCourseDesign is the highest instructional constraint",
            "projectContext defines learner and implementation constraints",
            "resourceSettings controls presentation only",
        ],
        "context": context,
        "resourceSpecificTask": task,
        "outputRules": [
            "Transform the confirmed course design into a classroom-ready resource; do not redesign it.",
            "Do not change learning objectives, core pedagogy, activity order, or assessment logic.",
            "If settings conflict with confirmed design, follow confirmed design.",
            "Do not invent missing context or evidence.",
            "Return JSON only, without markdown fences or explanation.",
            "Use unique non-empty block keys and non-empty block content.",
            "Copy the outputTemplate exactly: fill content only; do not add fields, remove fields, rename block keys, or change the JSON hierarchy.",
            *TEACHING_RESOURCE_STRUCTURE_RULES,
        ],
        "outputTemplate": RESOURCE_OUTPUT_TEMPLATES[request.resource_type],
    }
    return [
        {"role": "system", "content": "You are an expert instructional resource designer. Follow the supplied confirmed course design and JSON contract exactly."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


_TYPE_MARKERS = {
    ResourceType.TEACHER_GUIDE: ("activity", "lesson_flow", "活动", "流程", "环节"),
    ResourceType.WORKSHEET: ("task", "任务", "学习", "填写", "记录"),
    ResourceType.TASK_CARD: ("task", "任务", "产出", "output"),
    ResourceType.AI_CASE: ("dialogue", "对话", "human", "ai"),
    ResourceType.DISCUSSION: ("question", "问题", "讨论"),
    ResourceType.ASSESSMENT: ("criteria", "rubric", "评价", "指标"),
    ResourceType.REFLECTION: ("reflection", "learning_gain", "反思", "问题"),
}


def validate_generated_resource(
    resource_type: ResourceType,
    content: ResourceDraftContent,
    request: TeachingResourceGenerationRequest,
) -> None:
    del request
    if not content.title or not content.title.strip():
        raise ValueError("Generated resource title is empty")
    if not content.blocks:
        raise ValueError("Generated resource blocks are empty")
    keys = [block.key.strip() for block in content.blocks]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("Generated resource block keys must be non-empty and unique")
    if any(block.content is None or (isinstance(block.content, str) and not block.content.strip()) for block in content.blocks):
        raise ValueError("Generated resource block content is empty")
    expected_keys = list(_RESOURCE_BLOCK_KEYS[resource_type])
    if keys != expected_keys:
        raise ValueError(f"Generated resource block keys must exactly match the fixed template: {expected_keys}")
    if resource_type == ResourceType.ASSESSMENT:
        validate_assessment_content(content)
    searchable = json.dumps(content.model_dump(mode="json", by_alias=True), ensure_ascii=False).lower()
    if not any(marker in searchable for marker in _TYPE_MARKERS[resource_type]):
        raise ValueError(f"Generated {resource_type.value} lacks its required basic content")
