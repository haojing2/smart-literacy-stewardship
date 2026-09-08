from demo_common import provider, resource_revision_request, run

async def demo(): return await provider().propose_resource_revision(resource_revision_request())
if __name__ == "__main__": run(demo())
