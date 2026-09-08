from __future__ import annotations

import json
from collections.abc import Sequence

from app.models.course_project import CourseProject
from app.models.research import ResearchChatSession
from app.schemas.research_assistant import ResearchChatMessageInput


RECENT_MESSAGE_LIMIT = 10


class ConversationContextBuilder:
    """Build bounded OpenAI-compatible messages for a stateless chat provider.

    This class is deliberately provider-agnostic: it only serializes persisted
    conversation state and never invokes Spark or any other model client.
    """

    @classmethod
    def build(
        cls,
        *,
        conversation: ResearchChatSession,
        messages: Sequence[ResearchChatMessageInput],
        current_question: str,
    ) -> list[dict[str, str]]:
        question = current_question.strip()
        if not question:
            raise ValueError("current_question is required")

        effective_history = [
            message
            for message in messages
            if message.role in {"USER", "ASSISTANT"} and message.content.strip()
        ]
        # The normal send flow persists the current USER turn before creating
        # context. Exclude only that trailing persisted copy, then append the
        # question once below.
        if (
            effective_history
            and effective_history[-1].role == "USER"
            and effective_history[-1].content.strip() == question
        ):
            effective_history.pop()

        result: list[dict[str, str]] = []
        summary = conversation.conversation_summary
        if summary and summary.strip():
            result.append(
                {
                    "role": "system",
                    "content": "Earlier conversation summary:\n" + summary.strip(),
                }
            )
        result.extend(
            {
                "role": message.role.lower(),
                "content": message.content.strip(),
            }
            for message in effective_history[-RECENT_MESSAGE_LIMIT:]
        )
        result.append({"role": "user", "content": question})
        return result


class ResearchConversationContextBuilder:
    """Build the bounded, self-contained prompt sent to stateless Agents."""

    @classmethod
    def recent_messages(
        cls, messages: Sequence[ResearchChatMessageInput]
    ) -> list[ResearchChatMessageInput]:
        return [
            message
            for message in messages
            if message.role in {"USER", "ASSISTANT"}
        ][-RECENT_MESSAGE_LIMIT:]

    @classmethod
    def build(
        cls,
        *,
        project: CourseProject,
        conversation_summary: str | None,
        recent_messages: Sequence[ResearchChatMessageInput],
        current_question: str,
    ) -> str:
        project_context = [
            f"Project name: {project.title}",
            f"Topic: {project.topic}",
            f"Grade: {project.grade if project.grade is not None else 'Not specified'}",
            f"Class hours: {project.class_hours if project.class_hours is not None else 'Not specified'}",
        ]
        if project.student_level:
            project_context.append(f"Student level: {project.student_level}")
        if project.student_experience:
            project_context.append(f"Student experience: {project.student_experience}")
        if project.lesson_minutes is not None:
            project_context.append(f"Lesson minutes: {project.lesson_minutes}")
        if project.class_size is not None:
            project_context.append(f"Class size: {project.class_size}")
        if project.constraints_json:
            project_context.append(
                "Constraints: "
                + json.dumps(project.constraints_json, ensure_ascii=False)
            )
        if project.context_diagnosis_json:
            project_context.append(
                "Teaching context: "
                + json.dumps(project.context_diagnosis_json, ensure_ascii=False)
            )

        conversation = "\n".join(
            f"{message.role}: {message.content}" for message in recent_messages
        ) or "No recent conversation."
        summary = conversation_summary or "No earlier conversation summary."
        return "\n\n".join(
            (
                "[CURRENT PROJECT]\n" + "\n".join(project_context),
                "[EARLIER CONVERSATION SUMMARY]\n" + summary,
                "[RECENT CONVERSATION]\n" + conversation,
                "[CURRENT QUESTION]\n" + current_question,
                (
                    "[RESPONSE INSTRUCTION]\nUse the configured research knowledge "
                    "base and the context above to answer the current question."
                ),
            )
        )
