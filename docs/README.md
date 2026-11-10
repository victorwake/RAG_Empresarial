# Documentación — SmartDocs AI

Índice de la documentación técnica y funcional del proyecto.

> **Estado:** Etapas 1–4 cerradas — próxima Etapa 5. Punto de reanudación: [`status.md`](status.md). Los documentos son **vivos**: se actualizan al cerrar cada etapa.
>
> Las decisiones que dependen de experimentación están marcadas como **“a validar en Etapa 5”** y no deben tratarse como valores definitivos.

---

## Mapa de documentos

| Documento | Qué responde | Audiencia |
|---|---|---|
| [`status.md`](status.md) | Dónde está el proyecto, cómo verificarlo y desde dónde retomar | Todo el equipo |
| [`requirements.md`](requirements.md) | Qué debe hacer el sistema, para quién, con qué límites y qué queda fuera | Producto, desarrollo, evaluación |
| [`architecture.md`](architecture.md) | Cómo se organiza el sistema, componentes, capas, flujos e interfaces | Desarrollo, revisión técnica |
| [`database.md`](database.md) | Entidades, relaciones, índices, multi-tenancy y migraciones | Backend, datos |
| [`api.md`](api.md) | Contrato REST, autenticación, errores, paginación y endpoints | Backend, frontend |
| [`rag-pipeline.md`](rag-pipeline.md) | Ingesta, chunking, embeddings, retrieval, prompt y guardrails | IA, backend |
| [`security.md`](security.md) | Autenticación, autorización, aislamiento, archivos y prompt injection | Backend, seguridad |
| [`testing.md`](testing.md) | Estrategia de pruebas, dataset dorado, métricas RAG y rendimiento | Calidad, desarrollo |
| [`deployment.md`](deployment.md) | Docker, configuración, HTTPS, operación y comparativa de hosting | DevOps, despliegue |
| [`decisions.md`](decisions.md) | Registro de decisiones de arquitectura (ADR) | Todo el equipo |
| [`glossary.md`](glossary.md) | Conceptos clave y respuestas a preguntas de entrevista | Estudio, portafolio |

Plan de etapas: [`../ROADMAP.md`](../ROADMAP.md).
Visión general: [`../README.md`](../README.md).

---

## Rutas de lectura

### Si vas a desarrollar el backend

1. `requirements.md` — alcance y límites.
2. `architecture.md` — capas e interfaces.
3. `database.md` — modelo de datos.
4. `api.md` — contrato de endpoints.
5. `security.md` — reglas que no se negocian.
6. `testing.md` — cómo se valida.

### Si vas a desarrollar el frontend

1. `api.md` — contrato y errores.
2. `security.md` — manejo de tokens y permisos.
3. `requirements.md` — casos de uso y criterios de aceptación.
4. `glossary.md` — vocabulario para la interfaz.

### Si vas a revisar o defender el proyecto

1. `../README.md` — resumen ejecutivo.
2. `architecture.md` — decisiones estructurales.
3. `rag-pipeline.md` — cómo se recupera y genera.
4. `testing.md` — cómo se mide la calidad.
5. `decisions.md` y `glossary.md` — justificación y conceptos.

---

## Convenciones de la documentación

- **Idioma:** español. Nombres de código, tablas, columnas y endpoints en inglés.
- **Requisitos:** se usa la nomenclatura `RF-###` (funcional) y `RNF-###` (no funcional).
- **Prioridad:** MoSCoW (`Must`, `Should`, `Could`, `Won't`).
- **Etapas:** referencian el número de etapa del [`ROADMAP`](../ROADMAP.md).
- **Estados de documento:** `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.
- **Estados de respuesta RAG:** `ANSWERED`, `NO_INFO`, `ERROR`.
- **Roles:** `ADMIN`, `USER`.
- **IDs:** UUID. **Fechas:** UTC en ISO 8601.
- **Marcador experimental:** “a validar en Etapa 5” para chunking, `top_k`, `min_score` y modelo de embeddings.
- **Decisiones:** toda decisión estructural nueva se registra en `decisions.md` con estado `Aceptada`, `Reemplazada` o `Diferida`.

---

## Reglas de coherencia

Para evitar contradicciones entre documentos:

1. Los nombres de entidades y campos son los definidos en `database.md`.
2. Los endpoints y códigos de error son los definidos en `api.md`.
3. Las reglas de acceso son las definidas en `security.md`.
4. Los estados y transiciones son los definidos en `database.md` y `api.md`.
5. Las métricas de calidad son las definidas en `testing.md`.
6. Si un documento necesita una excepción, se actualiza primero la fuente de verdad y luego el resto.

---

## Mantenimiento

Al cerrar cada etapa:

- [ ] Actualizar los documentos afectados.
- [ ] Actualizar `status.md` con estado, verificación y próximo paso.
- [ ] Registrar decisiones nuevas o cambios de decisión en `decisions.md`.
- [ ] Actualizar checkboxes del `ROADMAP`.
- [ ] Anotar resultados de calibración o evaluación con fecha.
- [ ] Verificar que los enlaces relativos sigan siendo válidos.
