from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.course_project import CourseProject
from app.models.research import (
    ResearchAnalysis,
    ResearchChatMessage,
    ResearchChatSession,
    ResearchResource,
)
from app.models.user import SysUser
from app.repositories.research_resource_repository import ResearchResourceRepository
from app.services.document_parser_service import (
    DocumentParserService,
    DocumentParsingError,
)


@pytest.fixture(autouse=True)
def isolated_research_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    storage_root = tmp_path / "research"
    knowledge_base_root = tmp_path / "knowledge_bases"
    monkeypatch.setattr(settings, "research_storage_root", storage_root)
    monkeypatch.setattr(settings, "knowledge_base_root", knowledge_base_root)
    return knowledge_base_root


def create_project(db: Session, user: SysUser, *, deleted: bool = False) -> CourseProject:
    project = CourseProject(
        user_id=user.id,
        title="研究资源测试项目",
        topic="AI 素养",
        project_type="NEW_TOPIC",
        workflow_state="DRAFT",
        stale_sections_json=[],
        is_deleted=deleted,
    )
    db.add(project)
    db.commit()
    return project


def make_docx(text: str = "研究报告正文") -> bytes:
    content = BytesIO()
    with ZipFile(content, "w") as document:
        document.writestr("[Content_Types].xml", "<Types />")
        document.writestr(
            "word/document.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
                f"{text}</w:t></w:r></w:p></w:body></w:document>"
            ),
        )
    return content.getvalue()


def make_blank_pdf() -> bytes:
    content = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(content)
    return content.getvalue()


def make_text_pdf(text: str = "Research evidence for collaborative learning") -> bytes:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


def test_upload_pdf_persists_owned_resource_and_file(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
    isolated_research_storage: Path,
) -> None:
    project = create_project(db, teacher)
    payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"

    response = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("论文.pdf", payload, "application/pdf")},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data == {
        "resourceId": data["resourceId"],
        "fileName": "论文.pdf",
        "mimeType": "application/pdf",
        "fileSize": len(payload),
        "processingStatus": "UPLOADED",
        "indexStatus": "pending",
    }

    resource = db.get(ResearchResource, data["resourceId"])
    assert resource is not None
    assert resource.user_id == teacher.id
    assert resource.project_id == project.id
    assert resource.processing_status == "UPLOADED"
    assert resource.storage_key.startswith(f"project_{project.id}/raw/")
    stored_file = isolated_research_storage / Path(resource.storage_key)
    assert stored_file.read_bytes() == payload
    assert stored_file.name == "论文.pdf"


def test_pdf_upload_extract_and_agent_analysis_chain(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = create_project(db, teacher)
    upload = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("study.pdf", make_text_pdf(), "application/pdf")},
    )
    assert upload.status_code == 201
    resource_id = upload.json()["data"]["resourceId"]

    extracted = client.post(
        f"/api/v1/research-resources/{resource_id}/extract-text",
        headers=auth_headers,
    )
    assert extracted.status_code == 200
    assert extracted.json()["data"]["processingStatus"] == "TEXT_EXTRACTED"
    assert extracted.json()["data"]["extractedText"].strip()

    analyzed = client.post(
        f"/api/v1/projects/{project.id}/research-chat/sessions",
        headers=auth_headers,
        json={"resourceId": resource_id},
    )
    assert analyzed.status_code == 201
    assert analyzed.json()["data"]["latestAnalysis"] is not None
    resource = db.get(ResearchResource, resource_id)
    assert resource is not None
    assert resource.processing_status == "TEXT_EXTRACTED"
    assert resource.extracted_text
    assert db.scalar(
        select(func.count()).select_from(ResearchAnalysis).where(
            ResearchAnalysis.resource_id == resource_id
        )
    ) == 1


def test_upload_docx_is_supported(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = create_project(db, teacher)
    payload = make_docx()
    response = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={
            "file": (
                "report.docx",
                payload,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201
    assert response.json()["data"]["mimeType"].endswith("wordprocessingml.document")


def test_upload_deduplicates_identical_content_within_one_project(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
    isolated_research_storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = create_project(db, teacher)
    payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    parse_calls: list[Path] = []

    def parse_pdf_to_markdown(
        self: DocumentParserService, *, project_id: int, pdf_path: Path
    ) -> str:
        parse_calls.append(pdf_path)
        return "# Parsed paper"

    monkeypatch.setattr(
        DocumentParserService, "parse_pdf_to_markdown", parse_pdf_to_markdown
    )

    first = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("first.pdf", payload, "application/pdf")},
    )
    second = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("renamed-copy.pdf", payload, "application/pdf")},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["data"] == first.json()["data"]
    assert db.scalar(select(func.count()).select_from(ResearchResource)) == 1
    assert parse_calls == []
    raw_dir = isolated_research_storage / f"project_{project.id}" / "raw"
    assert len(list(raw_dir.iterdir())) == 1


def test_upload_does_not_start_local_pdf_indexing(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = create_project(db, teacher)
    calls: list[tuple[int, Path]] = []

    def parse_pdf_to_markdown(
        self: DocumentParserService, *, project_id: int, pdf_path: Path
    ) -> str:
        calls.append((project_id, pdf_path))
        return "# Parsed paper"

    monkeypatch.setattr(
        DocumentParserService, "parse_pdf_to_markdown", parse_pdf_to_markdown
    )
    response = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("paper.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )

    assert response.status_code == 201
    resource = db.get(ResearchResource, response.json()["data"]["resourceId"])
    assert resource is not None
    assert calls == []
    assert resource.file_hash == resource.sha256
    assert resource.index_status == "pending"
    assert resource.parsed_path is None
    assert resource.parse_error is None


def test_upload_is_not_affected_by_disabled_local_parser(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
    isolated_research_storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = create_project(db, teacher)

    def fail_parse(*args: object, **kwargs: object) -> str:
        raise DocumentParsingError("unable to parse this PDF")

    monkeypatch.setattr(DocumentParserService, "parse_pdf_to_markdown", fail_parse)
    response = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("paper.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )

    assert response.status_code == 201
    resource = db.get(ResearchResource, response.json()["data"]["resourceId"])
    assert resource is not None
    assert resource.index_status == "pending"
    assert resource.parse_error is None
    assert (isolated_research_storage / resource.storage_key).is_file()


def test_upload_allows_identical_content_in_different_projects(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    first_project = create_project(db, teacher)
    second_project = create_project(db, teacher)
    payload = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"

    first = client.post(
        f"/api/v1/projects/{first_project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("paper.pdf", payload, "application/pdf")},
    )
    second = client.post(
        f"/api/v1/projects/{second_project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("paper.pdf", payload, "application/pdf")},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["resourceId"] != second.json()["data"]["resourceId"]
    assert db.scalar(select(func.count()).select_from(ResearchResource)) == 2


def test_upload_requires_authentication(
    client: TestClient,
    db: Session,
    teacher: SysUser,
) -> None:
    project = create_project(db, teacher)
    response = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        files={"file": ("paper.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )
    assert response.status_code == 401
    assert db.scalar(select(func.count()).select_from(ResearchResource)) == 0


def test_upload_rejects_foreign_and_soft_deleted_projects(
    client: TestClient,
    db: Session,
    other: SysUser,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    foreign_project = create_project(db, other)
    deleted_project = create_project(db, teacher, deleted=True)
    upload = {"file": ("paper.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")}

    foreign = client.post(
        f"/api/v1/projects/{foreign_project.id}/research-resources/upload",
        headers=auth_headers,
        files=upload,
    )
    deleted = client.post(
        f"/api/v1/projects/{deleted_project.id}/research-resources/upload",
        headers=auth_headers,
        files=upload,
    )

    assert foreign.status_code == 404
    assert deleted.status_code == 404
    assert db.scalar(select(func.count()).select_from(ResearchResource)) == 0


@pytest.mark.parametrize(
    ("file_name", "content"),
    [
        ("paper.txt", b"plain text"),
        ("fake.pdf", b"not a pdf"),
        ("fake.docx", b"not a docx"),
    ],
)
def test_upload_rejects_unsupported_or_spoofed_files(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
    isolated_research_storage: Path,
    file_name: str,
    content: bytes,
) -> None:
    project = create_project(db, teacher)
    response = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": (file_name, content, "application/octet-stream")},
    )
    assert response.status_code == 415
    assert db.scalar(select(func.count()).select_from(ResearchResource)) == 0
    assert not list(isolated_research_storage.rglob("*.*"))


def test_upload_does_not_create_analysis_or_chat_records(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = create_project(db, teacher)
    response = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("paper.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )
    assert response.status_code == 201
    assert db.scalar(select(func.count()).select_from(ResearchAnalysis)) == 0
    assert db.scalar(select(func.count()).select_from(ResearchChatSession)) == 0
    assert db.scalar(select(func.count()).select_from(ResearchChatMessage)) == 0


def test_database_failure_removes_newly_saved_file(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
    isolated_research_storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = create_project(db, teacher)

    def fail_create(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(ResearchResourceRepository, "create", fail_create)
    with pytest.raises(RuntimeError, match="simulated database failure"):
        client.post(
            f"/api/v1/projects/{project.id}/research-resources/upload",
            headers=auth_headers,
            files={"file": ("paper.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        )

    assert db.scalar(select(func.count()).select_from(ResearchResource)) == 0
    assert not list(isolated_research_storage.rglob("*.*"))


def test_extract_text_endpoint_persists_full_cleaned_docx_text(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = create_project(db, teacher)
    upload = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={
            "file": (
                "study.docx",
                make_docx("第一段   内容\u200b\n第二段完整内容"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    resource_id = upload.json()["data"]["resourceId"]

    response = client.post(
        f"/api/v1/research-resources/{resource_id}/extract-text",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resourceId"] == resource_id
    assert data["processingStatus"] == "TEXT_EXTRACTED"
    assert data["extractedText"] == "第一段 内容\n第二段完整内容"
    resource = db.get(ResearchResource, resource_id)
    db.refresh(resource)
    assert resource.processing_status == "TEXT_EXTRACTED"
    assert resource.extracted_text == data["extractedText"]
    assert resource.error_message is None


def test_extract_text_passes_through_text_extracting_state(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = create_project(db, teacher)
    upload = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("study.docx", make_docx(), "application/octet-stream")},
    )
    resource_id = upload.json()["data"]["resourceId"]
    observed_statuses: list[str] = []

    def observe_status(*args: object, **kwargs: object) -> str:
        resource = db.get(ResearchResource, resource_id)
        db.refresh(resource)
        observed_statuses.append(resource.processing_status)
        return "完整正文"

    monkeypatch.setattr(DocumentParserService, "parse", observe_status)
    response = client.post(
        f"/api/v1/research-resources/{resource_id}/extract-text",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert observed_statuses == ["TEXT_EXTRACTING"]


def test_extract_text_failure_persists_clear_error(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = create_project(db, teacher)
    upload = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("scanned.pdf", make_blank_pdf(), "application/pdf")},
    )
    resource_id = upload.json()["data"]["resourceId"]

    response = client.post(
        f"/api/v1/research-resources/{resource_id}/extract-text",
        headers=auth_headers,
    )

    assert response.status_code == 422
    resource = db.get(ResearchResource, resource_id)
    db.refresh(resource)
    assert resource.processing_status == "FAILED"
    assert resource.extracted_text is None
    assert resource.error_message
    assert "scanned PDF" in resource.error_message
    assert "OCR is not supported" in resource.error_message


def test_extract_text_requires_authentication(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    auth_headers: dict[str, str],
) -> None:
    project = create_project(db, teacher)
    upload = client.post(
        f"/api/v1/projects/{project.id}/research-resources/upload",
        headers=auth_headers,
        files={"file": ("study.docx", make_docx(), "application/octet-stream")},
    )
    resource_id = upload.json()["data"]["resourceId"]
    response = client.post(f"/api/v1/research-resources/{resource_id}/extract-text")
    assert response.status_code == 401


def test_extract_text_rejects_foreign_or_deleted_project_resources(
    client: TestClient,
    db: Session,
    teacher: SysUser,
    other: SysUser,
    auth_headers: dict[str, str],
) -> None:
    foreign_project = create_project(db, other)
    deleted_project = create_project(db, teacher, deleted=True)
    resources = [
        ResearchResource(
            project_id=foreign_project.id,
            user_id=other.id,
            original_filename="foreign.pdf",
            storage_key=f"{other.id}/{foreign_project.id}/foreign.pdf",
            media_type="application/pdf",
            size_bytes=10,
            sha256="a" * 64,
            processing_status="UPLOADED",
        ),
        ResearchResource(
            project_id=deleted_project.id,
            user_id=teacher.id,
            original_filename="deleted.pdf",
            storage_key=f"{teacher.id}/{deleted_project.id}/deleted.pdf",
            media_type="application/pdf",
            size_bytes=10,
            sha256="b" * 64,
            processing_status="UPLOADED",
        ),
    ]
    db.add_all(resources)
    db.commit()

    for resource in resources:
        response = client.post(
            f"/api/v1/research-resources/{resource.id}/extract-text",
            headers=auth_headers,
        )
        assert response.status_code == 404
        db.refresh(resource)
        assert resource.processing_status == "UPLOADED"
