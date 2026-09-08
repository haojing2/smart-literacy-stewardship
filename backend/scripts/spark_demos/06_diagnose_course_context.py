from demo_common import context_request, provider, run

async def demo(): return await provider().diagnose_course_context(context_request())
if __name__ == "__main__": run(demo())
