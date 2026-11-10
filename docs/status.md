# Estado del proyecto — SmartDocs AI

Punto único de reanudación. Actualizar al cerrar cada etapa.

- **Actualizado:** 2026-11-10
- **Rama:** `feat/etapa-3-gestion-documental`
- **Etapa actual:** Etapa 3 cerrada; Etapa 4 es la siguiente.
- **Commit:** ver `git log -1 --oneline`. El cierre de Etapa 3 se commitea junto con estos documentos.

---

## 1. Etapas

| Etapa | Estado |
|---|---|
| 1 — Análisis y planificación | Cerrada |
| 2 — Backend, infraestructura y autenticación básica | Cerrada |
| 3 — Gestión documental | Cerrada |
| 4 — Extracción y procesamiento | Próxima |

---

## 2. Entregado en la Etapa 3

- Entidades `Document` y `ProcessingJob` con migración `0003_documents_y_processing_jobs`.
- FK compuestas y `UNIQUE (organization_id, id)` en `documents` y `processing_jobs`; índice único parcial de jobs activos por documento.
- `FileStorage` (Protocol) y `LocalFileStorage` con nombres generados por el sistema y protección contra path traversal.
- `ProcessingQueue` (Protocol) y `FastAPIProcessingQueue` no durable sobre `BackgroundTasks` (ADR-004).
- Carga multipart con validación de extensión, MIME, firma mágica, tamaño y checksum SHA-256; detección de duplicados por organización (`409` con `existing_document_id`).
- Endpoints de documentos: carga, listado paginado, consulta, eliminación, reproceso y descarga del archivo original.
- Transiciones de estado `PENDING → PROCESSING → COMPLETED | FAILED` con claim atómico e `attempts`.
- Reconciliación de jobs huérfanos al arranque (marcan `FAILED` con motivo de interrupción).
- Job de ingesta con stub de extracción: completa el documento sin extraer texto (ADR-017; extracción real en Etapa 4).
- Tests unitarios de validación, integración de endpoints/procesamiento y aislamiento por organización en documentos.
- Excepciones nuevas: `413 Payload Too Large` y `415 Unsupported Media Type` con soporte de `extra` en `AppError`.

---

## 3. Verificación registrada

Última ejecución local:

- **Tests:** 87 pasan.
- **Cobertura:** 87 % total; módulos nuevos de Etapa 3 mayoritariamente al 100 % (routes/documents, document_service, repositorios y schemas al 100 %).
- **Ruff:** sin errores.
- **Migraciones:** ciclo `upgrade head → downgrade base → upgrade head` verificado en una base desechable.
- **Alembic:** `0003_documents_y_processing_jobs (head)` aplicada en la base de desarrollo `smartdocs`.
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

- El job de procesamiento es un stub: marca el documento `COMPLETED` sin extraer texto ni generar chunks (ADR-017). La extracción real se implementa en Etapa 4.
- La cola `FastAPIProcessingQueue` no es durable; se compensa con reconciliación al arranque, claim atómico y reproceso manual.
- `DELETE /documents/{id}` no bloquea por job activo: los jobs se eliminan en cascada y el job en vuelo detecta la eliminación y termina limpiamente.
- Las migraciones se ejecutan manualmente; el entrypoint automático queda como decisión futura.
- La suite de tests crea el esquema con `create_all`/`drop_all`; las migraciones se verifican por separado (ADR-016).
- Rate limiting y protección contra fuerza bruta quedan para una etapa posterior.
- No existen aún extractores de texto, chunks, pipeline RAG, proxy TLS ni frontend.

---

## 6. Próximo paso: Etapa 4 — Extracción y procesamiento

1. Definir la interfaz `TextExtractor` con resultado normalizado y metadatos.
2. Implementar `PDFProcessor` (PyMuPDF), `DOCXProcessor` (python-docx) y `TXTProcessor` con detección de codificación.
3. Normalizar espacios, saltos de línea y caracteres de control; preservar página/sección.
4. Detectar documentos sin texto extraíble y registrar el motivo.
5. Integrar la extracción en `ProcessingService.run_job` reemplazando el stub de Etapa 3.
6. Manejo de errores por archivo y por página; `FAILED` con mensaje accionable.
7. Tests con archivos de ejemplo válidos, corruptos y vacíos.

Criterio de cierre: cargar un archivo de cada formato y obtener su contenido textual correctamente extraído, con metadatos y errores controlados.

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
