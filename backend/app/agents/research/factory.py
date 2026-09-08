from app.agents.research.base import ResearchAgentProvider
from app.agents.research.errors import ResearchAgentConfigurationError
from app.agents.research.mock_research_agent import MockResearchAgent
from app.agents.research.spark_research_agent import SparkResearchAgent
from app.core.config import settings


def build_research_agent_provider() -> ResearchAgentProvider:
    """Composition root for 研教智联 only; course design uses assistants.factory."""
    configured = settings.research_agent_provider
    provider_name = (
        configured.strip().lower()
        if configured and configured.strip()
        else ("mock" if settings.llm_provider.strip().lower() == "mock" else "spark_assistant")
    )
    if provider_name == "mock":
        return MockResearchAgent()
    if provider_name == "spark_assistant":
        return SparkResearchAgent()
    raise ResearchAgentConfigurationError(
        f"Unsupported RESEARCH_AGENT_PROVIDER: {settings.research_agent_provider}"
    )
