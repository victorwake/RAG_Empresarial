# Estado del proyecto — SmartDocs AI

Punto único de reanudación. Actualizar al cerrar cada etapa.

- **Actualizado:** 2026-11-08
- **Rama:** `feat/etapa-2-backend-base`
- **Etapa actual:** Etapa 2 cerrada; Etapa 3 es la siguiente.
- **Commit:** ver `git log -1 --oneline`. El cierre de Etapa 2 se commitea junto con estos documentos.

---

## 1. Etapas

| Etapa | Estado |
|---|---|
| 1 — Análisis y planificación | Cerrada |
| 2 — Backend, infraestructura y autenticación básica | Cerrada |
| 3 — Gestión documental | Próxima |

---

## 2. Entregado en la Etapa 2

- FastAPI con estructura modular, configuración por entorno y Swagger.
- PostgreSQL 16 + pgvector con Docker Compose y healthcheck.
- SQLAlchemy 2.0 async, sesión por request y Alembic.
- Modelos `Organization`, `User` y `RefreshToken`.
- Auth: login con `organization_slug`, refresh rotativo, logout idempotente y `GET /auth/me`.
- Access token JWT corto; refresh token JWT con `jti`/`ver` y hash SHA-256 persistido.
- Argon2id, política mínima de contraseña, 401 genérico y `TenantContext`.
- Logging estructurado con `request_id`, manejo global de errores y CORS.
- CLI `create-organization` y `create-admin`.
- Dockerfile multi-stage no-root, Compose, `.dockerignore` y `requirements.txt` de respaldo.
- Tests unitarios, de integración y de aislamiento por organización.

---

## 3. Verificación registrada

Última ejecución local:

- **Tests:** 24 pasan.
- **Cobertura:** 81 %.
- **Ruff:** sin errores.
- **Migraciones:** `upgrade` y `downgrade` verificados.
- **Docker:** imagen de API construida y healthy; `GET /health` responde 200.
- **Alembic en contenedor:** `0002_users_y_refresh_tokens (head)`.
- **CLI:** probado contra `smartdocs_test`, incluida la validación de organización duplicada.

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
- PostgreSQL de desarrollo: `smartdocs` en `localhost:5432`.
- Base de tests: `smartdocs_test` en el mismo contenedor; creada por `docker/postgres/init-test-db.sql`.
- `.env` local no versionado; `.env.example` es la plantilla.
- Contenedor `smartdocs-db` puede quedar corriendo; `smartdocs-api` se detuvo tras la validación.
- Los emails de prueba usan dominios `.com`; `email-validator` rechaza `.test`.

---

## 5. Desviaciones y deuda conocida

- Las migraciones se ejecutan manualmente; el entrypoint automático queda como decisión futura.
- La suite de tests crea el esquema con `create_all`/`drop_all`; las migraciones se verifican por separado (ADR-016).
- Rate limiting y protección contra fuerza bruta quedan para una etapa posterior.
- La cola de procesamiento se implementará en la Etapa 3 con `BackgroundTasks`; no será durable.
- No existen aún proxy TLS, frontend, almacenamiento abstracto ni pipeline RAG.
- El refresh token se guarda hasheado; el token en claro solo lo posee el cliente.

---

## 6. Próximo paso: Etapa 3 — Gestión documental

1. Crear entidades `Document` y `ProcessingJob` con migración `0003`.
2. Aplicar FK compuestas y `UNIQUE (organization_id, id)` según `docs/database.md`.
3. Implementar `FileStorage` y `LocalFileStorage`.
4. Implementar carga multipart con validación de extensión, MIME, tamaño, checksum y duplicados.
5. Implementar listado, consulta, eliminación y reproceso.
6. Implementar `ProcessingQueue` y `FastAPIProcessingQueue` no durable.
7. Implementar transiciones de estado y reconciliación de jobs huérfanos.
8. Agregar tests de carga, validación, duplicados, borrado y estados.

Criterio de cierre: cargar PDF, DOCX y TXT por API, listarlos, consultarlos, eliminarlos y reprocesarlos con estados correctos.

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
