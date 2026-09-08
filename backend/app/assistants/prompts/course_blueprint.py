from app.assistants.prompts._json import build_json_messages
from app.schemas.course_design import CourseActivityProposal, CourseActivityRegenerationRequest, CourseBlueprintGenerationRequest, CourseBlueprintGenerationResult

def build_course_blueprint_messages(request: CourseBlueprintGenerationRequest) -> list[dict[str, str]]:
    return build_json_messages("Generate exactly four activities. objectiveRefs may only reference supplied objective IDs.", request, CourseBlueprintGenerationResult)

def build_course_activity_regeneration_messages(request: CourseActivityRegenerationRequest) -> list[dict[str, str]]:
    return build_json_messages("Regenerate only the requested activity, preserving course continuity and valid objectiveRefs.", request, CourseActivityProposal)
