from app.services.chunk_service import ChunkService, ChunkingError


class StubSentenceSplitter:
    def __init__(self) -> None:
        self.received: str | None = None

    def split_text(self, text: str) -> list[str]:
        self.received = text
        return ["# Context\n\nFirst finding.", "Second finding."]


def test_chunk_markdown_keeps_required_file_metadata() -> None:
    splitter = StubSentenceSplitter()
    chunks = ChunkService(splitter=splitter).chunk_markdown(
        markdown="# Context\n\nFirst finding. Second finding.",
        project_id=1013,
        file_id=88,
        filename="paper.md",
    )

    assert splitter.received == "# Context\n\nFirst finding. Second finding."
    assert [(chunk.chunk_index, chunk.content) for chunk in chunks] == [
        (0, "# Context\n\nFirst finding."),
        (1, "Second finding."),
    ]
    assert all(chunk.project_id == 1013 for chunk in chunks)
    assert all(chunk.file_id == 88 for chunk in chunks)
    assert all(chunk.filename == "paper.md" for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == 2


def test_chunk_service_uses_centrally_supplied_parameters() -> None:
    service = ChunkService(chunk_size=1000, chunk_overlap=120, splitter=StubSentenceSplitter())
    assert service.chunk_size == 1000
    assert service.chunk_overlap == 120


def test_chunk_service_rejects_invalid_inputs() -> None:
    service = ChunkService(splitter=StubSentenceSplitter())
    try:
        service.chunk_markdown(
            markdown=" ", project_id=1, file_id=1, filename="paper.md"
        )
    except ChunkingError as exc:
        assert "Markdown content" in str(exc)
    else:
        raise AssertionError("empty Markdown should not be chunked")
