from demo_common import analysis, provider, run
from app.schemas.research_assistant import ResearchChatRequest

async def demo():
    return await provider().chat(ResearchChatRequest(resource_id=1, message="请根据研究分析建议一项课堂活动。", analysis=analysis()))

if __name__ == "__main__": run(demo())
