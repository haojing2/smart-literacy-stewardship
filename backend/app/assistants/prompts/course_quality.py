from app.assistants.prompts._json import build_json_messages
from app.schemas.course_design import CourseQualityCheckRequest, CourseQualityCheckResult

def build_course_quality_messages(request: CourseQualityCheckRequest) -> list[dict[str, str]]:
    return build_json_messages("Check semantic quality only; do not repeat deterministic coverage or timing checks.", request, CourseQualityCheckResult)
