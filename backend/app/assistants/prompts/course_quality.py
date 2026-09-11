from app.assistants.prompts._json import build_json_messages
from app.schemas.course_design import CourseQualityCheckRequest, CourseQualityCheckResult

def build_course_quality_messages(request: CourseQualityCheckRequest) -> list[dict[str, str]]:
    return build_json_messages(
        "Check semantic quality only; do not repeat deterministic coverage or timing checks. "
        "checkType is only for system execution. evidence.target may contain only machine "
        "parameters such as type, id, scaffold, and studentEvidence. suggestion must be concise, "
        "natural Chinese written for teachers. Never include ADD_SCAFFOLD, "
        "ADD_PROCESS_EVIDENCE, id:, type:, or content: in suggestion.",
        request,
        CourseQualityCheckResult,
    )
