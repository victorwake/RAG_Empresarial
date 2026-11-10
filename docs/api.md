# API — SmartDocs AI

Contrato REST del backend. La fuente ejecutable será `/openapi.json` expuesto por FastAPI.

- **Base URL local:** `http://localhost:8000`
- **Prefijo versionado:** `/api/v1`
- **Formato:** JSON UTF-8, excepto carga de archivos (`multipart/form-data`) y descarga (`application/octet-stream`).
- **Autenticación:** `Authorization: Bearer <access_token>`.
- **Fechas:** ISO 8601 UTC (`2026-01-31T12:00:00Z`).
- **IDs:** UUID.
- **Documentación interactiva:** `/docs` (Swagger UI), `/redoc`, `/openapi.json`.
- **Colección Postman:** `postman/SmartDocs-AI.postman_collection.json` con entorno local (`SmartDocs-Local.postman_environment.json`) y muestras en `postman/samples/` para probar los flujos de auth, documentos y casos de error sin escribir requests a mano.

---

## 1. Convenciones

### 1.1. Versionado

- La versión vive en la ruta: `/api/v1`.
- Cambios incompatibles requieren `/api/v2`.
- Agregar campos opcionales no rompe compatibilidad; eliminarlos o cambiar su tipo sí.

### 1.2. Paginación

Parámetros comunes:

| Parámetro | Tipo | Default | Máximo |
|---|---|---|---|
| `limit` | integer | 20 | 100 |
| `offset` | integer | 0 | — |

Respuesta estándar:

```json
{
  "items": [],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

Reglas:

- `limit` fuera de rango devuelve `422`.
- El orden por defecto es `created_at DESC`.
- La paginación por cursor podrá incorporarse si el volumen lo requiere.

### 1.3. Filtros

- Los filtros se envían por query string.
- Los valores desconocidos devuelven `422`.
- Los filtros de organización **no** se aceptan: se derivan del token.

### 1.4. Cabeceras

| Cabecera | Uso |
|---|---|
| `Authorization` | `Bearer <token>` en endpoints protegidos |
| `X-Request-ID` | Opcional para trazabilidad; si no se envía, el servidor genera uno |
| `Content-Type` | `application/json` o `multipart/form-data` |
| `Accept` | `application/json` |

La respuesta incluye `X-Request-ID` para diagnóstico.

### 1.5. Códigos de estado

| Código | Uso |
|---|---|
| `200 OK` | Consulta exitosa |
| `201 Created` | Recurso creado |
| `202 Accepted` | Trabajo aceptado para procesamiento asíncrono |
| `204 No Content` | Eliminación o logout exitoso |
| `400 Bad Request` | Solicitud malformada |
| `401 Unauthorized` | Token ausente, inválido o expirado; credenciales de login inválidas |
| `403 Forbidden` | Autenticado sin permisos en su organización (no se usa para login) |
| `404 Not Found` | Recurso inexistente **o de otra organización** |
| `409 Conflict` | Duplicado o estado incompatible |
| `413 Payload Too Large` | Archivo excede el límite |
| `415 Unsupported Media Type` | Formato no soportado |
| `422 Unprocessable Entity` | Validación de datos |
| `429 Too Many Requests` | Límite de tasa (futuro) |
| `500 Internal Server Error` | Error no controlado |
| `502 Bad Gateway` | Fallo del proveedor de IA |
| `504 Gateway Timeout` | Timeout del proveedor de IA |

### 1.6. Formato de errores

Problem Details (RFC 9457 / RFC 7807):

```json
{
  "type": "https://smartdocs.ai/errors/not-found",
  "title": "Recurso no encontrado",
  "status": 404,
  "detail": "El documento solicitado no existe.",
  "instance": "/api/v1/documents/3f1c...",
  "request_id": "01J..."
}
```

Errores de validación:

```json
{
  "type": "https://smartdocs.ai/errors/validation",
  "title": "Error de validación",
  "status": 422,
  "detail": "Uno o más campos son inválidos.",
  "instance": "/api/v1/documents",
  "request_id": "01J...",
  "errors": [
    { "field": "file", "message": "La extensión .exe no está permitida." }
  ]
}
```

Reglas:

- Nunca exponer stack traces, SQL ni rutas internas.
- No revelar la existencia de recursos de otra organización (`404`).
- `detail` debe ser accionable para el usuario.

---

## 2. Autenticación

### 2.1. Modelo de tokens

- **Access token:** JWT de corta duración (15 minutos por defecto).
- **Refresh token:** JWT con `type=refresh`, `jti` y `ver`, revocable y rotativo (7 días por defecto). En la base de datos solo se persiste su hash SHA-256, nunca el token en claro.
- Claims del access token: `sub` (user ID), `org` (organization ID), `role`, `ver` (versión de sesión), `type=access`, `iat`, `exp`, `jti`.
- El cliente envía el access token en `Authorization`.
- El refresh token se envía solo a `/auth/refresh` y `/auth/logout`.
- La reutilización de un refresh token ya revocado invalida toda la sesión del usuario (`token_version += 1`).

### 2.2. `POST /api/v1/auth/login`

Autentica un usuario y emite tokens. Requiere el identificador de organización para soportar emails duplicados entre organizaciones.

**Request:**

```json
{
  "organization_slug": "acme",
  "email": "admin@acme.com",
  "password": "********"
}
```

| Campo | Obligatorio | Descripción |
|---|---|---|
| `organization_slug` | Sí | Slug único de la organización |
| `email` | Sí | Email del usuario dentro de la organización |
| `password` | Sí | Contraseña |

**Response `200`:**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Errores:** `401` genérico para credenciales inválidas, organización inexistente, usuario inexistente o usuario inactivo. No se distingue el motivo real para evitar enumeración de cuentas.

### 2.3. `POST /api/v1/auth/refresh`

Rota el refresh token y emite un nuevo par.

**Request:**

```json
{ "refresh_token": "eyJhbGciOiJIUzI1NiIs..." }
```

**Response `200`:** mismo formato que login.

**Errores:** `401` token inválido, vencido o revocado.

> Cada refresh revoca el token presentado. Reutilizar un token revocado invalida la sesión.

### 2.4. `POST /api/v1/auth/logout`

Endpoint público que recibe el refresh token; no requiere access token. Es idempotente: un token inválido, vencido o ya revocado también devuelve `204`.

**Request:**

```json
{ "refresh_token": "eyJhbGciOiJIUzI1NiIs..." }
```

**Response `204 No Content`.**

### 2.5. `GET /api/v1/auth/me`

Devuelve el perfil del usuario autenticado.

**Response `200`:**

```json
{
  "id": "uuid",
  "organization_id": "uuid",
  "name": "Ana Pérez",
  "email": "ana@acme.com",
  "role": "ADMIN",
  "is_active": true,
  "created_at": "2026-01-31T12:00:00Z"
}
```

---

## 3. Usuarios (solo `ADMIN`)

### 3.1. `GET /api/v1/users`

Lista usuarios de la organización del administrador.

**Query:** `limit`, `offset`, `role`, `is_active`, `search` (nombre o email).

**Response `200`:** paginado de `UserResponse`.

### 3.2. `POST /api/v1/users`

Crea un usuario en la organización del administrador.

**Request:**

```json
{
  "name": "Carlos Gómez",
  "email": "carlos@acme.com",
  "password": "********",
  "role": "USER"
}
```

**Response `201`:** `UserResponse` (sin `password_hash`).

**Errores:** `409` email duplicado en la organización; `422` contraseña débil.

### 3.3. `GET /api/v1/users/{id}`

**Response `200`:** `UserResponse`.

**Errores:** `404` si no pertenece a la organización.

### 3.4. `PATCH /api/v1/users/{id}`

Actualiza `name`, `role` o `is_active`. No permite cambiar email ni contraseña en el MVP.

**Response `200`:** `UserResponse`.

**Reglas:** un administrador no puede desactivarse a sí mismo ni quitarse el rol si es el único administrador activo.

---

## 4. Documentos

### 4.1. `POST /api/v1/documents`

Carga un documento y lo encola para procesamiento.

- **Roles:** `ADMIN`.
- **Content-Type:** `multipart/form-data`.
- **Campo:** `file` (obligatorio).
- **Tamaño máximo:** 25 MB (configurable).
- **Extensiones:** `.pdf`, `.docx`, `.txt`.

**Response `202 Accepted`:**

```json
{
  "id": "uuid",
  "organization_id": "uuid",
  "uploaded_by": "uuid",
  "filename": "politica_rrhh.pdf",
  "original_filename": "Política RRHH.pdf",
  "mime_type": "application/pdf",
  "file_size": 1048576,
  "status": "PENDING",
  "checksum": "sha256...",
  "page_count": null,
  "created_at": "2026-01-31T12:00:00Z",
  "updated_at": "2026-01-31T12:00:00Z"
}
```

**Errores:**

| Código | Causa |
|---|---|
| `409` | Documento duplicado (mismo checksum en la organización); incluye `existing_document_id` |
| `413` | Archivo mayor al límite |
| `415` | Extensión o MIME no permitido |
| `422` | Archivo vacío o corrupto |
| `403` | Usuario sin rol `ADMIN` |

### 4.2. `GET /api/v1/documents`

Lista documentos de la organización.

**Query:** `limit`, `offset`, `status`, `search` (filename), `uploaded_by`.

**Response `200`:** paginado de `DocumentResponse`.

> Un `USER` solo ve metadatos de documentos autorizados. En el MVP, todos los documentos de la organización son consultables; la autorización granular por documento queda como mejora futura.

### 4.3. `GET /api/v1/documents/{id}`

**Response `200`:** `DocumentResponse`.

**Errores:** `404` si no existe o pertenece a otra organización.

### 4.4. `DELETE /api/v1/documents/{id}`

Elimina el documento, su archivo, sus chunks y sus jobs.

- **Roles:** `ADMIN`.
- **Response:** `204 No Content`.
- **Errores:** `404` si no existe o pertenece a otra organización.

> No bloquea por un job activo: los jobs se eliminan en cascada con el documento y un job en vuelo detecta la eliminación y termina sin efecto.

### 4.5. `POST /api/v1/documents/{id}/reprocess`

Elimina chunks previos y reencola el documento.

- **Roles:** `ADMIN`.
- **Response `202 Accepted`:** `DocumentResponse` con `status = PENDING`.
- **Errores:** `404`; `409` si ya hay un job activo.

### 4.6. `GET /api/v1/documents/{id}/chunks`

Consulta los fragmentos generados (uso administrativo y diagnóstico).

- **Roles:** `ADMIN`.
- **Query:** `limit`, `offset`.
- **Response `200`:**

```json
{
  "items": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "chunk_index": 3,
      "content": "Texto del fragmento...",
      "page_number": 8,
      "section": "Solicitud de vacaciones",
      "embedding_model": "gemini-embedding-...",
      "metadata": {},
      "created_at": "2026-01-31T12:00:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

> El vector no se expone en la API.

### 4.7. `GET /api/v1/documents/{id}/file`

Descarga el archivo original si el usuario tiene acceso.

- **Roles:** `ADMIN` y `USER`.
- **Response `200`:** `application/octet-stream` con `Content-Disposition`.
- **Errores:** `404` si no existe o pertenece a otra organización.

---

## 5. Conversaciones y chat

### 5.1. `POST /api/v1/conversations`

Crea una conversación para el usuario autenticado.

**Request:**

```json
{ "title": "Consulta sobre vacaciones" }
```

`title` es opcional; si se omite, se usa `"Nueva conversación"`.

**Response `201`:**

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "organization_id": "uuid",
  "title": "Consulta sobre vacaciones",
  "created_at": "2026-01-31T12:00:00Z",
  "updated_at": "2026-01-31T12:00:00Z"
}
```

### 5.2. `GET /api/v1/conversations`

Lista las conversaciones del usuario autenticado.

**Query:** `limit`, `offset`.

**Response `200`:** paginado de `ConversationResponse`.

### 5.3. `GET /api/v1/conversations/{id}`

Devuelve la conversación con sus mensajes y fuentes.

**Query:** `include_messages` (default `true`), `limit`, `offset` para mensajes.

**Response `200`:**

```json
{
  "id": "uuid",
  "title": "Consulta sobre vacaciones",
  "created_at": "2026-01-31T12:00:00Z",
  "updated_at": "2026-01-31T12:05:00Z",
  "messages": {
    "items": [
      {
        "id": "uuid",
        "role": "USER",
        "content": "¿Cuántos días de vacaciones corresponden con 5 años de antigüedad?",
        "status": null,
        "created_at": "2026-01-31T12:01:00Z"
      },
      {
        "id": "uuid",
        "role": "ASSISTANT",
        "content": "Según la Política de Recursos Humanos...",
        "status": "ANSWERED",
        "model": "gemini-...",
        "latency_ms": 2450,
        "created_at": "2026-01-31T12:01:03Z",
        "sources": [
          {
            "chunk_id": "uuid",
            "document_id": "uuid",
            "filename": "Politica_RRHH.pdf",
            "page_number": 8,
            "section": "Vacaciones",
            "relevance_score": 0.82,
            "rank": 1
          }
        ]
      }
    ],
    "total": 2,
    "limit": 20,
    "offset": 0
  }
}
```

**Errores:** `404` si la conversación no existe o es de otro usuario. El administrador accede a conversaciones de su organización mediante `GET /api/v1/admin/conversations/{id}` (solo lectura).

### 5.4. `PATCH /api/v1/conversations/{id}`

Actualiza el título.

**Request:** `{ "title": "Nuevo título" }`

**Response `200`:** `ConversationResponse`.

### 5.5. `DELETE /api/v1/conversations/{id}`

**Response `204 No Content`.**

### 5.6. `POST /api/v1/conversations/{id}/messages`

Envía una pregunta y obtiene la respuesta del asistente.

**Request:**

```json
{
  "content": "¿Cuál es el procedimiento para solicitar vacaciones?",
  "document_ids": ["uuid"],
  "top_k": 6,
  "min_score": 0.35,
  "response_style": "DETAILED"
}
```

| Campo | Obligatorio | Descripción |
|---|---|---|
| `content` | Sí | Pregunta, 1–4000 caracteres |
| `document_ids` | No | Restringe la búsqueda a documentos específicos de la organización |
| `top_k` | No | Sobrescribe el valor configurado (límite máximo acotado) |
| `min_score` | No | Solo para configuraciones de evaluación. En el MVP el umbral se toma de la configuración del servidor. |
| `response_style` | No | `CONCISE` o `DETAILED`; por defecto `DETAILED` |

**Response `200`:**

```json
{
  "user_message_id": "uuid",
  "message_id": "uuid",
  "status": "ANSWERED",
  "answer": "Según el documento \"Política de Recursos Humanos\", el procedimiento consiste en...",
  "sources": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "filename": "Politica_RRHH.pdf",
      "page_number": 8,
      "section": "Solicitud de vacaciones",
      "relevance_score": 0.82,
      "rank": 1
    }
  ],
  "model": "gemini-...",
  "latency_ms": 2450,
  "usage": {
    "prompt_tokens": 1800,
    "completion_tokens": 220
  }
}
```

**Respuesta sin información (`NO_INFO`):**

```json
{
  "user_message_id": "uuid",
  "message_id": "uuid",
  "status": "NO_INFO",
  "answer": "No encontré información suficiente en la documentación disponible para responder esta consulta.",
  "sources": [],
  "model": null,
  "latency_ms": 120,
  "usage": null
}
```

**Errores:**

| Código | Causa |
|---|---|
| `404` | Conversación inexistente o de otro usuario |
| `422` | Pregunta vacía o demasiado larga |
| `502` | Error del proveedor de IA |
| `504` | Timeout del proveedor de IA |

Reglas:

- Si no hay candidatos válidos, **no se llama al LLM** y se responde `NO_INFO`.
- Las fuentes expuestas solo pueden ser chunks recuperados para esa consulta.
- El `min_score` enviado por el cliente se acepta solo para roles `ADMIN` y se registra en logs; en producción el valor de referencia es el configurado.

---

## 6. Administración

Todos los endpoints requieren rol `ADMIN` y operan sobre la organización del token.

### 6.1. `GET /api/v1/admin/stats`

```json
{
  "documents": {
    "total": 42,
    "pending": 1,
    "processing": 2,
    "completed": 37,
    "failed": 2
  },
  "conversations": {
    "total": 120,
    "last_7_days": 18
  },
  "messages": {
    "total": 540,
    "answered": 510,
    "no_info": 24,
    "error": 6
  },
  "avg_latency_ms": 2310
}
```

### 6.2. `GET /api/v1/admin/activity`

Actividad reciente de la organización.

**Query:** `limit`, `offset`, `type` (`document_uploaded`, `document_processed`, `document_failed`, `conversation_created`, `question_asked`).

**Response `200`:** paginado de eventos con `created_at`, `actor`, `type`, `resource_id`.

> En el MVP la actividad se compone a partir de documentos, jobs y mensajes existentes. Los accesos denegados se registran en logs; una tabla de auditoría persistente queda como mejora futura.

### 6.3. `GET /api/v1/admin/conversations`

Historial de conversaciones de la organización para auditoría.

**Query:** `limit`, `offset`, `user_id`, `from`, `to`.

**Response `200`:** paginado de `ConversationResponse` con `user` resumido.

### 6.4. `GET /api/v1/admin/conversations/{id}`

Detalle de una conversación de la organización para auditoría, incluyendo mensajes y fuentes.

**Query:** `limit`, `offset` para mensajes.

**Response `200`:** mismo formato que `GET /api/v1/conversations/{id}`, con `user` resumido.

**Errores:** `404` si no pertenece a la organización.

> Este endpoint no permite al administrador escribir en la conversación; es de solo lectura.

### 6.5. `GET /api/v1/admin/unanswered`

Consultas sin resultado (`NO_INFO`) para identificar vacíos documentales.

**Query:** `limit`, `offset`, `from`, `to`.

**Response `200`:** paginado con pregunta, usuario, fecha y cantidad de candidatos recuperados.

---

## 7. Health

### 7.1. `GET /health`

Público, sin autenticación.

**Response `200`:**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "ok",
  "timestamp": "2026-01-31T12:00:00Z"
}
```

**Response `503`:** base de datos no disponible.

### 7.2. `GET /api/v1/health`

Alias versionado para clientes.

---

## 8. Resumen de endpoints

| Método | Ruta | Rol | Etapa |
|---|---|---|---|
| POST | `/api/v1/auth/login` | Público | 2 |
| POST | `/api/v1/auth/refresh` | Público (refresh token) | 2 |
| POST | `/api/v1/auth/logout` | Público (refresh token) | 2 |
| GET | `/api/v1/auth/me` | Autenticado | 2 |
| GET | `/api/v1/users` | ADMIN | 8 |
| POST | `/api/v1/users` | ADMIN | 8 |
| GET | `/api/v1/users/{id}` | ADMIN | 8 |
| PATCH | `/api/v1/users/{id}` | ADMIN | 8 |
| POST | `/api/v1/documents` | ADMIN | 3 |
| GET | `/api/v1/documents` | Autenticado | 3 |
| GET | `/api/v1/documents/{id}` | Autenticado | 3 |
| DELETE | `/api/v1/documents/{id}` | ADMIN | 3 |
| POST | `/api/v1/documents/{id}/reprocess` | ADMIN | 3 |
| GET | `/api/v1/documents/{id}/chunks` | ADMIN | 5 |
| GET | `/api/v1/documents/{id}/file` | Autenticado | 3 |
| POST | `/api/v1/conversations` | Autenticado | 6 |
| GET | `/api/v1/conversations` | Autenticado | 6 |
| GET | `/api/v1/conversations/{id}` | Autenticado | 6 |
| PATCH | `/api/v1/conversations/{id}` | Autenticado | 6 |
| DELETE | `/api/v1/conversations/{id}` | Autenticado | 6 |
| POST | `/api/v1/conversations/{id}/messages` | Autenticado | 6 |
| GET | `/api/v1/admin/stats` | ADMIN | 7 |
| GET | `/api/v1/admin/activity` | ADMIN | 7 |
| GET | `/api/v1/admin/conversations` | ADMIN | 7 |
| GET | `/api/v1/admin/conversations/{id}` | ADMIN | 7 |
| GET | `/api/v1/admin/unanswered` | ADMIN | 7 |
| GET | `/health` | Público | 2 |
| GET | `/api/v1/health` | Público | 2 |

---

## 9. Schemas principales

### 9.1. `DocumentResponse`

```text
id: uuid
organization_id: uuid
uploaded_by: uuid
filename: string
original_filename: string
mime_type: string
file_size: integer
status: PENDING | PROCESSING | COMPLETED | FAILED
checksum: string
page_count: integer | null
created_at: datetime
updated_at: datetime
```

### 9.2. `ConversationResponse`

```text
id: uuid
user_id: uuid
organization_id: uuid
title: string
created_at: datetime
updated_at: datetime
```

### 9.3. `ChatResponse`

```text
user_message_id: uuid
message_id: uuid
status: ANSWERED | NO_INFO | ERROR
answer: string
sources: SourceResponse[]
model: string | null
latency_ms: integer
usage: { prompt_tokens: integer, completion_tokens: integer } | null
```

### 9.4. `SourceResponse`

```text
chunk_id: uuid
document_id: uuid
filename: string
page_number: integer | null
section: string | null
relevance_score: float
rank: integer
```

---

## 10. Reglas transversales

1. Todo endpoint protegido exige access token válido y usuario activo.
2. Toda consulta se filtra por la organización del token.
3. `organization_id` nunca se acepta como parámetro de entrada.
4. Recursos de otra organización se responden como `404`.
5. Los errores no exponen detalles internos.
6. Las operaciones de escritura registran `request_id` y actor.
7. Los endpoints de carga devuelven `202` y el cliente consulta el estado.
8. Los límites de `top_k` y `min_score` enviados por el cliente se validan contra rangos permitidos.
