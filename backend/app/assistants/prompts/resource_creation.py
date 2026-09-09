from __future__ import annotations

import json

from app.schemas.resource_creation import (
    ResourceDraftContent,
    ResourceType,
    TeachingResourceGenerationRequest,
    TeachingResourceGenerationResult,
)


RESOURCE_PROMPT_TEMPLATES: dict[ResourceType, str] = {
    ResourceType.TEACHER_GUIDE: """生成教师上课时可快速查看的教师流程卡。严格按 activities 的顺序，每个活动单独成块，包含环节名称、时间、教学目标、教师行为、学生行为、AI支持、教师提示/追问、观察重点、可能困难及简短处理建议；另含 overview、assessment_reminder、closing。活动总时间必须与课程蓝图一致，不得新增教学环节。""",
    ResourceType.WORKSHEET: """生成符合当前年级和学生水平、可直接填写的学生学习单。任务必须对应课堂活动且有明确记录要求，可按实际需要包含 learning_goal、before_thinking、task_N、evidence_record、ai_interaction_record、reflection、final_output。仅当课程设计涉及 AI 互动时，才要求学生记录初始观点、AI贡献、接受/修改/拒绝及理由和观点变化。""",
    ResourceType.TASK_CARD: """生成可直接发给学生的课堂任务卡，数量、组织形式、时间提示和标准遵循 resourceSettings。每张卡包含任务名称、目标、情境/问题、步骤、时间、个人/小组方式、材料或AI、最终产出、完成标准；小组任务给出简洁分工。任务时间不得超过对应活动时间。""",
    ResourceType.AI_CASE: """生成用于分析、讨论和评价的人—AI对话案例，而不是让AI直接给答案。包含案例情境、人的初始问题/观点、遵循 turns 的多轮 Human-AI dialogue、关键判断节点、应接受/修改/拒绝的AI贡献及分析问题。errorAnswer=true 时加入一处不完整、片面、需核查或推理有问题但不荒谬的回答，训练判断、核查、比较、修订和解释理由。""",
    ResourceType.DISCUSSION: """根据 quantity、thinkingLevel、groupPrompt 生成紧扣课程内容的讨论问题，形成适当的理解、解释、比较、分析、评价或迁移层次。每题包含 question、purpose、expectedThinking、followUpPrompt、groupOrWholeClass，禁止泛泛的“你怎么看”。""",
    ResourceType.ASSESSMENT: """依据已确认 learning objectives、assessment design 和 activities 生成课堂评价工具，并遵循 type、evaluator、rubric、levels、observableIndicators。每个评价指标必须明确对齐一个 objective，且可观察、可判断；避免模糊表述。Rubric 包含指标、指定数量的等级描述和表现证据。""",
    ResourceType.REFLECTION: """依据 objectives、activities、assessment、studentLevel 生成课后反思单，受 audience、questionCount、actionPlan 控制。学生版关注学习所得、判断证据、困难、观点变化和下一步；教师版关注目标达成、学生表现、课堂证据、困难、支架与AI支持及下次调整。问题数量接近并遵循 questionCount。""",
}


def build_teaching_resource_messages(
    request: TeachingResourceGenerationRequest,
) -> list[dict[str, str]]:
    if request.resource_type == ResourceType.PPT:
        raise ValueError("PPT is reserved for a dedicated model/API")
    task = RESOURCE_PROMPT_TEMPLATES[request.resource_type]
    context = {
        "projectContext": request.project.model_dump(mode="json", by_alias=True),
        "confirmedCourseDesign": {
            "objectives": request.objectives,
            "pedagogy": request.pedagogy,
            "activities": request.activities,
            "assessments": request.assessments,
            "courseBlueprint": request.course_blueprint,
        },
        "researchBasedEvidence": request.research_evidence,
        "resourceSettings": {
            "commonSettings": request.common_settings,
            "currentTypeSettings": request.resource_settings,
        },
    }
    payload = {
        "contextPriority": [
            "confirmedCourseDesign is the highest instructional constraint",
            "projectContext defines learner and implementation constraints",
            "researchBasedEvidence supports strategies but must not redesign the course",
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
        ],
        "resultSchema": TeachingResourceGenerationResult.model_json_schema(by_alias=True),
    }
    return [
        {"role": "system", "content": "You are an expert instructional resource designer. Follow the supplied confirmed course design and JSON contract exactly."},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


_TYPE_MARKERS = {
    ResourceType.TEACHER_GUIDE: ("activity", "活动", "流程", "环节"),
    ResourceType.WORKSHEET: ("task", "任务", "学习", "填写", "记录"),
    ResourceType.TASK_CARD: ("task", "任务", "产出", "output"),
    ResourceType.AI_CASE: ("dialogue", "对话", "human", "ai"),
    ResourceType.DISCUSSION: ("question", "问题", "讨论"),
    ResourceType.ASSESSMENT: ("criteria", "rubric", "评价", "指标"),
    ResourceType.REFLECTION: ("reflection", "反思", "问题"),
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
    searchable = json.dumps(content.model_dump(mode="json", by_alias=True), ensure_ascii=False).lower()
    if not any(marker in searchable for marker in _TYPE_MARKERS[resource_type]):
        raise ValueError(f"Generated {resource_type.value} lacks its required basic content")
