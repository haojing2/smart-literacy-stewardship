from app.assistants.prompts._json import build_json_messages
from app.schemas.course_design import CourseAssessmentGenerationRequest, CourseAssessmentGenerationResult

def build_course_assessment_messages(request: CourseAssessmentGenerationRequest) -> list[dict[str, str]]:
    return build_json_messages("Generate assessments whose objectiveId values only reference supplied objectives.", request, CourseAssessmentGenerationResult)
