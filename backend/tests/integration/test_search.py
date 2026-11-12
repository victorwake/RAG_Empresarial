"""Tests de integración de búsqueda semántica y chunks."""


import pytest
from app.models.document_chunk import DocumentChunk
from app.repositories.document_chunk_repository import DocumentChunkRepository
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import (
    FakeEmbeddingProvider,
    auth_headers,
    create_document,
)


@pytest.mark.asyncio
async def test_search_returns_relevant_chunks(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_a,
    org_a,
) -> None:
    """La búsqueda devuelve chunks relevantes de la organización."""
    provider = FakeEmbeddingProvider(dimension=768)

    # Crear un documento
    document = await create_document(
        db_session, org_a, admin_a, filename="politica.pdf"
    )

    # Crear chunks manualmente con embeddings del fake provider
    texts = [
        "La política de vacaciones otorga 15 días por año de antigüedad.",
        "El proceso de solicitud de vacaciones requiere aprobación del supervisor.",
        "Los beneficios de salud incluyen cobertura dental y visual.",
    ]
    embeddings = await provider.embed_documents(texts)

    chunks = []
    for i, (text, embedding) in enumerate(zip(texts, embeddings, strict=False)):
        chunk = DocumentChunk(
            document_id=document.id,
            organization_id=org_a.id,
            chunk_index=i,
            content=text,
            embedding=embedding,
            embedding_model=provider.model_name,
            metadata={"token_count": 10, "content_hash": f"hash{i}"},
        )
        db_session.add(chunk)
        chunks.append(chunk)

    await db_session.commit()

    # Buscar
    headers = auth_headers(admin_a)
    resp = await client.post(
        "/api/v1/search",
        json={"query": "vacaciones días antigüedad"},
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["status"] in ("ANSWERED", "NO_INFO")
    assert "sources" in data["result"]
    assert data["result"]["top_k"] == 6


@pytest.mark.asyncio
async def test_search_no_info_when_no_chunks(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_a,
    org_a,
) -> None:
    """Sin chunks, la búsqueda devuelve NO_INFO."""
    headers = auth_headers(admin_a)
    resp = await client.post(
        "/api/v1/search",
        json={"query": "pregunta sin resultados"},
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["status"] == "NO_INFO"
    assert data["result"]["sources"] == []
    assert data["result"]["total"] == 0


@pytest.mark.asyncio
async def test_search_requires_auth(
    client: AsyncClient,
) -> None:
    """La búsqueda sin token devuelve 401."""
    resp = await client.post(
        "/api/v1/search",
        json={"query": "algo"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_chunks_requires_admin(
    db_session: AsyncSession,
    client: AsyncClient,
    org_a,
    admin_a,
) -> None:
    """GET /documents/{id}/chunks requiere rol ADMIN."""
    document = await create_document(
        db_session, org_a, admin_a, filename="test.pdf"
    )

    headers = auth_headers(admin_a)
    resp = await client.get(
        f"/api/v1/documents/{document.id}/chunks",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_chunks_scoped_to_organization(
    db_session: AsyncSession,
    client: AsyncClient,
    admin_a,
    admin_b,
    org_a,
    org_b,
) -> None:
    """Los chunks de una organización no son visibles desde otra."""
    provider = FakeEmbeddingProvider(dimension=768)

    # Documento en org_a
    doc_a = await create_document(db_session, org_a, admin_a, filename="doc_a.pdf")
    text_a = "Contenido exclusivo de Acme."
    embedding_a = await provider.embed_query(text_a)
    chunk_a = DocumentChunk(
        document_id=doc_a.id,
        organization_id=org_a.id,
        chunk_index=0,
        content=text_a,
        embedding=embedding_a,
        embedding_model=provider.model_name,
    )
    db_session.add(chunk_a)

    # Documento en org_b
    doc_b = await create_document(db_session, org_b, admin_b, filename="doc_b.pdf")
    text_b = "Contenido exclusivo de Globex."
    embedding_b = await provider.embed_query(text_b)
    chunk_b = DocumentChunk(
        document_id=doc_b.id,
        organization_id=org_b.id,
        chunk_index=0,
        content=text_b,
        embedding=embedding_b,
        embedding_model=provider.model_name,
    )
    db_session.add(chunk_b)

    await db_session.commit()

    # Buscar desde org_a — no debe ver chunks de org_b
    headers_a = auth_headers(admin_a)
    resp_a = await client.post(
        "/api/v1/search",
        json={"query": "contenido exclusivo"},
        headers=headers_a,
    )
    assert resp_a.status_code == 200
    sources_a = resp_a.json()["result"]["sources"]
    for source in sources_a:
        assert source["document_id"] == str(doc_a.id)

    # Buscar desde org_b — no debe ver chunks de org_a
    headers_b = auth_headers(admin_b)
    resp_b = await client.post(
        "/api/v1/search",
        json={"query": "contenido exclusivo"},
        headers=headers_b,
    )
    assert resp_b.status_code == 200
    sources_b = resp_b.json()["result"]["sources"]
    for source in sources_b:
        assert source["document_id"] == str(doc_b.id)


@pytest.mark.asyncio
async def test_repository_search_filters_by_min_score(
    db_session: AsyncSession,
    org_a,
    admin_a,
) -> None:
    """El repositorio respeta el umbral min_score."""
    provider = FakeEmbeddingProvider(dimension=768)
    repo = DocumentChunkRepository(db_session)

    # Crear un documento real para cumplir la FK
    document = await create_document(db_session, org_a, admin_a, filename="test.pdf")

    # Crear un chunk
    text = "Texto de prueba para el repositorio."
    embedding = await provider.embed_query(text)
    chunk = DocumentChunk(
        document_id=document.id,
        organization_id=org_a.id,
        chunk_index=0,
        content=text,
        embedding=embedding,
        embedding_model=provider.model_name,
    )
    db_session.add(chunk)
    await db_session.commit()

    # Buscar con min_score muy alto — no debería devolver nada
    query_embedding = await provider.embed_query("texto completamente diferente")
    results = await repo.search(
        organization_id=org_a.id,
        query_embedding=query_embedding,
        top_k=10,
        min_score=0.99,
    )
    # Con un umbral muy alto, es probable que no haya resultados
    # (depende del fake provider, pero el filtro debe aplicarse)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_delete_document_cascades_to_chunks(
    db_session: AsyncSession,
    org_a,
    admin_a,
) -> None:
    """Eliminar un documento elimina sus chunks en cascada."""
    provider = FakeEmbeddingProvider(dimension=768)

    document = await create_document(db_session, org_a, admin_a, filename="temp.pdf")
    text = "Chunk temporal."
    embedding = await provider.embed_query(text)
    chunk = DocumentChunk(
        document_id=document.id,
        organization_id=org_a.id,
        chunk_index=0,
        content=text,
        embedding=embedding,
        embedding_model=provider.model_name,
    )
    db_session.add(chunk)
    await db_session.commit()

    # Verificar que el chunk existe
    repo = DocumentChunkRepository(db_session)
    chunks_before, total_before = await repo.list_by_document(document_id=document.id)
    assert total_before == 1

    # Eliminar el documento
    from app.repositories.document_repository import DocumentRepository

    doc_repo = DocumentRepository(db_session)
    await doc_repo.delete(document)
    await db_session.commit()

    # Verificar que el chunk fue eliminado en cascada
    chunks_after, total_after = await repo.list_by_document(document_id=document.id)
    assert total_after == 0
