from demo_common import assessment_request, provider, run

async def demo(): return await provider().generate_course_assessments(assessment_request())
if __name__ == "__main__": run(demo())
