from app.assistants.base import ResearchAssistantProvider
from app.assistants.mock_research_assistant import MockResearchAssistant
from app.assistants.spark_client import SparkLLMClient
from app.assistants.spark_research_assistant import SparkResearchAssistant
from app.core.config import settings


class AssistantProviderConfigurationError(RuntimeError):
    """Raised at application composition time for invalid LLM configuration."""


def build_research_assistant_provider() -> ResearchAssistantProvider:
    """Application composition point; services must not import concrete providers."""

    provider = settings.llm_provider.strip().lower()
    if provider == "mock":
        return MockResearchAssistant()
    if provider == "spark":
        missing = [
            name
            for name, value in (
                ("SPARK_API_KEY", settings.spark_api_key),
                ("SPARK_API_BASE", settings.spark_api_base),
                ("SPARK_MODEL_ID", settings.spark_model_id),
            )
            if not value or not value.strip()
        ]
        if missing:
            raise AssistantProviderConfigurationError(
                f"Spark provider configuration is missing: {', '.join(missing)}"
            )
        return SparkResearchAssistant(client=SparkLLMClient())
    raise AssistantProviderConfigurationError(
        f"Unsupported LLM_PROVIDER: {settings.llm_provider}"
    )
