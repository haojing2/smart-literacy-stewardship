from demo_common import provider, resource_generation_request, run

async def demo(): return await provider().generate_teaching_resource(resource_generation_request())
if __name__ == "__main__": run(demo())
