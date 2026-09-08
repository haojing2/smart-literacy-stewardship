from demo_common import provider, quality_request, run

async def demo(): return await provider().check_course_quality(quality_request())
if __name__ == "__main__": run(demo())
