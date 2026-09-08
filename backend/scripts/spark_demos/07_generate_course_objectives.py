from demo_common import objectives_request, provider, run

async def demo(): return await provider().generate_course_objectives(objectives_request())
if __name__ == "__main__": run(demo())
