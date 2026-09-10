from __future__ import annotations

from dataclasses import dataclass
import logging

from app.core.config import settings
from app.services.project_knowledge_service import (
    ProjectKnowledgeService,
    ProjectKnowledgeSource,
)


logger = logging.getLogger(__name__)


RESEARCH_ANALYSIS_FIELD_QUERIES: dict[str, tuple[str, ...]] = {
    "participants": (
        "研究对象 样本 参与者 被试 学生 年级 人数 participants sample learners research subjects population",
    ),
    "researchTopic": (
        "研究问题 研究目的 研究主题 研究目标 research question purpose objective topic",
    ),
    "aiLiteracyDimensions": (
        "能力重点 核心能力 素养 认知 情感 协作 AI素养 ability competence literacy dimensions",
    ),
    "teachingStrategies": (
        "教学策略 教学方法 学习支架 干预措施 教学活动 intervention teaching strategy scaffold procedure",
    ),
    "intervention": (
        "实验周期 干预时长 周 课时 实施过程 intervention duration weeks lessons treatment",
    ),
    "assessmentTools": (
        "评价工具 测量工具 问卷 量表 测验 编码框架 assessment measure instrument questionnaire scale test rubric",
    ),
    "mainFindings": (
        "研究结果 主要发现 显著 效果 影响 learning outcomes results findings effect",
    ),
    "limitations": (
        "研究局限 研究不足 局限性 未来研究 limitations future research discussion",
    ),
    "teachingImplications": (
        "教学启示 实践启示 教育意义 教学建议 implications teaching practice",
    ),
}


@dataclass(frozen=True)
class ResearchAnalysisEvidenceBundle:
    prompt_context: str
    field_sources: dict[str, list[ProjectKnowledgeSource]]
    unique_sources: list[ProjectKnowledgeSource]
    retrieved_count: int
    context_chars: int

    @property
    def field_coverage(self) -> dict[str, int]:
        return {field: len(sources) for field, sources in self.field_sources.items()}


class ResearchAnalysisEvidenceCollector:
    """Collect bounded, resource-scoped evidence independently for each field."""

    def __init__(self, project_knowledge: ProjectKnowledgeService) -> None:
        self.project_knowledge = project_knowledge

    async def collect(
        self,
        *,
        project_id: int,
        file_id: int,
        fields: list[str] | None = None,
        top_k: int = 3,
        max_chunks: int | None = None,
        max_chars: int | None = None,
    ) -> ResearchAnalysisEvidenceBundle:
        selected_fields = fields or list(RESEARCH_ANALYSIS_FIELD_QUERIES)
        chunk_limit = settings.research_analysis_max_chunks if max_chunks is None else max_chunks
        char_limit = (
            settings.research_analysis_max_context_chars if max_chars is None else max_chars
        )
        if top_k <= 0 or chunk_limit <= 0 or char_limit <= 0:
            raise ValueError("Research analysis evidence limits must be positive")

        field_sources: dict[str, list[ProjectKnowledgeSource]] = {}
        retrieved_count = 0
        for field in selected_fields:
            queries = RESEARCH_ANALYSIS_FIELD_QUERIES.get(field)
            if not queries:
                continue
            ranked: dict[str, ProjectKnowledgeSource] = {}
            for query in queries:
                sources = await self.project_knowledge.search_resource(
                    project_id=project_id,
                    file_id=file_id,
                    query=query,
                    top_k=top_k,
                )
                retrieved_count += len(sources)
                for source in sources:
                    previous = ranked.get(source.chunk_id)
                    if previous is None or source.score > previous.score:
                        ranked[source.chunk_id] = source
                logger.info(
                    "Research analysis retrieval project_id=%s resource_id=%s "
                    "analysis_field=%s retrieval_query=%r retrieved_count=%s selected_chunk_ids=%s",
                    project_id,
                    file_id,
                    field,
                    query,
                    len(sources),
                    [source.chunk_id for source in sources],
                )
            field_sources[field] = sorted(
                ranked.values(), key=lambda source: source.score, reverse=True
            )[:top_k]

        # First reserve one best chunk per field, then fill remaining registry slots.
        registry: dict[str, ProjectKnowledgeSource] = {}
        for rank in range(top_k):
            for field in selected_fields:
                sources = field_sources.get(field, [])
                if rank < len(sources):
                    registry.setdefault(sources[rank].chunk_id, sources[rank])
                if len(registry) >= chunk_limit:
                    break
            if len(registry) >= chunk_limit:
                break

        allowed_ids = set(registry)
        field_sources = {
            field: [source for source in sources if source.chunk_id in allowed_ids]
            for field, sources in field_sources.items()
        }
        prompt_context = self._render(
            selected_fields=selected_fields,
            field_sources=field_sources,
            registry=registry,
            max_chars=char_limit,
        )
        bundle = ResearchAnalysisEvidenceBundle(
            prompt_context=prompt_context,
            field_sources=field_sources,
            unique_sources=list(registry.values()),
            retrieved_count=retrieved_count,
            context_chars=len(prompt_context),
        )
        logger.info(
            "Research analysis evidence collected project_id=%s resource_id=%s "
            "field_coverage=%s unique_chunks=%s analysis_context_chars=%s",
            project_id,
            file_id,
            bundle.field_coverage,
            len(bundle.unique_sources),
            bundle.context_chars,
        )
        return bundle

    @staticmethod
    def _render(
        *,
        selected_fields: list[str],
        field_sources: dict[str, list[ProjectKnowledgeSource]],
        registry: dict[str, ProjectKnowledgeSource],
        max_chars: int,
    ) -> str:
        field_sections = []
        for field in selected_fields:
            chunk_ids = [source.chunk_id for source in field_sources.get(field, [])]
            field_sections.append(
                f"[FIELD EVIDENCE: {field}]\nchunk_ids: "
                + (", ".join(chunk_ids) if chunk_ids else "NONE")
            )
        prefix = "\n\n".join(field_sections) + "\n\n[CHUNK REGISTRY]"
        if len(prefix) >= max_chars:
            return prefix[:max_chars]

        chunks = list(registry.values())
        remaining = max_chars - len(prefix)
        per_chunk = max(160, remaining // max(1, len(chunks)))
        blocks = [prefix]
        for source in chunks:
            header = (
                f"\n\n[CHUNK {source.chunk_id}]\nfilename={source.filename}\n"
                f"file_id={source.file_id}\nchunk_index={source.chunk_index}\ncontent:\n"
            )
            available = min(per_chunk, max_chars - sum(len(block) for block in blocks))
            if available <= len(header):
                break
            blocks.append(header + source.content[: available - len(header)])
        return "".join(blocks)[:max_chars]
