from app.assistants.prompts._json import build_json_messages
from app.schemas.course_design import CourseObjectiveGenerationRequest, CourseObjectiveGenerationResult

def build_course_objective_messages(request: CourseObjectiveGenerationRequest) -> list[dict[str, str]]:
    return build_json_messages("Generate 2 to 4 objectives. standardRefs and literacyRefs must only use IDs supplied in the request.", request, CourseObjectiveGenerationResult)
