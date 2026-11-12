# Estado del proyecto — SmartDocs AI

Punto único de reanudación. Actualizar al cerrar cada etapa.

- **Actualizado:** 2026-11-11 (pruebas con Docker verificadas)
- **Rama:** `feat/etapa-5-embeddings`
- **Etapa actual:** Etapa 5 cerrada y verificada con Docker; Etapa 6 es la siguiente.
- **Commit:** ver `git log -1 --oneline`. El cierre de Etapa 5 se commitea junto con estos documentos.

---

## 1. Etapas

| Etapa | Estado |
|---|---|
| 1 — Análisis y planificación | Cerrada |
| 2 — Backend, infraestructura y autenticación básica | Cerrada |
| 3 — Gestión documental | Cerrada |
| 4 — Extracción y procesamiento | Cerrada |
| 5 — Embeddings y búsqueda vectorial | Cerrada |

---

## 2. Entregado en la Etapa 5

- Modelo `DocumentChunk` con FK compuesta `(organization_id, document_id)`, `UNIQUE(document_id, chunk_index)`, CHECK constraints, columna `embedding vector(N)` y `metadata JSONB`.
- Migración `0004_document_chunks_y_pgvector` con tabla completa, índice HNSW `vector_cosine_ops` y todos los índices de filtrado.
- Chunking por tokens con overlap configurable en `app/rag/chunker.py`: respeta límites de párrafo, conserva `page_number`/`section`, calcula `content_hash` SHA-256 y metadatos por chunk.
- Interfaz `EmbeddingProvider` en `app/rag/embedding_provider.py` con `embed_documents`, `embed_query`, `model_name` y `dimension`.
- `GeminiEmbeddingProvider` con lotes, reintentos con backoff exponencial, timeout y validación de dimensión.
- `DocumentChunkRepository` con `insert_many`, `delete_by_document`, `list_by_document` y `search` con similitud coseno, filtro por `organization_id`, `min_score` y `top_k`.
- Integración en `ProcessingService`: después de extraer texto, normaliza, chunking, genera embeddings, elimina chunks previos (idempotente) y persiste los nuevos.
- Endpoint `POST /api/v1/search` con autenticación, filtro por organización y respuesta `ANSWERED`/`NO_INFO`.
- Endpoint `GET /api/v1/documents/{id}/chunks` (ADMIN) con paginación.
- Schemas `ChunkResponse`, `ChunkListResponse`, `SearchRequest`, `SearchResponse`, `SearchSource`, `SearchResult`.
- `FakeEmbeddingProvider` en conftest para tests sin conexión a Gemini.
- Tests unitarios del chunker (10 casos) e integración de búsqueda y aislamiento (7 casos).
- Dependencias nuevas: `pgvector>=0.2`, `aiohttp>=3.9`.

---

## 3. Entregado en la Etapa 4

- Contrato común de extracción en `app/document_processing/base.py`: `TextExtractor` (Protocol), `ExtractionResult` (texto, páginas, `page_count`, metadatos y advertencias) y `ensure_extractable` con umbral mínimo de texto útil.
- `PDFProcessor` (PyMuPDF): texto por página, `page_count`, metadatos de título/autor, detección de archivo corrupto, PDF protegido con contraseña y PDF sin texto (posible escaneo); advertencias por página dañada sin abortar el documento.
- `DOCXProcessor` (python-docx): párrafos y tablas en orden documental (filas como celdas separadas por `|`), metadatos de `core_properties`; formatos sin paginación reportan `page_count` nulo.
- `TXTProcessor`: decodificación con detección de BOM (UTF-32/16/8), UTF-8 estricto y `charset-normalizer` como respaldo.
- `normalize_text`: unifica saltos de línea, elimina caracteres de control, une cortes de palabra con guion, colapsa espacios/tabs/NBSP, recorta líneas y limita líneas vacías consecutivas.
- `find_extractor` y `DEFAULT_EXTRACTORS` para selección por tipo MIME; `ProcessingService` ejecuta la extracción real vía `asyncio.to_thread` reemplazando el stub de ADR-017 (ADR-018).
- El texto extraído es transitorio: no se persiste; los chunks de la Etapa 5 serán la representación derivada (ADR-018).
- `documents.page_count` se completa al procesar (columna existente; sin migraciones nuevas).
- Mensajes de error accionables por caso: archivo vacío o truncado, tipo no soportado, corrupto, protegido y sin texto extraíble.
- Tests unitarios del normalizador y de cada extractor (incluidos cifrado, corrupción y advertencias) e integración del servicio con PDF/DOCX/TXT reales; builders de archivos reales en `conftest.py`.

---

## 4. Verificación registrada

Última ejecución con Docker activo (2026-11-11):

- **Tests:** 142 pasando (100 %). Incluye 10 unitarios del chunker, 7 de búsqueda semántica, 16 de processing con embeddings, y todos los tests de auth, documentos, y aislamiento multi-tenant.
- **Cobertura:** 87 % total. `app/document_processing` al 100 %, `app/rag/chunker.py` al 99 %, `app/repositories/document_chunk_repository.py` al 100 %, `app/api/routes/search.py` al 100 %.
- **Ruff:** sin errores en todo el código base.
- **Migraciones:** 4 migraciones aplicadas (`0001`-`0004`), incluyendo `document_chunks` con índice HNSW.
- **Docker:** contenedor `smartdocs-db` corriendo con PostgreSQL + pgvector activo.

Comandos de referencia:

```bash
# Desde la raíz del repositorio
docker compose up -d db

# Desde backend/
python -m uv sync --dev
python -m uv run alembic upgrade head
python -m uv run pytest --cov=app
python -m uv run ruff check .

# API en Docker
docker compose up -d --build api
curl http://localhost:8000/health
```

> `uv` no está en el `PATH` en este entorno; usar `python -m uv` donde corresponda.

---

## 5. Entorno local

- Python 3.12.16 instalado por `uv`.
- PostgreSQL de desarrollo: `smartdocs` en `localhost:5432`, con migración `0004` aplicada (cuando Docker esté disponible).
- Base de tests: `smartdocs_test` en el mismo contenedor; creada por `docker/postgres/init-test-db.sql`.
- `.env` local no versionado; `.env.example` es la plantilla.
- Contenedor `smartdocs-db` puede quedar corriendo; `smartdocs-api` se detuvo tras la validación de Etapa 2.
- Los emails de prueba usan dominios `.com`; `email-validator` rechaza `.test`.

---

## 6. Desviaciones y deuda conocida

- El texto extraído se persiste como chunks (ADR-018 resuelto en Etapa 5). Al reprocesar se eliminan los chunks previos y se regeneran.
- OCR de PDFs escaneados fuera de alcance: fallan con mensaje accionable; la interfaz `TextExtractor` permite incorporarlo en el futuro.
- La cola `FastAPIProcessingQueue` no es durable; se compensa con reconciliación al arranque, claim atómico y reproceso manual.
- `DELETE /documents/{id}` elimina chunks en cascada a nivel de base de datos.
- Las migraciones se ejecutan manualmente; el entrypoint automático queda como decisión futura.
- La suite de tests crea el esquema con `create_all`/`drop_all`; las migraciones se verifican por separado (ADR-016).
- Rate limiting y protección contra fuerza bruta quedan para una etapa posterior.
- No existen aún conversaciones, motor RAG, proxy TLS ni frontend.
- El umbral `min_score` se dejó en 0.35 como valor inicial; la calibración con dataset dorado se hace en la Etapa 9.

---

## 7. Próximo paso: Etapa 6 — Motor RAG

1. Definir interfaz `LLMProvider` e implementar `GeminiLLMProvider`.
2. Construir el contexto con pregunta, fragmentos, metadatos e instrucciones.
3. Diseñar y versionar el prompt del sistema.
4. Implementar endpoint `POST /api/v1/conversations` y `POST /api/v1/conversations/{id}/messages`.
5. Política de "no información" cuando no hay contexto válido.
6. Validación de salida: fuentes existentes, formato, longitud.

---

## 7. Documentos de referencia

- [`../README.md`](../README.md) — visión general y puesta en marcha.
- [`../ROADMAP.md`](../ROADMAP.md) — plan completo y checklists.
- [`architecture.md`](architecture.md) — capas y estado de implementación.
- [`api.md`](api.md) — contrato REST.
- [`database.md`](database.md) — modelo de datos y migraciones.
- [`security.md`](security.md) — reglas de seguridad y checklists.
- [`testing.md`](testing.md) — estrategia de pruebas.
- [`deployment.md`](deployment.md) — Docker y operación.
- [`decisions.md`](decisions.md) — ADRs.
