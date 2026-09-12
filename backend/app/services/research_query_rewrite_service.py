from __future__ import annotations

from collections.abc import Sequence

from app.assistants.spark_client import SparkLLMClient
from app.schemas.research_assistant import ResearchChatMessageInput


class ResearchQueryRewriteService:
    """Turn a contextual follow-up into a standalone local-retrieval query."""

    def __init__(self, client: SparkLLMClient | None = None) -> None:
        # SparkLLMClient validates configuration in its constructor. Keep it lazy
        # so application startup and first-turn fallback do not require an LLM call.
        self._client = client

    async def rewrite(
        self,
        *,
        conversation_summary: str | None,
        recent_messages: Sequence[ResearchChatMessageInput],
        current_question: str,
        project_title: str | None,
        project_topic: str | None,
        resource_filename: str | None = None,
    ) -> str:
        question = current_question.strip()
        if not question:
            raise ValueError("current_question is required")
        recent = "\n".join(
            f"{message.role}: {message.content.strip()}"
            for message in recent_messages[-8:]
            if message.role in {"USER", "ASSISTANT"} and message.content.strip()
        ) or "No recent conversation."
        prompt = (
            "Rewrite the current research-chat question into one standalone retrieval query. "
            "Resolve pronouns and omitted subjects from the conversation. Preserve the user's "
            "meaning and important terminology. Add only close synonyms useful for retrieval. "
            "Do not answer the question. Do not invent paper facts. Return only the query text, "
            "without quotes, labels, JSON, or Markdown.\n\n"
            f"Project title: {project_title or 'Not provided'}\n"
            f"Project topic: {project_topic or 'Not provided'}\n"
            f"Resource filename: {resource_filename or 'Project scope'}\n\n"
            "Conversation summary:\n"
            f"{conversation_summary or 'No earlier conversation summary.'}\n\n"
            f"Recent conversation:\n{recent}\n\n"
            f"Current question:\n{question}"
        )
        client = self._client or SparkLLMClient()
        rewritten = await client.chat(
            [
                {
                    "role": "system",
                    "content": "You produce concise standalone search queries for local academic retrieval.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=512,
        )
        result = rewritten.strip().strip("`\"' ")
        if not result:
            raise ValueError("Query rewrite returned an empty query")
        return result[:1000]
