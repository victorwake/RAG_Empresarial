# Estado del proyecto — SmartDocs AI

Punto único de reanudación. Actualizar al cerrar cada etapa.

- **Actualizado:** 2026-11-10
- **Rama:** `feat/etapa-4-extraccion`
- **Etapa actual:** Etapa 4 cerrada; Etapa 5 es la siguiente.
- **Commit:** ver `git log -1 --oneline`. El cierre de Etapa 4 se commitea junto con estos documentos.

---

## 1. Etapas

| Etapa | Estado |
|---|---|
| 1 — Análisis y planificación | Cerrada |
| 2 — Backend, infraestructura y autenticación básica | Cerrada |
| 3 — Gestión documental | Cerrada |
| 4 — Extracción y procesamiento | Cerrada |
| 5 — Embeddings y búsqueda vectorial | Próxima |

---

## 2. Entregado en la Etapa 4

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

## 3. Verificación registrada

Última ejecución local:

- **Tests:** 125 pasan.
- **Cobertura:** 89 % total; `app/document_processing` al 100 % en todos sus módulos; `processing_service` al 99 %.
- **Ruff:** sin errores.
- **Migraciones:** sin cambios en esta etapa; `0003_documents_y_processing_jobs` sigue siendo `head`.
- **Docker:** contenedor `smartdocs-db` en ejecución; la imagen de API no se reconstruyó en esta etapa.

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
docker compose run --rm api alembic current
```

> `uv` no está en el `PATH` en este entorno; usar `python -m uv` donde corresponda.

---

## 4. Entorno local

- Python 3.12.16 instalado por `uv`.
- PostgreSQL de desarrollo: `smartdocs` en `localhost:5432`, con migración `0003` aplicada.
- Base de tests: `smartdocs_test` en el mismo contenedor; creada por `docker/postgres/init-test-db.sql`.
- `.env` local no versionado; `.env.example` es la plantilla.
- Contenedor `smartdocs-db` puede quedar corriendo; `smartdocs-api` se detuvo tras la validación de Etapa 2.
- Los emails de prueba usan dominios `.com`; `email-validator` rechaza `.test`.

---

## 5. Desviaciones y deuda conocida

- El texto extraído no se persiste: se extrae de nuevo al reprocesar (ADR-018). Los chunks de la Etapa 5 serán la representación persistida.
- OCR de PDFs escaneados fuera de alcance: fallan con mensaje accionable; la interfaz `TextExtractor` permite incorporarlo en el futuro.
- La cola `FastAPIProcessingQueue` no es durable; se compensa con reconciliación al arranque, claim atómico y reproceso manual.
- `DELETE /documents/{id}` no bloquea por job activo: los jobs se eliminan en cascada y el job en vuelo detecta la eliminación y termina limpiamente.
- Las migraciones se ejecutan manualmente; el entrypoint automático queda como decisión futura.
- La suite de tests crea el esquema con `create_all`/`drop_all`; las migraciones se verifican por separado (ADR-016).
- Rate limiting y protección contra fuerza bruta quedan para una etapa posterior.
- No existen aún chunks, pipeline RAG, proxy TLS ni frontend.

---

## 6. Próximo paso: Etapa 5 — Embeddings y búsqueda vectorial

1. Implementar chunking por tokens con overlap configurable y `page_number`/metadatos por chunk.
2. Definir interfaz `EmbeddingProvider` y proveedor Gemini por defecto con lotes y reintentos.
3. Crear entidad `DocumentChunk` con columna `vector(N)` (migración `0004` reservada) e índice ANN.
4. Búsqueda semántica con `top_k` y `min_score` configurables y filtros por organización.
5. Calibrar el umbral con dataset dorado antes de cerrar la etapa.

Criterio de cierre: realizar una consulta y recuperar fragmentos pertinentes sin LLM, con métricas y umbral justificados.

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
