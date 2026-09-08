from demo_common import blueprint_request, provider, run

async def demo(): return await provider().generate_course_blueprint(blueprint_request())
if __name__ == "__main__": run(demo())
