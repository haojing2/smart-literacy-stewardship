from app.services.knowledge_base_path_service import KnowledgeBasePathService


def test_project_knowledge_base_layout_is_created_on_demand(tmp_path) -> None:
    service = KnowledgeBasePathService(tmp_path / "knowledge_bases")

    assert service.raw_dir(42) == tmp_path / "knowledge_bases" / "project_42" / "raw"
    assert service.parsed_dir(42).is_dir()
    assert service.index_dir(42).is_dir()


def test_project_knowledge_base_rejects_invalid_project_id(tmp_path) -> None:
    service = KnowledgeBasePathService(tmp_path)
    try:
        service.project_root(0)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid project id must be rejected")


def test_raw_file_collision_can_use_a_suffixed_name(tmp_path) -> None:
    service = KnowledgeBasePathService(tmp_path)
    first = service.raw_file(3, "paper.pdf")
    first.write_bytes(b"first")
    replacement = first.with_name(f"{first.stem} (1){first.suffix}")
    assert replacement.name == "paper (1).pdf"
    assert first.read_bytes() == b"first"
