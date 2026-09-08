from demo_common import provider, resource_review_request, run

async def demo(): return await provider().review_teaching_resource(resource_review_request())
if __name__ == "__main__": run(demo())
