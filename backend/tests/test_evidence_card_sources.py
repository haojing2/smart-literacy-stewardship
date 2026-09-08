from app.schemas.evidence_card import EvidenceCardSource


def test_uploaded_resource_source_keeps_file_provenance() -> None:
    source = EvidenceCardSource(
        source_type="UPLOADED_RESOURCE",
        source_label="study.pdf",
        project_id=1,
        resource_id=2,
        original_filename="study.pdf",
        media_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
    )
    assert source.source_label == "study.pdf"
    assert source.sha256 == "a" * 64
    assert source.verification_note is None


def test_knowledge_base_source_has_no_fabricated_file_provenance() -> None:
    source = EvidenceCardSource(
        source_type="KNOWLEDGE_BASE",
        source_label="讯飞研教智联知识库",
        verification_note="知识库来源，具体文献依据待教师核查",
        project_id=1,
    )
    assert source.resource_id is None
    assert source.original_filename is None
    assert source.sha256 is None
    assert source.citations == []
