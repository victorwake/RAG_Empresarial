"""Tests de integración del endpoint de chat RAG."""

import uuid

import pytest
from app.models.document_chunk import DocumentChunk
from httpx import AsyncClient
from tests.conftest import (
    FakeEmbeddingProvider,
    auth_headers,
    build_pdf_bytes,
    create_document,
)


@pytest.mark.asyncio
async def test_chat_returns_answered_with_sources(
    client: AsyncClient,
    org_a,
    admin_a,
    db_session,
) -> None:
    """El endpoint de chat devuelve ANSWERED con fuentes cuando hay chunks."""
    # Crear un documento y un chunk
    document = await create_document(
        db_session, org_a, admin_a,
        filename="politica_rrhh.pdf",
        content=build_pdf_bytes("La politica de vacaciones permite 15 dias al ano."),
    )

    provider = FakeEmbeddingProvider(dimension=768)
    query = "Cuantos dias de vacaciones tengo?"
    embedding = await provider.embed_query(query)

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document.id,
        organization_id=org_a.id,
        chunk_index=0,
        content=(
            "La politica de vacaciones permite 15 dias laborales "
            "al ano para todos los empleados."
        ),
        embedding=embedding,
        embedding_model="fake-test-model",
        page_number=1,
        section="Vacaciones",
        metadata_={},
    )
    db_session.add(chunk)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/chat",
        json={"question": query},
        headers=auth_headers(admin_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ANSWERED"
    assert len(data["sources"]) > 0
    assert data["sources"][0]["document_id"] == str(document.id)
    assert data["sources"][0]["page_number"] == 1


@pytest.mark.asyncio
async def test_chat_returns_no_info_without_chunks(
    client: AsyncClient,
    org_a,
    admin_a,
) -> None:
    """El endpoint de chat devuelve NO_INFO cuando no hay chunks."""
    resp = await client.post(
        "/api/v1/chat",
        json={"question": "Cuantos dias de vacaciones tengo?"},
        headers=auth_headers(admin_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "NO_INFO"
    assert len(data["sources"]) == 0


@pytest.mark.asyncio
async def test_chat_requires_auth(client: AsyncClient) -> None:
    """El endpoint de chat requiere autenticación."""
    resp = await client.post(
        "/api/v1/chat",
        json={"question": "Hola"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_chat_creates_conversation(
    client: AsyncClient,
    org_a,
    admin_a,
) -> None:
    """El chat crea una conversación automáticamente si no se proporciona."""
    resp = await client.post(
        "/api/v1/chat",
        json={"question": "Pregunta de prueba"},
        headers=auth_headers(admin_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["message_id"] is not None


@pytest.mark.asyncio
async def test_list_conversations_returns_empty(
    client: AsyncClient,
    org_a,
    admin_a,
) -> None:
    """Listar conversaciones devuelve lista vacía al inicio."""
    resp = await client.get(
        "/api/v1/chat/conversations",
        headers=auth_headers(admin_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["conversations"] == []


@pytest.mark.asyncio
async def test_list_conversations_after_chat(
    client: AsyncClient,
    org_a,
    admin_a,
) -> None:
    """Después de un chat, la conversación aparece en la lista."""
    # Hacer un chat
    await client.post(
        "/api/v1/chat",
        json={"question": "Pregunta de prueba"},
        headers=auth_headers(admin_a),
    )

    resp = await client.get(
        "/api/v1/chat/conversations",
        headers=auth_headers(admin_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_conversation_detail(
    client: AsyncClient,
    org_a,
    admin_a,
) -> None:
    """Obtener el detalle de una conversación muestra los mensajes."""
    # Hacer un chat
    await client.post(
        "/api/v1/chat",
        json={"question": "Pregunta de prueba"},
        headers=auth_headers(admin_a),
    )

    # Obtener la conversación
    list_resp = await client.get(
        "/api/v1/chat/conversations",
        headers=auth_headers(admin_a),
    )
    conv_id = list_resp.json()["conversations"][0]["id"]

    detail_resp = await client.get(
        f"/api/v1/chat/conversations/{conv_id}",
        headers=auth_headers(admin_a),
    )
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["id"] == conv_id
    assert len(data["messages"]) >= 2  # user + assistant


@pytest.mark.asyncio
async def test_get_conversation_not_found(
    client: AsyncClient,
    org_a,
    admin_a,
) -> None:
    """Obtener una conversación inexistente devuelve 404."""
    resp = await client.get(
        f"/api/v1/chat/conversations/{uuid.uuid4()}",
        headers=auth_headers(admin_a),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_chat_filters_by_organization(
    client: AsyncClient,
    org_a,
    org_b,
    admin_a,
    admin_b,
    db_session,
) -> None:
    """Los chunks de otra organización no aparecen en los resultados."""
    # Crear un chunk en org_b
    document_b = await create_document(
        db_session, org_b, admin_b,
        filename="secreto.pdf",
        content=build_pdf_bytes("Informacion secreta de Globex."),
    )

    provider = FakeEmbeddingProvider(dimension=768)
    query = "Informacion secreta"
    embedding = await provider.embed_query(query)

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=document_b.id,
        organization_id=org_b.id,
        chunk_index=0,
        content="Informacion secreta de Globex que no debe verse.",
        embedding=embedding,
        embedding_model="fake-test-model",
        page_number=1,
        section="Secretos",
        metadata_={},
    )
    db_session.add(chunk)
    await db_session.flush()

    # admin_a busca — no debería ver el chunk de org_b
    resp = await client.post(
        "/api/v1/chat",
        json={"question": query},
        headers=auth_headers(admin_a),
    )
    assert resp.status_code == 200
    data = resp.json()
    # No debería tener fuentes de org_b
    for source in data["sources"]:
        assert source["document_id"] != str(document_b.id)
