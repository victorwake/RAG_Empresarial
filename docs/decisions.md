# Decisiones de arquitectura (ADR) — SmartDocs AI

Registro de decisiones estructurales, su contexto, consecuencias y estado.

- **Estados:** `Aceptada`, `Reemplazada`, `Diferida`, `Rechazada`.
- **Regla:** una decisión nueva que afecte la arquitectura se agrega aquí antes o junto con su implementación.
- **Formato:** contexto → decisión → consecuencias → alternativas consideradas.

---

## Índice

| ADR | Decisión | Estado |
|---|---|---|
| [ADR-001](#adr-001-monolito-modular-sin-langchain) | Monolito modular sin LangChain | Aceptada |
| [ADR-002](#adr-002-postgresql--pgvector) | PostgreSQL + pgvector | Aceptada |
| [ADR-003](#adr-003-gemini-con-capa-de-abstracción) | Gemini con capa de abstracción | Aceptada |
| [ADR-004](#adr-004-processingqueue-con-backgroundtasks-temporal) | `ProcessingQueue` con `BackgroundTasks` temporal | Aceptada |
| [ADR-005](#adr-005-react--typescript--vite) | React + TypeScript + Vite | Aceptada |
| [ADR-006](#adr-006-multi-tenancy-por-esquema-compartido) | Multi-tenancy por esquema compartido | Aceptada |
| [ADR-007](#adr-007-alembic-para-migraciones) | Alembic para migraciones | Aceptada |
| [ADR-008](#adr-008-uuid-como-clave-primaria) | UUID como clave primaria | Aceptada |
| [ADR-009](#adr-009-filestorage-con-almacenamiento-local-inicial) | `FileStorage` con almacenamiento local inicial | Aceptada |
| [ADR-010](#adr-010-umbral-de-retrieval-experimental-y-configurable) | Umbral de retrieval experimental y configurable | Aceptada |
| [ADR-011](#adr-011-refresh-tokens-revocables-persistidos) | Refresh tokens revocables persistidos | Aceptada |
| [ADR-012](#adr-012-contenido-documental-como-dato-no-confiable) | Contenido documental como dato no confiable | Aceptada |
| [ADR-013](#adr-013-decisión-de-hosting-diferida) | Decisión de hosting diferida | Diferida |
| [ADR-014](#adr-014-python-312--uv--ruff) | Python 3.12 + uv + Ruff | Aceptada |
| [ADR-015](#adr-015-login-con-organization_slug-y-claves-foráneas-compuestas) | Login con `organization_slug` y claves foráneas compuestas | Aceptada |
| [ADR-016](#adr-016-esquema-de-tests-con-create_all-y-migraciones-verificadas-aparte) | Esquema de tests con `create_all` y migraciones verificadas aparte | Aceptada |
| [ADR-017](#adr-017-job-de-ingesta-con-stub-de-extracción-en-etapa-3) | Job de ingesta con stub de extracción en Etapa 3 | Aceptada |

---

## ADR-001: Monolito modular sin LangChain

**Estado:** Aceptada.

**Contexto:**

El objetivo es comprender y poder explicar el pipeline RAG, no solo hacerlo funcionar. LangChain abstrae piezas clave (carga, splitting, retrieval, cadenas) y puede ocultar el comportamiento real.

**Decisión:**

- Implementar el pipeline RAG directamente con Python.
- Organizar el backend como monolito modular con capas claras.
- Usar interfaces propias para LLM, embeddings, storage, queue y extractores.
- Evaluar LangChain o LlamaIndex más adelante, sin reescribir la aplicación.

**Consecuencias:**

- Mayor control y comprensión de cada etapa.
- Más código propio inicial.
- Dependencias menos acopladas.
- Posibilidad de adoptar un framework después si aporta valor.

**Alternativas consideradas:**

- LangChain desde el inicio: más rápido de prototipar, menos transparente.
- LlamaIndex: útil para indexación, pero agrega abstracción innecesaria para el MVP.

---

## ADR-002: PostgreSQL + pgvector

**Estado:** Aceptada.

**Contexto:**

El sistema necesita datos relacionales (usuarios, documentos, conversaciones) y vectores (chunks). Agregar una base vectorial independiente aumenta la infraestructura y la complejidad operativa.

**Decisión:**

- Usar PostgreSQL 16 con la extensión pgvector.
- Almacenar vectores en `document_chunks.embedding`.
- Usar índice HNSW con similitud coseno.

**Consecuencias:**

- Una sola base para datos y vectores.
- Transacciones y filtros por organización en la misma consulta.
- Menos servicios que operar.
- Límites de escala menores que una base vectorial dedicada, aceptables para el MVP.

**Alternativas consideradas:**

- Qdrant, Weaviate, Pinecone: mejor escala vectorial, más infraestructura y sincronización.
- Búsqueda en memoria: no persistente, no apta para producción.

---

## ADR-003: Gemini con capa de abstracción

**Estado:** Aceptada.

**Contexto:**

El proyecto necesita generación y embeddings. Acoplar la lógica a un proveedor específico dificulta cambiar de modelo o de costo.

**Decisión:**

- Usar Gemini como proveedor por defecto para generación y embeddings.
- Definir `LLMProvider` y `EmbeddingProvider`.
- Configurar modelo y dimensión por entorno.
- Registrar modelo usado por consulta y por chunk.

**Consecuencias:**

- Menos proveedores y claves en el MVP.
- Cambio de proveedor localizado en adaptadores.
- La calidad depende del modelo elegido; se evalúa con el dataset dorado.

**Alternativas consideradas:**

- OpenAI para embeddings y Gemini para generación: dos proveedores, más configuración.
- Modelo local: sin costo por token, pero más recursos y calidad a validar.

---

## ADR-004: `ProcessingQueue` con `BackgroundTasks` temporal

**Estado:** Aceptada.

**Contexto:**

El procesamiento documental es lento y no debe bloquear la request. Para el MVP se busca simplicidad sin agregar Redis ni un worker.

**Decisión:**

- Definir la interfaz `ProcessingQueue`.
- Implementación inicial `FastAPIProcessingQueue` sobre `BackgroundTasks`.
- Documentar que **no es una cola durable**.
- Compensar con reconciliación al arranque de jobs `PENDING`/`PROCESSING`, idempotencia y reproceso manual.
- Migrar a Celery/Redis u otra cola cuando se justifique.

**Consecuencias:**

- Simplicidad operativa inicial.
- Riesgo de pérdida de trabajos ante reinicios.
- Sin reintentos automáticos ni garantía de orden.
- La interfaz permite migrar sin cambiar endpoints.

**Criterio de migración:**

- Concurrencia sostenida, reintentos confiables, múltiples instancias o reinicios frecuentes.

**Alternativas consideradas:**

- Celery + Redis desde el inicio: robusto, pero agrega infraestructura y configuración.
- Procesamiento sincrónico: bloquea la request, inaceptable.

---

## ADR-005: React + TypeScript + Vite

**Estado:** Aceptada.

**Contexto:**

El frontend debe ser mantenible y demostrar buenas prácticas. El documento original mencionaba React con JavaScript.

**Decisión:**

- React + TypeScript + Vite.
- React Router, TanStack Query y cliente API tipado.
- Vitest + Testing Library.

**Consecuencias:**

- Tipado y mejor mantenibilidad.
- Mayor esfuerzo inicial que JavaScript puro.
- Mejor alineación con prácticas actuales de la industria.

**Alternativas consideradas:**

- React + JavaScript: más simple, menos seguro ante cambios.
- Next.js: más framework del necesario para una SPA administrativa.

---

## ADR-006: Multi-tenancy por esquema compartido

**Estado:** Aceptada.

**Contexto:**

El sistema es empresarial y debe aislar datos por organización desde el MVP. Crear una base o esquema por organización agrega complejidad operativa.

**Decisión:**

- Esquema compartido con `organization_id` en todas las tablas de negocio.
- `organization_id` se deriva **solo** del token autenticado.
- Scoping obligatorio en repositorios y en la búsqueda vectorial.
- Respuesta `404` para recursos de otra organización.
- RLS como defensa en profundidad futura.
- FK compuestas obligatorias desde Etapa 3 (ver ADR-015).

**Consecuencias:**

- Aislamiento lógico garantizado por código y pruebas, reforzado con FK compuestas.
- Menor complejidad operativa.
- Riesgo si se omite un filtro; mitigado con repositorios base y tests obligatorios.
- RLS no se usa como sustituto en el MVP.

**Alternativas consideradas:**

- Base de datos por organización: aislamiento fuerte, mucha operación.
- Esquema por organización: intermedio, migraciones más complejas.
- RLS desde el inicio: valioso, pero no reemplaza el scoping y agrega complejidad.

---

## ADR-007: Alembic para migraciones

**Estado:** Aceptada.

**Contexto:**

El esquema evoluciona por etapas y debe ser reproducible en local, CI y producción.

**Decisión:**

- Usar Alembic con SQLAlchemy 2.0.
- Una migración por cambio lógico.
- Revisar autogenerate y escribir `downgrade`.
- Aplicar migraciones en un paso controlado.

**Consecuencias:**

- Esquema versionado y reproducible.
- Requiere disciplina al cambiar modelos.
- Facilita entornos de test y despliegues.

**Alternativas consideradas:**

- `create_all()`: no apto para producción ni cambios incrementales.

---

## ADR-008: UUID como clave primaria

**Estado:** Aceptada.

**Contexto:**

Los IDs se exponen en APIs y deben evitar enumeración y colisiones entre organizaciones.

**Decisión:**

- Usar UUID como PK en todas las entidades.
- Generar en la base con `gen_random_uuid()` y/o en la aplicación.
- No usar IDs secuenciales en la API.

**Consecuencias:**

- IDs no predecibles.
- Índices ligeramente más grandes que enteros.
- Facilidad para integraciones y migraciones.

**Alternativas consideradas:**

- Enteros autoincrementales: más compactos, pero enumerables.

---

## ADR-009: `FileStorage` con almacenamiento local inicial

**Estado:** Aceptada.

**Contexto:**

El MVP necesita almacenar archivos sin incorporar un servicio externo.

**Decisión:**

- Definir `FileStorage`.
- Implementación `LocalFileStorage` con volumen persistente.
- Guardar rutas generadas por el sistema.
- Evolucionar a S3 u object storage.

**Consecuencias:**

- Simple y económico en local/VPS.
- Requiere backup del volumen.
- No escala horizontalmente sin almacenamiento compartido.

**Alternativas consideradas:**

- S3 desde el inicio: más robusto, más configuración y costo.

---

## ADR-010: Umbral de retrieval experimental y configurable

**Estado:** Aceptada.

**Contexto:**

La similitud coseno depende del modelo de embeddings y del corpus. Un umbral fijo universal puede producir falsos “no sé” o respuestas con contexto irrelevante.

**Decisión:**

- `top_k`, `min_score`, chunk size, overlap y modelo son configurables.
- El umbral se calibra en la Etapa 5 con un dataset de preguntas respondibles y no respondibles.
- No se fija un valor numérico definitivo antes de medir.
- Se distinguen tres estados: sin candidatos, bajo umbral y contexto válido.

**Consecuencias:**

- Decisiones basadas en evidencia.
- Necesidad de revaluar si cambia el modelo o el corpus.
- Mayor trabajo inicial de evaluación.

**Alternativas consideradas:**

- Umbral fijo (por ejemplo, 0.7): simple, pero arbitrario y frágil.
- Sin umbral: riesgo de usar contexto irrelevante.

---

## ADR-011: Refresh tokens revocables persistidos

**Estado:** Aceptada.

**Contexto:**

El modelo inicial del documento no incluía una tabla para refresh tokens, pero se requiere revocación y rotación.

**Decisión:**

- Agregar la entidad `refresh_tokens`.
- Almacenar hash SHA-256, `jti`, expiración y revocación.
- Rotar en cada refresh.
- Soportar revocación global con `users.token_version`.
- Evaluar almacenamiento del refresh token en frontend: cookie `HttpOnly`, `Secure`, `SameSite` con protección CSRF, o solo en memoria (con pérdida de sesión al recargar). La elección se documentará al implementar.

**Consecuencias:**

- Sesiones revocables y auditables.
- Una tabla adicional y limpieza periódica.
- Mayor seguridad que un refresh token stateless sin revocación.

**Alternativas consideradas:**

- Refresh token stateless sin persistencia: no revocable.
- Solo `token_version`: revoca todo, no sesiones individuales.

---

## ADR-012: Contenido documental como dato no confiable

**Estado:** Aceptada.

**Contexto:**

Los documentos pueden contener instrucciones maliciosas diseñadas para manipular al modelo (prompt injection).

**Decisión:**

- Tratar todo contenido documental como dato, nunca como instrucción.
- Delimitar el contexto explícitamente.
- Instruir al modelo a no obedecer instrucciones internas, no revelar el prompt, no ejecutar acciones y citar fuentes.
- Validar la salida.
- Mantener un corpus de pruebas de inyección.

**Consecuencias:**

- Mayor robustez frente a documentos manipulados.
- Necesidad de pruebas específicas y revisión del prompt.
- No elimina el riesgo por completo; se monitorea.

**Alternativas consideradas:**

- Confiar en el modelo sin reglas explícitas: riesgo alto.
- Filtrado de contenido por palabras clave: insuficiente y fácil de evadir.

---

## ADR-013: Decisión de hosting diferida

**Estado:** Diferida.

**Contexto:**

El despliegue depende de costos, soporte de pgvector, persistencia y facilidad operativa. Tomar la decisión al inicio puede limitar el diseño sin necesidad.

**Decisión:**

- Mantener la aplicación portable vía Docker.
- Documentar la comparativa en [`deployment.md`](deployment.md).
- Elegir el proveedor en la Etapa 10 con criterios explícitos.
- No asumir servicios gratuitos con Docker o pgvector persistente.

**Consecuencias:**

- Flexibilidad hasta el final.
- Requiere verificar el proveedor antes de la etapa de despliegue.

---

## ADR-014: Python 3.12 + uv + Ruff

**Estado:** Aceptada.

**Contexto:**

Se necesita un entorno reproducible, rápido y con herramientas modernas de calidad.

**Decisión:**

- Python 3.12.
- `uv` para gestión de dependencias y entorno, con `pyproject.toml` y `uv.lock`.
- `requirements.txt` de respaldo para compatibilidad.
- Ruff para lint y formato.
- Pytest para tests.

**Consecuencias:**

- Instalaciones rápidas y reproducibles.
- Un solo tool para lint y format.
- Requiere que el entorno de despliegue soporte `uv` o use el lock exportado.

**Alternativas consideradas:**

- pip + venv + requirements.txt: simple y universal, más lento y menos reproducible.
- Poetry: maduro, más pesado.

## ADR-015: Login con organization_slug y claves foráneas compuestas

**Estado:** Aceptada.

**Contexto:**

El modelo `UNIQUE (organization_id, email)` permite emails duplicados entre organizaciones, pero el login solo recibía email y contraseña. También era necesario reforzar la integridad relacional entre organizaciones.

**Decisión:**

- Agregar `organizations.slug` único.
- Requerir `organization_slug` en `POST /api/v1/auth/login`.
- Agregar `UNIQUE (organization_id, id)` en tablas padre y FK compuestas **obligatorias** entre entidades relacionadas (`documents`, `document_chunks`, `conversations`, `processing_jobs`).
- Mantener `UNIQUE (organization_id, email)` para usuarios.

**Consecuencias:**

- Soporta múltiples organizaciones con el mismo email sin ambigüedad.
- PostgreSQL impide relaciones cruzadas entre organizaciones.
- Las FK compuestas se implementan en Etapa 3; no quedan como mejora futura.
- Cambio pequeño en el contrato de login.

**Alternativas consideradas:**

- Hacer el email único globalmente: más simple, pero menos flexible para organizaciones existentes.
- Resolver por email únicamente: ambiguo con el esquema propuesto.

---

## ADR-016: Esquema de tests con `create_all` y migraciones verificadas aparte

**Estado:** Aceptada.

**Contexto:**

La suite de integración necesita una base PostgreSQL real y un esquema limpio para cada ejecución. Aplicar todas las migraciones de Alembic antes de cada suite agrega tiempo y acopla el aislamiento de los tests al historial de migraciones. Aun así, las migraciones deben validarse por separado para detectar divergencias con los modelos.

**Decisión:**

- Crear y eliminar el esquema de la base `smartdocs_test` con `Base.metadata.create_all` / `drop_all` al inicio y al final de la sesión de tests.
- Aislar cada test con una transacción y rollback.
- Verificar las migraciones por separado contra una base vacía: `alembic upgrade head`, `alembic downgrade base` y `alembic upgrade head`.
- Mantener `docker/postgres/init-test-db.sql` para crear la base de tests en el contenedor.

**Consecuencias:**

- Suite más rápida y estable para el desarrollo diario.
- Los tests no detectan por sí solos divergencias entre modelos y migraciones; la verificación explícita de Alembic cubre ese riesgo.
- El esquema de tests puede diferir temporalmente del esquema migrado si se olvida ejecutar la verificación de migraciones.

**Alternativas consideradas:**

- Aplicar migraciones en cada sesión de tests: más fiel al esquema real, pero más lento y frágil ante fallos de migración.
- SQLite en memoria: descartado por falta de `vector`, `citext` y comportamiento real de PostgreSQL.
- `testcontainers`: útil en CI, pero agrega complejidad innecesaria para el entorno local actual.

---

## ADR-017: Job de ingesta con stub de extracción en Etapa 3

**Estado:** Aceptada.

**Contexto:**

La Etapa 3 entrega la gestión documental completa (modelos, almacenamiento, endpoints, cola, transiciones de estado y reconciliación), pero la extracción de texto real de PDF/DOCX/TXT corresponde a la Etapa 4. Se necesita un flujo verificable de extremo a extremo sin adelantar los extractores.

**Decisión:**

- El job de ingesta (`ProcessingService.run_job`) verifica el archivo (existencia, tamaño no vacío), transiciona `PENDING → PROCESSING → COMPLETED` y **no extrae texto ni genera chunks**.
- `documents.page_count` queda `NULL` hasta que exista extracción.
- El contrato de jobs, estados, cola y endpoints es definitivo; la Etapa 4 reemplaza el cuerpo del job por la extracción real sin cambiar modelos ni endpoints.

**Consecuencias:**

- La Etapa 3 se cierra con un ciclo verificable: carga → job → `COMPLETED`, incluida reconciliación, claim atómico, idempotencia y reproceso.
- Un documento `COMPLETED` durante la Etapa 3 no tiene texto indexado; el reproceso manual tras la Etapa 4 lo procesa con extracción real.
- Los tests de procesamiento validan estados y fallos, no contenido extraído.

**Alternativas consideradas:**

- Implementar extractores mínimos en la Etapa 3: mezcla alcances y duplica el trabajo planificado para la Etapa 4.
- Dejar los documentos en `PENDING` sin ejecutar jobs: no permite validar la cola, la reconciliación ni el reproceso.

---

## Plantilla para nuevas decisiones

```markdown
## ADR-XXX: Título

**Estado:** Aceptada | Rechazada | Reemplazada | Diferida

**Contexto:**

...

**Decisión:**

...

**Consecuencias:**

...

**Alternativas consideradas:**

...
```
