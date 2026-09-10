import json

from app.assistants.prompts._json import build_json_messages
from app.schemas.research_assistant import (
    EvidenceCardDraftResult, EvidenceCardGenerationRequest, ResearchAnalysisRequest,
    ResearchAnalysisResult, ResearchAnalysisPatch, ResearchAnalysisSupplementRequest,
    ResearchChatRequest, ResearchChatResult,
    ResearchConversationSummaryRequest, ResearchConversationSummaryResult,
)

def build_research_analysis_messages(request: ResearchAnalysisRequest) -> list[dict[str, str]]:
    return build_json_messages(
        "analysisEvidence is field-aware: FIELD EVIDENCE assigns chunk ids to each field, "
        "and CHUNK REGISTRY contains each chunk once. For every output field, inspect only "
        "its assigned chunks and extract only explicitly supported facts. Never fill a field "
        "from unrelated background text or invent participants, duration, instruments, "
        "findings, strategies, or limitations. Missing list fields must be []; "
        "missing nullable fields must be null. Use only resultSchema camelCase keys; fields "
        "such as participants, method, and sampleSize are forbidden. sourceExcerpt is "
        "optional and must be a verbatim substring of analysisEvidence when supplied. Always "
        "return evidenceReady=false; the application decides readiness. Return JSON only. "
        "Extract every result field independently.",
        request,
        ResearchAnalysisResult,
    )


def build_research_analysis_supplement_messages(
    request: ResearchAnalysisSupplementRequest,
) -> list[dict[str, str]]:
    return build_json_messages(
        "Complete only the requested missing fields in an existing research-paper analysis. "
        "Use only the supplied FIELD EVIDENCE. Return values only for missingFields; do not "
        "rewrite any already validated field. Do not return sourceExcerpt or evidenceReady. "
        "Do not infer unsupported information. If evidence is insufficient, leave the "
        "requested list field empty or nullable field null. Return JSON only.",
        request,
        ResearchAnalysisPatch,
    )
def build_research_chat_messages(request: ResearchChatRequest) -> list[dict[str, str]]:
    return _research_chat_context_messages(
        request,
        response_instruction=(
            "Answer the current question naturally and directly. You may optionally return "
            "a JSON object matching this schema when you can reliably provide structured "
            "analysis enrichment, but a normal natural-language answer is preferred:\n"
            + json.dumps(ResearchChatResult.model_json_schema(by_alias=True), ensure_ascii=False)
        ),
    )


def build_research_conversation_summary_messages(
    request: ResearchConversationSummaryRequest,
) -> list[dict[str, str]]:
    return build_json_messages(
        "Summarize the supplied earlier conversation for future multi-turn context. "
        "Retain only explicit user goals, key facts and concepts, confirmed decisions, "
        "explicit user preferences or constraints, current progress, and unresolved "
        "questions. Omit greetings and repetition. Do not infer preferences or add facts.",
        request,
        ResearchConversationSummaryResult,
    )


def build_research_chat_stream_messages(
    request: ResearchChatRequest,
) -> list[dict[str, str]]:
    """Build a plain-text prompt for the display-only streaming chat path."""
    return _research_chat_context_messages(
        request,
        response_instruction=(
            "Give a helpful plain-text answer. Do not emit JSON, markdown fences, "
            "or hidden reasoning."
        ),
    )


def _research_chat_context_messages(
    request: ResearchChatRequest,
    *,
    response_instruction: str,
) -> list[dict[str, str]]:
    """Keep conversation, retrieved evidence, and current question separate."""
    system_prompt = (
        "You are a cautious education-research assistant. Answer for the supplied "
        "current project using the knowledge base configured on the Research Agent "
        "platform and the retrieved local evidence below. For factual "
        "claims about uploaded papers, prioritize the supplied retrieval evidence. Never "
        "fabricate citations, filenames, chunk ids, page numbers, or document origins. "
        "If local evidence is insufficient, say that the current project materials are "
        "insufficient; provider knowledge may only be supplemental background. Only "
        "propose an analysisPatch when it is supported by retrieved evidence, the "
        "current resource analysis, or explicit conversation. Do not invent a "
        "sourceExcerpt."
    )
    project_lines = [
        f"Project title: {request.project_title or 'Not provided'}",
        f"Topic: {request.project_topic or 'Not provided'}",
        f"Grade: {request.grade if request.grade is not None else 'Not provided'}",
        f"Class hours: {request.class_hours if request.class_hours is not None else 'Not provided'}",
    ]
    system_prompt += "\n\n[CURRENT PROJECT]\n" + "\n".join(project_lines)
    scope_description = (
        f"Only resource {request.resource_id} may be used as uploaded-paper evidence."
        if request.retrieval_scope == "RESOURCE"
        else "Evidence may be retrieved from all ready resources in this project."
    )
    uploaded_resource_exists = "YES" if request.resource_id is not None else "PROJECT SCOPE"
    system_prompt += (
        "\n\n[LOCAL KNOWLEDGE STATUS]\n"
        f"Uploaded research resource exists: {uploaded_resource_exists}\n"
        f"Retrieval scope: {request.retrieval_scope}\n"
        f"Resource ID: {request.resource_id if request.resource_id is not None else 'Not applicable'}\n"
        f"Retrieval status: {request.retrieval_status}\n"
        f"Retrieval query: {request.retrieval_query or request.message}\n"
        f"{scope_description}\n"
        "Do not attribute claims to any file outside this scope. If an uploaded resource "
        "exists, EMPTY means no sufficiently relevant evidence was retrieved for this "
        "question, and FAILED means local retrieval had a technical failure. Neither status "
        "means that no file was uploaded. Never ask the user to upload or re-upload that "
        "resource merely because retrieval is EMPTY or FAILED."
    )
    def shown(value: object) -> str:
        if value is None or value == [] or value == {} or value == "":
            return "Not provided"
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    learner_lines = (
        f"Student level: {shown(request.student_level)}",
        f"Student experience: {shown(request.student_experience)}",
        f"Class size: {shown(request.class_size)}",
        f"Lesson minutes: {shown(request.lesson_minutes)}",
        f"AI access mode: {shown(request.ai_access_mode)}",
        f"Devices: {shown(request.devices)}",
        f"Constraints: {shown(request.constraints)}",
        f"Additional requirements: {shown(request.additional_requirements)}",
        f"Context diagnosis: {shown(request.context_diagnosis)}",
    )
    system_prompt += "\n\n[LEARNER AND TEACHING CONTEXT]\n" + "\n".join(learner_lines)
    if request.analysis is not None:
        system_prompt += (
            "\n\n[CURRENT RESEARCH ANALYSIS]\n"
            + request.analysis.model_dump_json(by_alias=True)
        )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "system",
            "content": "[CONVERSATION SUMMARY]\n"
            + (request.conversation_summary or "No earlier conversation summary."),
        },
    ]
    messages.extend(_recent_conversation_messages(request))
    messages.append(
        {
            "role": "system",
            "content": "[RETRIEVED PROJECT EVIDENCE]\n" + _project_evidence(request),
        }
    )
    messages.append(
        {
            "role": "user",
            "content": "[CURRENT USER QUESTION]\n"
            + request.message
            + "\n\n[RESPONSE INSTRUCTION]\n"
            + "Use the evidence retrieved for this current question first. If it is EMPTY, "
            + "state that the uploaded material exists but this retrieval found insufficient "
            + "direct evidence. If it is FAILED, state that the uploaded material exists but "
            + "it cannot currently be searched reliably. Do not claim that no material was uploaded.\n"
            + response_instruction,
        }
    )
    return messages


def _recent_conversation_messages(request: ResearchChatRequest) -> list[dict[str, str]]:
    messages = [
        {"role": message.role, "content": message.content}
        for message in request.conversation_messages
        if message.role in {"user", "assistant"}
    ]
    if (
        messages
        and messages[-1]["role"] == "user"
        and messages[-1]["content"].strip() == request.message.strip()
    ):
        messages.pop()
    return messages


def _project_evidence(request: ResearchChatRequest) -> str:
    if not request.project_knowledge_sources:
        if request.retrieval_status == "FAILED":
            return (
                "Local evidence retrieval failed for the current question. The uploaded "
                "research resource still exists; do not interpret this technical failure "
                "as absence of uploaded materials."
            )
        scope = "selected resource" if request.retrieval_scope == "RESOURCE" else "project"
        return (
            f"The research material exists, but retrieval returned no sufficiently relevant "
            f"evidence for the current question in the {scope} scope."
        )
    return "\n\n".join(
        "\n".join(
            (
                f"[项目资料证据 {index}]",
                f"文件：{source.filename}",
                f"chunk_id：{source.chunk_id}",
                "内容：",
                source.content,
            )
        )
        for index, source in enumerate(request.project_knowledge_sources, start=1)
    )

def build_evidence_card_messages(request: EvidenceCardGenerationRequest) -> list[dict[str, str]]:
    return build_json_messages("Build a DRAFT evidence card strictly from analysis and sourceFileName; do not invent bibliographic facts.", request, EvidenceCardDraftResult)
