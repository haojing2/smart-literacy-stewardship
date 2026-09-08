"""A session-bound document-search tool with no caller-controlled project ID."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.repositories.research_chat_repository import ResearchChatRepository
from app.services.project_knowledge_service import ProjectKnowledgeService


class SearchProjectDocumentsArguments(BaseModel):
    """The complete public input contract for this internal tool."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1)


@dataclass(frozen=True)
class SearchProjectDocumentsResult:
    content: str
    filename: str
    file_id: int
    chunk_id: str
    score: float


class CurrentConversationNotFoundError(LookupError):
    pass


class SearchProjectDocumentsTool:
    """Search only documents belonging to the tool's verified chat session.

    ``session_id`` and ``current_user_id`` are server-side runtime bindings;
    they are never part of the model-callable argument schema. The tool only
    retrieves chunks and does not generate an answer.
    """

    name = "search_project_documents"
    description = "Search ready local documents for the current research conversation."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keywords or a natural-language document search query.",
            }
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        db: Session,
        *,
        current_user_id: int,
        session_id: int,
        project_knowledge: ProjectKnowledgeService | None = None,
    ) -> None:
        self._current_user_id = current_user_id
        self._session_id = session_id
        self._repository = ResearchChatRepository(db)
        self._project_knowledge = project_knowledge or ProjectKnowledgeService(db)

    async def execute(
        self, arguments: SearchProjectDocumentsArguments | dict[str, Any]
    ) -> list[SearchProjectDocumentsResult]:
        parsed = SearchProjectDocumentsArguments.model_validate(arguments)
        session = self._repository.get_owned_session(
            session_id=self._session_id,
            user_id=self._current_user_id,
        )
        if session is None:
            raise CurrentConversationNotFoundError(
                "Current research conversation was not found"
            )
        sources = await self._project_knowledge.search(
            project_id=session.project_id,
            query=parsed.query,
        )
        return [
            SearchProjectDocumentsResult(
                content=source.content,
                filename=source.filename,
                file_id=source.file_id,
                chunk_id=source.chunk_id,
                score=source.score,
            )
            for source in sources
        ]
