"""Safely diagnose bounded-evidence structured analysis for one resource."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.research.errors import ResearchAgentContractError, ResearchAgentParseError
from app.agents.research.factory import build_research_agent_provider
from app.db.session import SessionLocal
from app.models.research import ResearchResource
from app.schemas.research_assistant import ResearchAnalysisRequest
from app.services.project_knowledge_service import ProjectKnowledgeService
from app.services.research_chat_service import ResearchChatService


async def run(resource_id: int) -> None:
    db = SessionLocal()
    try:
        resource = db.get(ResearchResource, resource_id)
        if resource is None:
            raise RuntimeError("resource was not found")
        print(f"processing_status={resource.processing_status}")
        print(f"index_status={resource.index_status}")
        service = ResearchChatService(
            db, build_research_agent_provider(), ProjectKnowledgeService(db)
        )
        evidence, sources, retrieved_count = await service._prepare_analysis_evidence(
            project_id=resource.project_id, file_id=resource.id
        )
        print(f"retrieved chunk count={retrieved_count}")
        print(f"retrieved unique chunk count={len(sources)}")
        print(f"context chars={len(evidence)}")
        for source in sources:
            print(
                f"filename={source.filename} chunk_id={source.chunk_id} "
                f"score={source.score:.6f}"
            )
        response = await service.provider.analyze_research(
            ResearchAnalysisRequest(
                resource_id=resource.id,
                analysis_evidence=evidence,
            )
        )
        for field, value in response.data.model_dump(by_alias=True).items():
            print(f"{field} has_value={bool(value)}")
    except (ResearchAgentContractError, ResearchAgentParseError) as exc:
        cause = exc.__cause__
        print(f"analysis_error={type(exc).__name__}")
        print(f"cause={type(cause).__name__ if cause else 'unknown'}")
        print(f"summary={exc}")
        raise SystemExit(1) from None
    finally:
        db.close()
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource-id", required=True, type=int)
    arguments = parser.parse_args()
    asyncio.run(run(arguments.resource_id))
