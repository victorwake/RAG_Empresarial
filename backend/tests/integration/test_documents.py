"""Pruebas de integración de gestión documental."""

import hashlib
import uuid
from datetime import UTC, datetime

from app.models.enums import DocumentStatus, JobStatus
from app.models.organization import Organization
from app.models.user import User
from app.services.file_validation import ALLOWED_MIME_BY_EXTENSION
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import (
    DOCX_BYTES,
    PDF_BYTES,
    TXT_BYTES,
    auth_headers,
    create_document,
    create_processing_job,
)


def _upload(client: AsyncClient, user: User, *, filename: str, content: bytes, mime: str):
    return client.post(
        "/api/v1/documents",
        files={"file": (filename, content, mime)},
        headers=auth_headers(user),
    )


async def test_upload_pdf_returns_202_and_enqueues_ingestion(
    client: AsyncClient, admin_a: User, fake_queue
) -> None:
    response = await _upload(
        client, admin_a, filename="informe.pdf", content=PDF_BYTES, mime="application/pdf"
    )

    assert response.status_code == 202
    body = response.json()
    assert body["filename"] == "informe.pdf"
    assert body["original_filename"] == "informe.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["file_size"] == len(PDF_BYTES)
    assert body["status"] == "PENDING"
    assert body["page_count"] is None
    assert body["checksum"] == hashlib.sha256(PDF_BYTES).hexdigest()
    assert body["uploaded_by"] == str(admin_a.id)
    assert body["organization_id"] == str(admin_a.organization_id)
    assert len(fake_queue.ingestions) == 1
    assert fake_queue.ingestions[0][0] == uuid.UUID(body["id"])


async def test_upload_docx_and_txt_are_accepted(client: AsyncClient, admin_a: User) -> None:
    docx = await _upload(
        client,
        admin_a,
        filename="memoria.docx",
        content=DOCX_BYTES,
        mime=ALLOWED_MIME_BY_EXTENSION["docx"],
    )
    txt = await _upload(
        client, admin_a, filename="notas.txt", content=TXT_BYTES, mime="text/plain"
    )

    assert docx.status_code == 202
    assert docx.json()["mime_type"] == ALLOWED_MIME_BY_EXTENSION["docx"]
    assert txt.status_code == 202
    assert txt.json()["mime_type"] == "text/plain"


async def test_upload_sanitizes_stored_filename(client: AsyncClient, admin_a: User) -> None:
    response = await _upload(
        client,
        admin_a,
        filename="..\\..\\evil<>:name.pdf",
        content=PDF_BYTES,
        mime="application/pdf",
    )

    assert response.status_code == 202
    assert response.json()["filename"] == "evil_name.pdf"


async def test_upload_same_content_twice_conflicts(client: AsyncClient, admin_a: User) -> None:
    first = await _upload(
        client, admin_a, filename="informe.pdf", content=PDF_BYTES, mime="application/pdf"
    )
    second = await _upload(
        client, admin_a, filename="copia.pdf", content=PDF_BYTES, mime="application/pdf"
    )

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["detail"] == "Ya existe un documento idéntico en la organización."
    assert second.json()["existing_document_id"] == first.json()["id"]

    listing = await client.get("/api/v1/documents", headers=auth_headers(admin_a))
    assert listing.json()["total"] == 1


async def test_upload_with_disallowed_extension_is_rejected(
    client: AsyncClient, admin_a: User
) -> None:
    response = await _upload(
        client,
        admin_a,
        filename="virus.exe",
        content=b"MZ contenido ejecutable",
        mime="application/octet-stream",
    )

    assert response.status_code == 415


async def test_upload_with_declared_mime_mismatch_is_rejected(
    client: AsyncClient, admin_a: User
) -> None:
    response = await _upload(
        client, admin_a, filename="informe.pdf", content=PDF_BYTES, mime="text/plain"
    )

    assert response.status_code == 415


async def test_upload_with_wrong_signature_is_rejected(client: AsyncClient, admin_a: User) -> None:
    response = await _upload(
        client,
        admin_a,
        filename="informe.pdf",
        content=b"esto no es un pdf",
        mime="application/pdf",
    )

    assert response.status_code == 422


async def test_upload_empty_file_is_rejected(client: AsyncClient, admin_a: User) -> None:
    response = await _upload(
        client, admin_a, filename="vacio.pdf", content=b"", mime="application/pdf"
    )

    assert response.status_code == 422


async def test_upload_oversized_file_is_rejected(strict_client: AsyncClient, admin_a: User) -> None:
    oversized = b"%PDF-" + b"0" * (1024 * 1024 + 10)
    response = await _upload(
        strict_client, admin_a, filename="grande.pdf", content=oversized, mime="application/pdf"
    )

    assert response.status_code == 413


async def test_upload_without_multipart_body_is_rejected(
    client: AsyncClient, admin_a: User
) -> None:
    response = await client.post("/api/v1/documents", headers=auth_headers(admin_a))

    assert response.status_code == 422
    assert response.json()["status"] == 422


async def test_upload_requires_authentication(client: AsyncClient, admin_a: User) -> None:
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("informe.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 401


async def test_upload_requires_admin_role(client: AsyncClient, user_a: User) -> None:
    response = await _upload(
        client, user_a, filename="informe.pdf", content=PDF_BYTES, mime="application/pdf"
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Se requiere rol ADMIN."


async def test_list_documents_paginates_and_orders_by_created_at(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, org_a: Organization
) -> None:
    documents = []
    for index in range(3):
        document = await create_document(
            db_session, org_a, admin_a, filename=f"doc-{index}.pdf"
        )
        document.created_at = datetime(2026, 1, index + 1, 12, 0, tzinfo=UTC)
        documents.append(document)
    await db_session.flush()

    first_page = await client.get(
        "/api/v1/documents", params={"limit": 2}, headers=auth_headers(admin_a)
    )
    second_page = await client.get(
        "/api/v1/documents", params={"limit": 2, "offset": 2}, headers=auth_headers(admin_a)
    )

    assert first_page.status_code == 200
    body = first_page.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [
        str(documents[2].id),
        str(documents[1].id),
    ]
    second_body = second_page.json()
    assert [item["id"] for item in second_body["items"]] == [str(documents[0].id)]


async def test_list_documents_filters_by_status(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, org_a: Organization
) -> None:
    pending = await create_document(db_session, org_a, admin_a, filename="pendiente.pdf")
    completed = await create_document(db_session, org_a, admin_a, filename="listo.pdf")
    completed.status = DocumentStatus.COMPLETED
    await db_session.flush()

    response = await client.get(
        "/api/v1/documents", params={"status": "COMPLETED"}, headers=auth_headers(admin_a)
    )
    listing = await client.get("/api/v1/documents", headers=auth_headers(admin_a))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(completed.id)
    assert pending.id != completed.id
    assert listing.json()["total"] == 2


async def test_list_documents_searches_by_filename(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, org_a: Organization
) -> None:
    await create_document(db_session, org_a, admin_a, filename="contrato-2026.pdf")
    await create_document(db_session, org_a, admin_a, filename="acta-directorio.pdf")
    await db_session.flush()

    search = await client.get(
        "/api/v1/documents", params={"search": "contrato"}, headers=auth_headers(admin_a)
    )
    wildcard = await client.get(
        "/api/v1/documents", params={"search": "%"}, headers=auth_headers(admin_a)
    )

    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["filename"] == "contrato-2026.pdf"
    assert wildcard.json()["total"] == 0


async def test_list_documents_filters_by_uploaded_by(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, user_a: User, org_a: Organization
) -> None:
    own = await create_document(db_session, org_a, admin_a, filename="del-admin.pdf")
    other = await create_document(db_session, org_a, user_a, filename="del-usuario.pdf")
    await db_session.flush()

    response = await client.get(
        "/api/v1/documents", params={"uploaded_by": str(user_a.id)}, headers=auth_headers(admin_a)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(other.id)
    assert own.id != other.id


async def test_list_documents_rejects_invalid_pagination(
    client: AsyncClient, admin_a: User
) -> None:
    response = await client.get(
        "/api/v1/documents", params={"limit": 0}, headers=auth_headers(admin_a)
    )

    assert response.status_code == 422


async def test_get_document_returns_metadata(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, org_a: Organization
) -> None:
    document = await create_document(db_session, org_a, admin_a, filename="informe.pdf")
    await db_session.flush()

    response = await client.get(
        f"/api/v1/documents/{document.id}", headers=auth_headers(admin_a)
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(document.id)
    assert response.json()["filename"] == "informe.pdf"


async def test_get_unknown_document_returns_404(client: AsyncClient, admin_a: User) -> None:
    response = await client.get(
        f"/api/v1/documents/{uuid.uuid4()}", headers=auth_headers(admin_a)
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "El documento solicitado no existe."


async def test_delete_document_removes_row_and_file(
    client: AsyncClient, admin_a: User, tmp_path, fake_queue
) -> None:
    upload = await _upload(
        client, admin_a, filename="informe.pdf", content=PDF_BYTES, mime="application/pdf"
    )
    document_id = upload.json()["id"]
    stored_files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert len(stored_files) == 1

    deletion = await client.delete(
        f"/api/v1/documents/{document_id}", headers=auth_headers(admin_a)
    )

    assert deletion.status_code == 204
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []

    fetch = await client.get(f"/api/v1/documents/{document_id}", headers=auth_headers(admin_a))
    assert fetch.status_code == 404

    again = await client.delete(
        f"/api/v1/documents/{document_id}", headers=auth_headers(admin_a)
    )
    assert again.status_code == 404


async def test_delete_document_requires_admin_role(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, user_a: User, org_a: Organization
) -> None:
    document = await create_document(db_session, org_a, admin_a, filename="informe.pdf")
    await db_session.flush()

    response = await client.delete(
        f"/api/v1/documents/{document.id}", headers=auth_headers(user_a)
    )

    assert response.status_code == 403
    remaining = await client.get(f"/api/v1/documents/{document.id}", headers=auth_headers(admin_a))
    assert remaining.status_code == 200


async def test_reprocess_document_creates_job_and_resets_status(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_a: User,
    org_a: Organization,
    fake_queue,
) -> None:
    document = await create_document(db_session, org_a, admin_a, filename="informe.pdf")
    document.status = DocumentStatus.COMPLETED
    await create_processing_job(db_session, document, status=JobStatus.COMPLETED)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/documents/{document.id}/reprocess", headers=auth_headers(admin_a)
    )

    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"
    assert len(fake_queue.reprocesses) == 1
    assert fake_queue.reprocesses[0][0] == document.id


async def test_reprocess_document_conflicts_when_job_is_active(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, org_a: Organization, fake_queue
) -> None:
    document = await create_document(db_session, org_a, admin_a, filename="informe.pdf")
    await create_processing_job(db_session, document)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/documents/{document.id}/reprocess", headers=auth_headers(admin_a)
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "El documento ya tiene un trabajo de procesamiento activo."
    assert fake_queue.reprocesses == []


async def test_reprocess_document_requires_admin_role(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, user_a: User, org_a: Organization
) -> None:
    document = await create_document(db_session, org_a, admin_a, filename="informe.pdf")
    document.status = DocumentStatus.COMPLETED
    await create_processing_job(db_session, document, status=JobStatus.COMPLETED)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/documents/{document.id}/reprocess", headers=auth_headers(user_a)
    )

    assert response.status_code == 403


async def test_download_returns_file_content_and_headers(
    client: AsyncClient, admin_a: User
) -> None:
    upload = await _upload(
        client, admin_a, filename="informe.pdf", content=PDF_BYTES, mime="application/pdf"
    )
    document_id = upload.json()["id"]

    response = await client.get(
        f"/api/v1/documents/{document_id}/file", headers=auth_headers(admin_a)
    )

    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-length"] == str(len(PDF_BYTES))
    assert response.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''informe.pdf"
    )


async def test_download_after_delete_returns_404(client: AsyncClient, admin_a: User) -> None:
    upload = await _upload(
        client, admin_a, filename="informe.pdf", content=PDF_BYTES, mime="application/pdf"
    )
    document_id = upload.json()["id"]
    await client.delete(f"/api/v1/documents/{document_id}", headers=auth_headers(admin_a))

    response = await client.get(
        f"/api/v1/documents/{document_id}/file", headers=auth_headers(admin_a)
    )

    assert response.status_code == 404


async def test_user_role_can_list_get_and_download(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, user_a: User, org_a: Organization
) -> None:
    upload = await _upload(
        client, admin_a, filename="informe.pdf", content=PDF_BYTES, mime="application/pdf"
    )
    document_id = upload.json()["id"]

    listing = await client.get("/api/v1/documents", headers=auth_headers(user_a))
    detail = await client.get(f"/api/v1/documents/{document_id}", headers=auth_headers(user_a))
    download = await client.get(
        f"/api/v1/documents/{document_id}/file", headers=auth_headers(user_a)
    )

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert detail.status_code == 200
    assert download.status_code == 200
    assert download.content == PDF_BYTES
