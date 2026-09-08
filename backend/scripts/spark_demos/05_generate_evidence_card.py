from demo_common import analysis, provider, run
from app.schemas.research_assistant import EvidenceCardGenerationRequest

async def demo():
    return await provider().generate_evidence_card(EvidenceCardGenerationRequest(resource_id=1, source_file_name="demo-study.txt", analysis=analysis()))

if __name__ == "__main__": run(demo())
