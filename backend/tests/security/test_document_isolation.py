"""Pruebas de aislamiento multi-tenant de documentos."""

from app.models.document import Document
from app.models.organization import Organization
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import PDF_BYTES, auth_headers, create_document


async def _document_of_org_a(db_session, admin_a: User, org_a: Organization) -> Document:
    return await create_document(db_session, org_a, admin_a, filename="secreto.pdf")


async def test_other_organization_cannot_get_document(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, admin_b: User, org_a: Organization
) -> None:
    document = await _document_of_org_a(db_session, admin_a, org_a)
    await db_session.flush()

    response = await client.get(f"/api/v1/documents/{document.id}", headers=auth_headers(admin_b))

    assert response.status_code == 404


async def test_other_organization_cannot_delete_document(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, admin_b: User, org_a: Organization
) -> None:
    document = await _document_of_org_a(db_session, admin_a, org_a)
    await db_session.flush()

    response = await client.delete(
        f"/api/v1/documents/{document.id}", headers=auth_headers(admin_b)
    )

    assert response.status_code == 404
    still_there = await client.get(
        f"/api/v1/documents/{document.id}", headers=auth_headers(admin_a)
    )
    assert still_there.status_code == 200


async def test_other_organization_cannot_reprocess_document(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_a: User,
    admin_b: User,
    org_a: Organization,
    fake_queue,
) -> None:
    document = await _document_of_org_a(db_session, admin_a, org_a)
    await db_session.flush()

    response = await client.post(
        f"/api/v1/documents/{document.id}/reprocess", headers=auth_headers(admin_b)
    )

    assert response.status_code == 404
    assert fake_queue.reprocesses == []


async def test_other_organization_cannot_download_document(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, admin_b: User, org_a: Organization
) -> None:
    document = await _document_of_org_a(db_session, admin_a, org_a)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/documents/{document.id}/file", headers=auth_headers(admin_b)
    )

    assert response.status_code == 404


async def test_other_organization_listing_is_empty(
    client: AsyncClient, db_session: AsyncSession, admin_a: User, admin_b: User, org_a: Organization
) -> None:
    await _document_of_org_a(db_session, admin_a, org_a)
    await create_document(db_session, org_a, admin_a, filename="otro.pdf")
    await db_session.flush()

    response = await client.get("/api/v1/documents", headers=auth_headers(admin_b))
    own_listing = await client.get("/api/v1/documents", headers=auth_headers(admin_a))

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0
    assert own_listing.json()["total"] == 2


async def test_upload_is_scoped_to_own_organization(
    client: AsyncClient, admin_a: User, admin_b: User
) -> None:
    upload = await client.post(
        "/api/v1/documents",
        files={"file": ("informe.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_headers(admin_b),
    )

    listing = await client.get("/api/v1/documents", headers=auth_headers(admin_a))

    assert upload.status_code == 202
    assert upload.json()["organization_id"] == str(admin_b.organization_id)
    assert listing.json()["total"] == 0
