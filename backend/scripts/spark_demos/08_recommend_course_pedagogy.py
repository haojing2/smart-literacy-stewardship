from demo_common import pedagogy_request, provider, run

async def demo(): return await provider().recommend_course_pedagogy(pedagogy_request())
if __name__ == "__main__": run(demo())
