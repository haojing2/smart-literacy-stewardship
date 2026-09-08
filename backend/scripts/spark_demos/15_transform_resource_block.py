from demo_common import provider, resource_transform_request, run

async def demo(): return await provider().transform_resource_block(resource_transform_request())
if __name__ == "__main__": run(demo())
