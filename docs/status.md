# Estado del proyecto — SmartDocs AI

Punto único de reanudación. Actualizar al cerrar cada etapa.

- **Actualizado:** 2026-11-11 (Etapa 6 verificada con Docker)
- **Rama:** `feat/etapa-6-motor-rag`
- **Etapa actual:** Etapa 6 cerrada y verificada con Docker; Etapa 7 es la siguiente.
- **Commit:** ver `git log -1 --oneline`. El cierre de Etapa 6 se commitea junto con estos documentos.

---

## 1. Etapas

| Etapa | Estado |
|---|---|
| 1 — Análisis y planificación | Cerrada |
| 2 — Backend, infraestructura y autenticación básica | Cerrada |
| 3 — Gestión documental | Cerrada |
| 4 — Extracción y procesamiento | Cerrada |
| 5 — Embeddings y búsqueda vectorial | Cerrada |
| 6 — Motor RAG | Cerrada |

---

## 2. Entregado en la Etapa 6

- Interfaz `LLMProvider` (Protocol) en `app/rag/llm_provider.py` con `model_name` y `generate(system_prompt, user_message)`.
- `GeminiLLMProvider` en `app/rag/gemini_llm.py` con timeouts, reintentos con backoff exponencial, `from_settings` y extracción de tokens/latencia.
- Prompt builder versionado en `app/rag/prompt_builder.py`: `SYSTEM_PROMPT_V1` con reglas anti prompt injection, `build_context_text` con límites de tokens, `build_full_prompt` que devuelve `(system, user)`.
- `RAGService` en `app/services/rag_service.py`: orquesta retrieval → política NO_INFO → prompt → LLM → validación → persistencia. Crea conversaciones automáticamente, persiste mensajes y fuentes.
- Modelos `Conversation`, `Message`, `MessageSource` con FK compuestas, CHECK constraints e índices según `database.md`.
- Migración `0005_conversations_y_mensajes` con tipos enum, tablas, FK, índices y CASCADE.
- Endpoints: `POST /api/v1/chat` (pregunta RAG), `GET /api/v1/chat/conversations` (lista), `GET /api/v1/chat/conversations/{id}` (detalle con mensajes).
- Schemas `ChatRequest`, `ChatResponse`, `ChatSource`, `ConversationSummary`, `ConversationsListResponse`, `MessageItem`, `ConversationDetailResponse`.
- `get_llm_provider()` en `app/api/dependencies.py` como dependency overridable.
- `FakeLLMProvider` en `conftest.py` para tests sin llamadas reales.
- Tests unitarios del prompt builder (10 casos) e integración del chat (9 casos): ANSWERED con fuentes, NO_INFO sin chunks, autenticación, creación de conversación, listado, detalle, 404 y aislamiento por organización.
- Política de "no información": si no hay chunks válidos, se responde `NO_INFO` sin llamar al LLM.
- Defensas anti prompt injection: delimitación XML del contexto, separación de roles, regla explícita en el prompt de no obedecer instrucciones dentro de documentos.

---

## 3. Entregado en la Etapa 5

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

- **Tests:** 163 pasando (0 fallando). Incluye 10 unitarios del prompt builder, 9 de integración del chat, 10 del chunker, 7 de búsqueda, y los tests de las etapas 1-4.
- **Cobertura:** 86 % total. `app/rag/prompt_builder.py` al 100 %, `app/services/rag_service.py` al 89 %, `app/document_processing` al 100 %.
- **Ruff:** sin errores en todo el código base.
- **Migraciones:** 5 migraciones (`0001`-`0005`), incluyendo `conversations`, `messages`, `message_sources`.
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
- El motor RAG y las conversaciones están implementados y verificados (Etapa 6). Faltan proxy TLS y frontend.
- Los modelos `Message.role` y `Message.status` se almacenan como `String(20)` en lugar de enum de PostgreSQL para simplificar la migración; el código de la API maneja ambos casos (enum y string).
- El umbral `min_score` se dejó en 0.35 como valor inicial; la calibración con dataset dorado se hace en la Etapa 9.
- La calibración del umbral con dataset dorado (ROADMAP §5.4) queda pendiente hasta que existan documentos reales.

---

## 7. Próximo paso: Etapa 7 — Frontend

1. Scaffolding del proyecto React + TypeScript + Vite.
2. Integrar login, logout y refresh automático.
3. Dashboard con métricas de documentos y consultas.
4. Gestión documental: subida, listado, estados.
5. Chat conversacional con historial y fuentes.

---

## 8. Documentos de referencia

- [`../README.md`](../README.md) — visión general y puesta en marcha.
- [`../ROADMAP.md`](../ROADMAP.md) — plan completo y checklists.
- [`architecture.md`](architecture.md) — capas y estado de implementación.
- [`api.md`](api.md) — contrato REST.
- [`database.md`](database.md) — modelo de datos y migraciones.
- [`security.md`](security.md) — reglas de seguridad y checklists.
- [`testing.md`](testing.md) — estrategia de pruebas.
- [`deployment.md`](deployment.md) — Docker y operación.
- [`decisions.md`](decisions.md) — ADRs.
