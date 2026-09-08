from app.assistants.prompts._json import build_json_messages
from app.schemas.course_design import CourseContextDiagnosis, CourseContextDiagnosisRequest

def build_course_context_messages(request: CourseContextDiagnosisRequest) -> list[dict[str, str]]:
    return build_json_messages("Diagnose the supplied teaching context only.", request, CourseContextDiagnosis)
