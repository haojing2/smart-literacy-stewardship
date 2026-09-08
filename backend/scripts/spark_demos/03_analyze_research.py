from demo_common import EXTRACTED_TEXT, provider, run
from app.schemas.research_assistant import ResearchAnalysisRequest

async def demo():
    return await provider().analyze_research(ResearchAnalysisRequest(resource_id=1, extracted_text=EXTRACTED_TEXT, project_title="演示项目", project_topic="AI 信息核验"))

if __name__ == "__main__": run(demo())
