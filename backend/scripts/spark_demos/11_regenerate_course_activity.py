from demo_common import activity, blueprint_request, provider, run
from app.schemas.course_design import CourseActivityRegenerationRequest

async def demo(): return await provider().regenerate_course_activity(CourseActivityRegenerationRequest(blueprint=blueprint_request(), activity=activity()))
if __name__ == "__main__": run(demo())
