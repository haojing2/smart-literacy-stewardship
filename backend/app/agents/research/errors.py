class ResearchAgentError(RuntimeError):
    """Base error for the research Assistant boundary."""


class ResearchAgentConfigurationError(ResearchAgentError):
    pass


class ResearchAgentConnectionError(ResearchAgentError):
    pass


class ResearchAgentTimeoutError(ResearchAgentError):
    pass


class ResearchAgentResponseError(ResearchAgentError):
    pass


class ResearchAgentParseError(ResearchAgentError):
    pass


class ResearchAgentContractError(ResearchAgentError):
    pass
