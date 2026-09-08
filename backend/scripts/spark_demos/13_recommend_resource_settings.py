from demo_common import provider, resource_settings_request, run

async def demo(): return await provider().recommend_resource_settings(resource_settings_request())
if __name__ == "__main__": run(demo())
