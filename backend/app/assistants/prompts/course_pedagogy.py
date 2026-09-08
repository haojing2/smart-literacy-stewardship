from app.assistants.prompts._json import build_json_messages
from app.schemas.course_design import CoursePedagogyRecommendationRequest, CoursePedagogyRecommendationResult

def build_course_pedagogy_messages(request: CoursePedagogyRecommendationRequest) -> list[dict[str, str]]:
    return build_json_messages("Recommend pedagogy using only supplied method IDs. Every recommendation must contain a valid supplied methodId; teachers create custom methods through the separate custom-method workflow.", request, CoursePedagogyRecommendationResult)
