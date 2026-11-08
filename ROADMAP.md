# Roadmap — SmartDocs AI

Plan de desarrollo incremental en 10 etapas. Cada etapa debe producir un resultado funcional y verificable antes de avanzar a la siguiente.

- **Duración estimada total:** 15 semanas.
- **Ritmo asumido:** 5–7 horas semanales, desarrollo individual.
- **Prioridad:** funcionalidades completas y verificables por encima del calendario.
- **Regla:** si una tarea depende de experimentación (chunking, umbral de retrieval, modelo de embeddings), se marca como **“a validar en Etapa 5”** y no se fija un valor definitivo antes de medir.

---

## Índice

- [Principios de ejecución](#principios-de-ejecución)
- [Definición de terminado](#definición-de-terminado)
- [Hitos](#hitos)
- [Dependencias entre etapas](#dependencias-entre-etapas)
- [Etapa 1 — Análisis y planificación](#etapa-1--análisis-y-planificación)
- [Etapa 2 — Entorno y estructura del backend](#etapa-2--entorno-y-estructura-del-backend)
- [Etapa 3 — Gestión documental](#etapa-3--gestión-documental)
- [Etapa 4 — Extracción y procesamiento](#etapa-4--extracción-y-procesamiento)
- [Etapa 5 — Embeddings y búsqueda vectorial](#etapa-5--embeddings-y-búsqueda-vectorial)
- [Etapa 6 — Motor RAG](#etapa-6--motor-rag)
- [Etapa 7 — Frontend](#etapa-7--frontend)
- [Etapa 8 — Seguridad y permisos empresariales](#etapa-8--seguridad-y-permisos-empresariales)
- [Etapa 9 — Testing y evaluación de calidad](#etapa-9--testing-y-evaluación-de-calidad)
- [Etapa 10 — Despliegue y documentación](#etapa-10--despliegue-y-documentación)
- [Riesgos y mitigaciones](#riesgos-y-mitigaciones)

---

## Principios de ejecución

1. **Incremental:** una funcionalidad terminada y probada vale más que tres a medias.
2. **Backend primero:** el RAG se valida desde Swagger antes de construir el frontend.
3. **Sin LangChain inicialmente:** el pipeline se implementa con Python para entender cada pieza.
4. **Proveedores desacoplados:** LLM, embeddings, almacenamiento y cola detrás de interfaces.
5. **Seguridad desde el MVP:** `organization_id` se deriva de la identidad autenticada, nunca del cliente.
6. **Sin invención:** si la recuperación no es suficiente, se responde que no hay información.
7. **Documentación viva:** cada etapa actualiza los documentos afectados y registra decisiones nuevas.
8. **Sin dependencias innecesarias:** cada librería debe justificar su presencia.

### Flujo de trabajo por etapa

1. Análisis del requerimiento y actualización de la documentación.
2. Diseño de la solución (endpoints, entidades, interfaces).
3. Implementación.
4. Pruebas automatizadas y manuales.
5. Corrección de errores.
6. Actualización de documentación y `CHANGELOG` si aplica.
7. Commit siguiendo Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).

### Convenciones

- Ramas: `main` estable; `feat/etapa-N-descripcion` por etapa o funcionalidad.
- API versionada en `/api/v1`.
- IDs UUID; timestamps UTC en ISO 8601.
- Errores con formato Problem Details (ver [`docs/api.md`](docs/api.md)).
- Código, docstrings y documentación en español; nombres de código en inglés.

---

## Definición de terminado

Una etapa se considera terminada cuando:

- [ ] El entregable funciona en el entorno local de forma reproducible.
- [ ] Existen pruebas automatizadas para la lógica nueva y pasan.
- [ ] Ruff no reporta errores.
- [ ] La API está reflejada en Swagger cuando corresponde.
- [ ] La documentación afectada está actualizada.
- [ ] Se registraron las decisiones nuevas en [`docs/decisions.md`](docs/decisions.md).
- [ ] El criterio de finalización específico de la etapa se cumple.
- [ ] No quedan secretos ni credenciales en el repositorio.

---

## Hitos

| Hito | Etapa | Resultado |
|---|---|---|
| Documentación y plan aprobados | 1 | Repositorio con docs completas y entorno definido |
| Backend operativo | 2 | FastAPI + PostgreSQL/pgvector + Docker + health check |
| Gestión documental | 3 | Carga, listado, borrado y reproceso por API |
| Ingesta de texto | 4 | PDF, DOCX y TXT extraídos y normalizados |
| Búsqueda semántica | 5 | Recuperación de fragmentos relevantes sin LLM |
| RAG completo | 6 | Respuestas con fuentes y política de “no sé” |
| Producto usable | 7 | Login, dashboard, documentos y chat desde web |
| Aislamiento empresarial | 8 | Usuarios y documentos separados por organización |
| Calidad medida | 9 | Tests, dataset dorado y métricas RAG |
| Producto desplegable | 10 | Demo accesible, README y documentación de instalación |

---

## Dependencias entre etapas

```mermaid
flowchart LR
    E1[1. Planificación] --> E2[2. Backend base]
    E2 --> E3[3. Gestión documental]
    E3 --> E4[4. Extracción]
    E4 --> E5[5. Embeddings y búsqueda]
    E5 --> E6[6. Motor RAG]
    E6 --> E7[7. Frontend]
    E2 --> E8[8. Seguridad]
    E3 --> E8
    E6 --> E9[9. Testing y evaluación]
    E7 --> E10[10. Despliegue]
    E9 --> E10
    E8 --> E10
```

Notas:

- La Etapa 8 puede iniciarse en paralelo con la 5–6, pero debe completarse antes del despliegue.
- La Etapa 9 consume el pipeline de la Etapa 6; conviene reservar tiempo para corregir hallazgos.
- La Etapa 10 no se inicia sin tests mínimos de aislamiento entre organizaciones.

---

## Etapa 1 — Análisis y planificación

**Objetivo:** definir alcance, decisiones técnicas y estructura del proyecto.

**Duración:** 1 semana.

### Tareas

- [x] Definir requisitos funcionales y no funcionales.
- [x] Establecer formatos soportados (PDF, DOCX, TXT) y límites de tamaño.
- [x] Diseñar la arquitectura general y el modelo de datos.
- [x] Diseñar los endpoints iniciales y las convenciones REST.
- [x] Documentar el pipeline RAG, la seguridad y la estrategia de testing.
- [x] Definir estructura de carpetas y stack.
- [x] Crear el roadmap por etapas.
- [x] Crear `.gitignore` y `.env.example`, e inicializar el repositorio Git (`git init`).
- [x] Definir el destino de despliegue o dejar la comparativa documentada (decisión diferida a Etapa 10, ver ADR-013).

### Entregables

- Documento de requisitos.
- Diagrama de arquitectura.
- Modelo inicial de datos.
- Contrato inicial de API.
- Pipeline RAG documentado.
- Plan de desarrollo.

### Criterio de finalización

Contar con planificación técnica clara, documentación coherente y entorno de desarrollo definido.

### Riesgos

- **Sobre-documentar:** mantener la documentación accionable; los detalles experimentales quedan como “a validar”.
- **Alcance creciente:** cualquier funcionalidad futura se registra fuera del MVP.

---

## Etapa 2 — Backend, infraestructura y autenticación básica

**Objetivo:** preparar una base sólida para desarrollar la aplicación, con autenticación y contexto de organización desde el inicio.

**Duración:** 1 semana.

### Tareas

- [ ] Crear proyecto Python 3.12 con `uv` (`pyproject.toml`, `uv.lock`) y `requirements.txt` de respaldo.
- [ ] Configurar Ruff (lint + format) y reglas de estilo.
- [ ] Configurar FastAPI con `app/main.py` y estructura modular.
- [ ] Configurar `pydantic-settings` y `.env.example`.
- [ ] Levantar PostgreSQL 16 con pgvector vía Docker Compose.
- [ ] Configurar SQLAlchemy 2.0 async y sesión por request.
- [ ] Inicializar Alembic y crear la migración base.
- [ ] Crear modelos de `Organization`, `User`, `RefreshToken` y enums asociados.
- [ ] Implementar autenticación básica: `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` y derivación de `organization_slug`/tenant.
- [ ] Emitir access token JWT de corta duración y refresh token rotativo y revocable.
- [ ] Implementar `TenantContext` y dependencias de autenticación/tenant.
- [ ] Implementar aprovisionamiento inicial (comando CLI) para crear organización y administrador.
- [ ] Configurar Argon2id para hashes de contraseñas y política mínima de longitud.
- [ ] Implementar endpoint de health check con verificación de base de datos.
- [ ] Configurar logging estructurado y request ID.
- [ ] Configurar manejo global de excepciones.
- [ ] Configurar Swagger/OpenAPI (`/docs`, `/redoc`, `/openapi.json`).
- [ ] Crear `Dockerfile` multi-stage del backend.
- [ ] Crear `docker-compose.yml` con API y base de datos.
- [ ] Configurar pytest y un test de health check.
- [ ] `git init` y primer commit.

### Estructura inicial

```text
backend/
  app/
    api/
      routes/
      dependencies.py
    core/
      config.py
      logging.py
      security.py
      exceptions.py
    database/
      session.py
      base.py
    models/
    schemas/
    services/
    repositories/
    rag/
    document_processing/
    main.py
  migrations/
  tests/
  pyproject.toml
  requirements.txt
  Dockerfile
  .env.example
```

### Entregables

- Backend ejecutándose.
- Base de datos conectada.
- Migración inicial.
- Docker Compose funcional.
- Login, refresh, logout y perfil autenticado operativos.
- API documentada en Swagger.

### Criterio de finalización

`docker compose up` levanta API y base de datos; `GET /health` responde correctamente verificando PostgreSQL; login, refresh, logout y `GET /auth/me` funcionan con Argon2id y tenant.

### A validar en esta etapa

- Versión exacta de la imagen `pgvector/pgvector`.
- Estrategia de ejecución de migraciones al arrancar (script de entrada o comando de release).

---

## Etapa 3 — Gestión documental

**Objetivo:** permitir cargar y administrar documentos, con endpoints protegidos por autenticación y permisos.

**Duración:** 1 semana.

### Tareas

- [ ] Crear entidades `Document` y `ProcessingJob` con sus migraciones.
- [ ] Aplicar claves foráneas compuestas obligatorias (`documents`-`users`, `document_chunks`-`documents`, `conversations`-`users`, `processing_jobs`-`documents`) con `UNIQUE (organization_id, id)` en tablas padre, según `docs/database.md §5.3`.
- [ ] Implementar `FileStorage` (interfaz) y `LocalFileStorage`.
- [ ] Implementar carga multipart con validación de extensión, MIME y tamaño, protegida con RBAC (`ADMIN`).
- [ ] Calcular checksum SHA-256 y detectar duplicados por organización (RF-013 como `Must`).
- [ ] Sanitizar nombres de archivo y evitar path traversal.
- [ ] Registrar metadatos y estado inicial `PENDING`.
- [ ] Implementar `ProcessingQueue` (interfaz) y `FastAPIProcessingQueue` como implementación **temporal no durable**.
- [ ] Implementar listado paginado, consulta individual y eliminación.
- [ ] Implementar reproceso (limpia chunks previos y reencola).
- [ ] Implementar transiciones de estado `PENDING → PROCESSING → COMPLETED | FAILED`.
- [ ] Reconciliar jobs huérfanos en `PENDING` y `PROCESSING` al arranque (marcar `FAILED` con motivo de interrupción y permitir reproceso).
- [ ] Garantizar que cada tarea cree su propia sesión de SQLAlchemy (sin reutilizar la sesión de la request).
- [ ] Transición atómica `PENDING -> PROCESSING` con control de intentos (`attempts++`).
- [ ] Asociar `uploaded_by` y `organization_id` derivados del usuario autenticado (nunca del cliente).
- [ ] Tests de carga, validación, duplicados, borrado y estados.

### Endpoints

```text
POST   /api/v1/documents
GET    /api/v1/documents
GET    /api/v1/documents/{id}
DELETE /api/v1/documents/{id}
POST   /api/v1/documents/{id}/reprocess
```

### Limitación conocida: BackgroundTasks

`FastAPIProcessingQueue` usa `BackgroundTasks`, que **no es una cola durable**:

- Si el proceso se reinicia, los trabajos pendientes o en curso pueden perderse.
- No hay reintentos automáticos ni garantía de orden.
- Es aceptable para el MVP, siempre que se documente y se compense con:
  - Reconciliación de estados huérfanos al arranque.
  - Job idempotente por `document_id` (reprocesar no duplica chunks).
  - Endpoint de reproceso manual.
- La interfaz `ProcessingQueue` permite migrar a Celery + Redis u otra cola sin modificar endpoints ni servicios.

**Criterio de migración:** volumen de documentos, necesidad de reintentos confiables o despliegues que interrumpan procesos.

### Entregables

- Carga documental funcional.
- Listado y administración.
- Validaciones y estados.
- Almacenamiento local abstraído.

### Criterio de finalización

Cargar PDF, DOCX y TXT por API, listarlos, consultarlos, eliminarlos y reprocesarlos, con estados correctos.

---

## Etapa 4 — Extracción y procesamiento

**Objetivo:** transformar documentos en texto utilizable por el pipeline RAG.

**Duración:** 1 semana.

### Tareas

- [ ] Definir interfaz `TextExtractor` con resultado normalizado y metadatos.
- [ ] Implementar `PDFProcessor` con PyMuPDF.
- [ ] Implementar `DOCXProcessor` con python-docx.
- [ ] Implementar `TXTProcessor` con detección de codificación.
- [ ] Normalizar espacios, saltos de línea y caracteres de control.
- [ ] Preservar página/sección cuando sea posible.
- [ ] Detectar documentos sin texto extraíble (posible escaneo) y registrar motivo.
- [ ] Implementar manejo de errores por archivo y por página.
- [ ] Registrar resultados y errores en `ProcessingJob`.
- [ ] Marcar `FAILED` con mensaje accionable.
- [ ] Tests con archivos de ejemplo válidos, corruptos y vacíos.

### Entregables

- Extractores funcionales.
- Texto normalizado.
- Metadatos documentales.
- Manejo de archivos inválidos.

### Criterio de finalización

Cargar un archivo de cada formato y obtener su contenido textual correctamente extraído, con metadatos y errores controlados.

### Fuera de alcance

- OCR de PDFs escaneados. La interfaz debe permitir incorporarlo en una etapa futura.

---

## Etapa 5 — Embeddings y búsqueda vectorial

**Objetivo:** convertir el contenido documental en información consultable por similitud semántica.

**Duración:** 2 semanas.

Esta es una de las etapas más importantes. Las decisiones de calidad se toman con evidencia, no por intuición.

### 5.1. Chunking

- [ ] Implementar división por tokens con overlap.
- [ ] Parámetros iniciales **configurables**: tamaño 500 tokens, overlap 75 tokens.
- [ ] Conservar `document_id`, `chunk_index`, `page_number` y metadatos.
- [ ] Evitar chunks vacíos o duplicados exactos.
- [ ] Documentar el tokenizador usado y su relación con el modelo de embeddings.

### 5.2. Embeddings

- [ ] Definir interfaz `EmbeddingProvider`.
- [ ] Implementar proveedor Gemini por defecto.
- [ ] Generar embeddings en lotes con reintentos y backoff exponencial.
- [ ] Validar dimensión contra la configuración.
- [ ] Registrar `embedding_model` y dimensión junto a cada chunk.
- [ ] Evitar regenerar embeddings si el contenido y el modelo no cambiaron.

### 5.3. Almacenamiento vectorial

- [ ] Crear entidad `DocumentChunk` con columna `vector(N)`.
- [ ] Crear índice ANN (HNSW o IVFFlat) y evaluar parámetros.
- [ ] Documentar que cambiar modelo o dimensión requiere migración y reindexación.

### 5.4. Búsqueda semántica

- [ ] Generar embedding de la consulta.
- [ ] Buscar por similitud coseno con `top_k` configurable.
- [ ] Aplicar filtros obligatorios por `organization_id` y, opcionalmente, por documento(s).
- [ ] Implementar `min_score` configurable.
- [ ] Distinguir tres casos: sin candidatos, candidatos bajo umbral, candidatos válidos.
- [ ] Registrar scores y parámetros usados para diagnóstico.

### Calibración del umbral (obligatoria antes de cerrar la etapa)

El umbral **no se fija de antemano**: la similitud coseno depende del modelo y del corpus.

1. Construir un conjunto pequeño de 15–30 preguntas con respuestas conocidas y preguntas que *no* estén en los documentos.
2. Medir la distribución de scores para preguntas respondibles y no respondibles.
3. Probar varios valores de `min_score` y `top_k`.
4. Evaluar Precision@K, Recall@K y tasa de falsos “no sé”.
5. Elegir el valor inicial según el punto de operación deseado y dejarlo configurable.
6. Documentar resultados y fecha de calibración.

### Entregables

- Generación de embeddings.
- Persistencia en pgvector.
- Búsqueda semántica funcional.
- Informe breve de calibración.

### Criterio de finalización

Realizar una consulta y recuperar fragmentos pertinentes sin usar todavía un LLM, con métricas y umbral justificados.

---

## Etapa 6 — Motor RAG

**Objetivo:** conectar la recuperación documental con un modelo de lenguaje para generar respuestas contextualizadas y verificables.

**Duración:** 2 semanas.

### Tareas

- [ ] Definir interfaz `LLMProvider`.
- [ ] Implementar `GeminiLLMProvider` con timeouts y reintentos controlados.
- [ ] Construir el contexto con pregunta, fragmentos, metadatos e instrucciones.
- [ ] Diseñar y versionar el prompt del sistema.
- [ ] Implementar la política de “no sé” sin llamar al LLM cuando no hay candidatos válidos.
- [ ] Generar respuesta estructurada con fuentes y estado.
- [ ] Soportar estilo de respuesta conciso o detallado.
- [ ] Validar que las fuentes citadas correspondan a chunks recuperados.
- [ ] Persistir conversación, mensajes y `MessageSource`.
- [ ] Registrar tokens, latencia, modelo y parámetros usados.
- [ ] Implementar límites operativos anti prompt injection (ver abajo).
- [ ] Tests unitarios del armado de prompt y de la validación de salida.
- [ ] Tests de integración con proveedor simulado (sin llamadas reales en CI).

### Contrato de respuesta

```json
{
  "message_id": "uuid",
  "status": "ANSWERED",
  "answer": "Según la Política de Recursos Humanos...",
  "sources": [
    {
      "document_id": "uuid",
      "filename": "Politica_RRHH.pdf",
      "chunk_id": "uuid",
      "page_number": 8,
      "section": "Solicitud de vacaciones",
      "relevance_score": 0.82
    }
  ],
  "model": "gemini-...",
  "latency_ms": 2450
}
```

`status` posibles: `ANSWERED`, `NO_INFO`, `ERROR`.

### Límites operativos del prompt

El contenido documental se trata como **dato no confiable**. El prompt debe indicar que el modelo:

1. No debe obedecer instrucciones encontradas dentro de los documentos.
2. Debe responder únicamente con el contexto recuperado.
3. Debe citar los fragmentos o documentos utilizados.
4. No debe ejecutar acciones ni acceder a herramientas desde el flujo de consulta.
5. Debe reconocer cuando la documentación no contiene la respuesta.
6. No debe asumir datos que no aparezcan en las fuentes.
7. Debe diferenciar información explícita de posibles interpretaciones.

La defensa se valida con casos de prueba específicos en la Etapa 8/9.

### Entregables

- Integración con LLM.
- Pipeline RAG funcional.
- Prompt documentado y versionado.
- Respuestas con fuentes.
- Manejo de consultas sin información.

### Criterio de finalización

Realizar preguntas sobre documentos cargados y obtener respuestas contextualizadas con referencias verificables, incluyendo el caso “no hay información suficiente”.

---

## Etapa 7 — Frontend

**Objetivo:** construir una interfaz que permita utilizar y administrar el sistema.

**Duración:** 2 semanas.

### Stack

- React + TypeScript + Vite.
- React Router.
- TanStack Query para estado remoto.
- Cliente API tipado generado o mantenido a partir de los schemas.
- Vitest + Testing Library.

### Tareas

- [ ] Scaffolding del proyecto y configuración de TypeScript estricto.
- [ ] Configurar lint/format y variables de entorno del frontend.
- [ ] Implementar cliente API con manejo de tokens.
- [ ] Integrar en React el login, logout y refresh automático ya implementados en Etapa 2.
- [ ] Proteger rutas por autenticación y rol.
- [ ] Dashboard con métricas: documentos totales, procesados, pendientes, fallidos, consultas y actividad reciente.
- [ ] Gestión documental: subida con progreso, listado, estados, metadatos, borrado y reproceso.
- [ ] Chat: envío de consultas, historial, indicador de procesamiento, respuestas, fuentes y acceso al fragmento.
- [ ] Manejar estados vacíos, errores y consultas sin información.
- [ ] Diseño responsive y accesible (foco, contraste, navegación por teclado).
- [ ] Tests de componentes y flujos críticos.

### Entregables

- Aplicación React.
- Login.
- Dashboard.
- Gestión documental.
- Chat conversacional.

### Criterio de finalización

Usar las funcionalidades principales desde la interfaz web sin interactuar con Swagger.

### Nota

No se empieza el frontend antes de validar el backend y el RAG desde Swagger.

---

## Etapa 8 — Seguridad y permisos empresariales

**Objetivo:** garantizar que cada usuario consulte únicamente la documentación autorizada.

**Duración:** 1 semana.

### Tareas

- [ ] Endurecer la autenticación existente: política de contraseñas, rehash, invalidación global con `token_version`, revocación administrativa de sesiones y rate limiting.
- [ ] Auditar y endurecer JWT y refresh tokens: expiración, rotación, revocación y detección de reutilización.
- [ ] Implementar roles `ADMIN` y `USER` y dependencias de autorización.
- [ ] Implementar gestión de usuarios por `ADMIN`: crear, listar, activar/desactivar y cambiar rol dentro de su organización.
- [ ] Verificar el aprovisionamiento inicial creado en Etapa 2; no se implementa registro público ni se duplica el comando.
- [ ] Derivar `organization_id` **siempre** del usuario autenticado; rechazar cualquier valor enviado por el cliente.
- [ ] Aplicar scoping por organización en todos los repositorios y en la búsqueda vectorial.
- [ ] Responder `404` ante recursos de otra organización (evitar enumeración); `403` solo para permisos dentro de la misma organización.
- [ ] Validar archivos y limitar tamaño, extensión y MIME.
- [ ] Proteger credenciales y claves API; revisar que no haya secretos en logs.
- [ ] Configurar CORS restrictivo.
- [ ] Implementar redacción de datos sensibles en logs.
- [ ] Tests de aislamiento cruzado: lectura, escritura, borrado, búsqueda vectorial y conversaciones.
- [ ] Tests de prompt injection con corpus de casos maliciosos.
- [ ] Revisar dependencias y permisos de archivos.

### Regla de multi-tenancy

> La organización nunca se toma del body, query string ni header del cliente. Se obtiene del token autenticado y se valida en cada operación, incluyendo los filtros de la consulta vectorial.

RLS en PostgreSQL queda como mejora futura, no como sustituto del scoping en el MVP.

### Entregables

- Autenticación endurecida (sin reimplementar login).
- Roles y permisos.
- Separación por organización.
- Validaciones de seguridad y pruebas de aislamiento.

### Criterio de finalización

Demostrar con tests que un usuario no puede acceder a información de otra organización ni a documentos para los que no tiene autorización, incluyendo la recuperación vectorial.

---

## Etapa 9 — Testing y evaluación de calidad

**Objetivo:** comprobar que el sistema funciona y que las respuestas de IA son confiables.

**Duración:** 2 semanas.

### Backend

- [ ] Tests de endpoints, autenticación, permisos y aislamiento.
- [ ] Tests de carga documental, extracción, persistencia y errores.
- [ ] Tests de idempotencia del reproceso.
- [ ] Cobertura mínima acordada en servicios y repositorios.

### Pipeline RAG

- [ ] Construir dataset dorado con documentos de prueba y preguntas verificables.
- [ ] Incluir preguntas sin respuesta en los documentos.
- [ ] Evaluar recuperación, generación, fuentes y reconocimiento de información inexistente.
- [ ] Medir Precision@K, Recall@K y MRR.
- [ ] Medir Faithfulness, Answer Relevancy y Correctness (RAGAS y/o métricas propias).
- [ ] Medir tasa de respuestas inventadas y tasa de falsos “no sé”.
- [ ] Ejecutar casos de prompt injection y verificar que no cambian el comportamiento.

### Rendimiento

- [ ] Tiempo de procesamiento documental.
- [ ] Tiempo de recuperación vectorial.
- [ ] Tiempo de respuesta del LLM.
- [ ] Tiempo total de consulta.
- [ ] Consumo de tokens y costo aproximado por consulta.

### Entregables

- Suite de tests.
- Dataset de evaluación versionado.
- Informe de resultados.
- Lista de problemas y correcciones.

### Criterio de finalización

Contar con resultados medibles que permitan evaluar calidad, confiabilidad, rendimiento y costo del sistema.

---

## Etapa 10 — Despliegue y documentación

**Objetivo:** preparar el sistema para ejecutarse fuera del entorno local.

**Duración:** 1 semana.

### Tareas

- [ ] Preparar Docker Compose de producción (API, PostgreSQL/pgvector, proxy).
- [ ] Configurar variables de entorno y secretos fuera del repositorio.
- [ ] Configurar migraciones en el arranque o en un paso de release.
- [ ] Configurar almacenamiento persistente y backups.
- [ ] Desplegar backend y frontend.
- [ ] Configurar HTTPS, cabeceras de seguridad y CORS de producción.
- [ ] Configurar logging, monitoreo básico y health checks.
- [ ] Implementar manejo de errores y páginas de estado.
- [ ] Documentar instalación, configuración, API y operación.
- [ ] Preparar datos de demostración.
- [ ] Verificar aislamiento entre organizaciones en el entorno desplegado.

### Decisión de hosting

Diferida a esta etapa. La comparativa y los criterios están en [`docs/deployment.md`](docs/deployment.md). No se asume que un servicio gratuito permita Docker o una base vectorial persistente.

### Entregables

- Aplicación desplegada.
- Repositorio actualizado.
- README profesional.
- Documentación técnica y de operación.
- Demo funcional.

### Criterio de finalización

Otra persona puede acceder a la aplicación y probar sus funcionalidades principales sin asistencia. La organización y el administrador inicial se crean con el comando de CLI.

---

## Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Recuperación de baja calidad | Respuestas incorrectas o “no sé” frecuentes | Dataset dorado, calibración de umbral, evaluación por etapa |
| Alucinaciones del LLM | Pérdida de confianza | Contexto acotado, política de “no sé”, validación de fuentes, tests |
| Prompt injection en documentos | Manipulación del modelo | Documentos como datos no confiables, límites operativos, corpus de pruebas |
| Fuga entre organizaciones | Incidente grave de seguridad | `organization_id` desde JWT, scoping en repositorios y búsqueda, tests cruzados |
| Pérdida de jobs con BackgroundTasks | Documentos sin procesar | Reconciliación al arranque, idempotencia, reproceso manual, migración a cola durable |
| Cambio de modelo de embeddings | Reindexación costosa | Registrar modelo/dimensión, documentar migración, parametrizar |
| Costos de IA | Presupuesto excedido | Medición de tokens, límites de contexto, caché cuando aplique |
| Sobre-ingeniería | Retraso del MVP | Interfaces mínimas, sin agentes ni integraciones en la primera versión |
| Falta de tiempo | Etapas inconclusas | Priorizar hitos; cada etapa deja algo demostrable |
