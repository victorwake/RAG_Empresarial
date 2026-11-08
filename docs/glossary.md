# Glosario y preguntas de entrevista — SmartDocs AI

Conceptos clave del proyecto y respuestas preparadas para explicar las decisiones técnicas.

---

## 1. Conceptos fundamentales

### RAG (Retrieval-Augmented Generation)

Arquitectura que combina **recuperación de información** con **generación de texto**. Antes de responder, el sistema busca fragmentos relevantes en una base documental y se los entrega al modelo como contexto. La respuesta se genera a partir de ese contexto, no solo del conocimiento general del modelo.

### LLM (Large Language Model)

Modelo de lenguaje entrenado para generar texto. En este proyecto se usa para redactar respuestas a partir del contexto recuperado. No es una base de datos ni una fuente de verdad.

### Embedding

Representación numérica (vector) del significado de un texto. Textos con significado similar producen vectores cercanos. Permiten buscar por similitud semántica en lugar de por coincidencia exacta de palabras.

### Vector

Lista de números que representa un texto en un espacio de alta dimensión. En el proyecto se almacena en pgvector y se compara mediante similitud coseno.

### Chunk

Fragmento de un documento más grande. Los documentos se dividen en chunks para que la recuperación sea precisa y para no superar el límite de contexto del modelo.

### Chunking

Proceso de dividir un documento en fragmentos. En el proyecto se hace por tokens, con overlap configurable. Valores iniciales: 500 tokens con 75 de overlap, **a validar en la Etapa 5**.

### Overlap

Cantidad de texto que se repite entre chunks consecutivos. Ayuda a no perder información que queda en el límite entre dos fragmentos.

### Token

Unidad mínima de texto que procesa un modelo. Puede ser una palabra, parte de una palabra o un signo. Los límites de contexto y los costos se miden en tokens.

### Similitud coseno

Medida de similitud entre dos vectores basada en el ángulo que forman. Valores cercanos a 1 indican alta similitud. Es la métrica usada por el índice pgvector del proyecto.

### Búsqueda semántica

Recuperación basada en significado (vectores), no en palabras exactas. Permite encontrar “vacaciones” cuando la pregunta dice “días libres”.

### Top-K

Cantidad de fragmentos que se recuperan como candidatos. Es configurable y se calibra con el dataset de evaluación.

### Umbral (`min_score`)

Score mínimo de similitud para considerar un fragmento relevante. **No se fija de antemano**: depende del modelo y del corpus, y se calibra en la Etapa 5.

### Grounding / Faithfulness

Grado en que una respuesta está respaldada por el contexto recuperado. Un sistema con alto grounding no inventa información.

### Alucinación

Afirmación generada por el modelo que no está respaldada por el contexto ni por los datos. El proyecto la previene con contexto acotado, reglas de prompt, validación de fuentes y política de `NO_INFO`.

### Prompt

Instrucciones y contexto que se envían al modelo. En el proyecto se compone de instrucciones del sistema, fragmentos documentales delimitados, la pregunta y las reglas de respuesta.

### Prompt injection

Ataque en el que un texto (por ejemplo, un documento) contiene instrucciones diseñadas para que el modelo ignore las reglas del sistema. En el proyecto el contenido documental se trata como **dato no confiable**.

### Re-ranking

Etapa opcional que reordena los fragmentos recuperados con un modelo más preciso. Está fuera del MVP.

### Búsqueda híbrida

Combinación de búsqueda semántica (vectores) y búsqueda textual tradicional (por ejemplo, PostgreSQL full-text). Está fuera del MVP.

### OCR

Reconocimiento óptico de caracteres. Permite extraer texto de PDFs escaneados o imágenes. Está fuera del MVP, pero la arquitectura permite incorporarlo.

### pgvector

Extensión de PostgreSQL que agrega el tipo `vector` y operadores de distancia, además de índices ANN. Permite almacenar embeddings junto a los datos relacionales.

### HNSW / IVFFlat

Tipos de índice aproximado de vecinos más cercanos (ANN) en pgvector. HNSW suele ofrecer mejor latencia y recall a costa de memoria; IVFFlat requiere ajuste de `lists`.

### Multi-tenancy

Capacidad de atender a varias organizaciones en la misma aplicación manteniendo sus datos aislados. En el proyecto se usa esquema compartido con `organization_id` derivado del token.

### RBAC

Control de acceso basado en roles. En el proyecto: `ADMIN` y `USER`.

### JWT

Token firmado que contiene claims (usuario, organización, rol, expiración). Se usa como access token de corta duración.

### Refresh token

Token de mayor duración que permite obtener nuevos access tokens. En el proyecto es revocable, rotativo y se almacena hasheado.

### Argon2id

Algoritmo de hash de contraseñas resistente a fuerza bruta y ataques con GPU. Es el elegido para almacenar contraseñas.

### Idempotencia

Propiedad por la cual ejecutar una operación varias veces produce el mismo resultado. El reproceso de documentos es idempotente: no duplica chunks.

### Cola durable

Sistema que persiste los trabajos y garantiza su ejecución aunque el proceso se reinicie. `BackgroundTasks` **no** es una cola durable.

### RAGAS

Herramienta de evaluación de sistemas RAG que calcula métricas como Faithfulness, Answer Relevancy y Context Precision.

### Precision@K

Proporción de fragmentos recuperados (entre los primeros K) que son relevantes.

### Recall@K

Proporción de fragmentos relevantes que fueron recuperados entre los primeros K.

### MRR (Mean Reciprocal Rank)

Promedio del inverso de la posición del primer resultado relevante. Un valor cercano a 1 indica que el primer resultado suele ser relevante.

---

## 2. Preguntas de entrevista

### ¿Qué diferencia hay entre RAG y un chatbot tradicional?

Un chatbot tradicional responde con el conocimiento general del modelo o con un prompt fijo. RAG primero **busca** información en una base documental y luego genera la respuesta usando ese contexto. Eso permite respuestas actualizadas, específicas de la empresa y con fuentes verificables, y reduce las alucinaciones.

### ¿Qué son los embeddings?

Son representaciones vectoriales del significado de un texto. Permiten medir similitud semántica: dos textos que significan lo mismo quedan cerca en el espacio vectorial, aunque usen palabras distintas. En el proyecto se generan con Gemini y se almacenan en pgvector.

### ¿Por qué dividís los documentos en chunks?

Por dos razones: los documentos completos pueden superar el límite de contexto del modelo, y recuperar fragmentos pequeños y específicos mejora la precisión. Un chunk grande mete ruido; uno demasiado pequeño pierde contexto. Por eso el tamaño y el overlap se calibran con documentos reales.

### ¿Cómo evitás que la IA invente información?

Con varias capas:

1. El prompt instruye a responder solo con el contexto.
2. Si la recuperación no supera el umbral, no se llama al LLM y se responde `NO_INFO`.
3. Se valida que las fuentes citadas existan entre los fragmentos recuperados.
4. Se evalúa Faithfulness y tasa de alucinación con un dataset dorado.
5. El contenido de los documentos se trata como dato, no como instrucción.

### ¿Qué sucede si la búsqueda recupera fragmentos incorrectos?

El sistema puede responder mal o responder `NO_INFO`. Para mitigarlo:

- Se calibran `top_k` y `min_score` con preguntas respondibles y no respondibles.
- Se mide Precision@K, Recall@K y MRR.
- Se ajusta el chunking y el modelo de embeddings.
- A futuro se puede incorporar re-ranking o búsqueda híbrida.

### ¿Cómo medís la calidad de las respuestas?

Con dos grupos de métricas:

- **Recuperación:** Precision@K, Recall@K, MRR y Hit Rate.
- **Generación:** Faithfulness, Answer Relevancy, Correctness, Citation Accuracy, tasa de `NO_INFO` y tasa de alucinación.

Se usa un dataset dorado con preguntas respondibles y no respondibles, y herramientas como RAGAS combinadas con métricas propias.

### ¿Cómo evitás que un usuario consulte documentos de otra empresa?

La organización se deriva del token autenticado, nunca del cliente. Todos los repositorios y la búsqueda vectorial filtran por `organization_id`. Los recursos ajenos responden `404`. Además hay tests obligatorios de aislamiento cruzado y FK compuestas obligatorias desde Etapa 3; RLS queda como defensa en profundidad futura.

### ¿Por qué usás pgvector y no una base vectorial dedicada?

Porque el proyecto ya necesita PostgreSQL para usuarios, documentos y conversaciones. pgvector permite tener datos relacionales y vectores en la misma base, con transacciones y filtros por organización en una sola consulta. Para el volumen del MVP es suficiente y reduce la infraestructura. Si la escala lo exigiera, se podría migrar a una base vectorial dedicada.

### ¿Por qué no usás LangChain?

Porque el objetivo es entender y poder explicar cada componente del pipeline. LangChain abstrae la carga, el splitting, el retrieval y las cadenas, lo que puede ocultar el comportamiento real. Implementarlo directamente permite controlar chunking, prompts, retrieval y evaluación. Más adelante se puede evaluar LangChain o LlamaIndex si aporta valor.

### ¿Qué pasa si cambiás el modelo de embeddings?

Los vectores dejan de ser comparables si cambia el modelo o la dimensión. Se requiere una migración: nueva columna o tabla, reindexación completa, validación de calidad con el dataset y luego eliminar los vectores anteriores. Por eso se registra `embedding_model` y la dimensión.

### ¿Cómo manejás un PDF escaneado?

En el MVP se detecta que no tiene texto extraíble y el job falla con un mensaje claro. La arquitectura permite incorporar OCR en una etapa futura sin cambiar el pipeline.

### ¿Qué es el prompt injection y cómo lo mitigás?

Es un ataque en el que un documento contiene instrucciones para manipular al modelo. Se mitiga tratando el contenido como dato no confiable, delimitándolo, instruyendo al modelo a no obedecer instrucciones internas, no ejecutar acciones, no revelar el prompt y citar fuentes. Además se valida la salida y se ejecutan pruebas específicas.

### ¿Por qué usás `BackgroundTasks` si no es una cola durable?

Porque para el MVP simplifica la infraestructura. Está detrás de la interfaz `ProcessingQueue`, se documenta su limitación y se compensa con reconciliación de estados huérfanos, idempotencia y reproceso manual. Cuando el volumen o la confiabilidad lo exijan, se migra a Celery/Redis sin cambiar los endpoints.

### ¿Cómo escalarías el sistema?

Primero mediría. Luego:

- Migrar la cola a una durable y separar workers.
- Escalar la API horizontalmente.
- Mover archivos a S3.
- Optimizar índices vectoriales.
- Agregar caché de respuestas frecuentes.
- Si la base vectorial se vuelve el cuello de botella, evaluar una dedicada.

### ¿Cómo manejás el costo de la IA?

Mido tokens de prompt y completion por consulta y por organización. No llamo al LLM si no hay contexto válido. Limito el contexto y el `top_k`. Puedo agregar caché para preguntas frecuentes y elegir modelos según costo/calidad. Los costos se reportan en la evaluación de la Etapa 9.

### ¿Qué pasa si el proveedor de IA falla?

Las consultas devuelven `502` o `504` con un mensaje genérico y el detalle queda en logs. No se pierden datos. Hay timeouts y reintentos acotados. La carga y el procesamiento de documentos no dependen de que el LLM esté disponible para el chat.

### ¿Cómo garantizás que el sistema no responda con información de otra organización a través del LLM?

El contexto que se envía al LLM solo contiene chunks filtrados por `organization_id`. No se envían documentos completos ni metadatos de otras organizaciones. Además, la validación de fuentes verifica que los chunks citados pertenezcan a la recuperación de esa consulta.

### ¿Qué decisiones dejarías para después y por qué?

- **Hosting:** depende de costos y soporte de pgvector; se decide en la Etapa 10.
- **Umbral de retrieval:** depende del modelo y del corpus; se calibra en la Etapa 5.
- **Re-ranking, búsqueda híbrida y OCR:** agregan valor pero no son necesarios para validar el MVP.
- **Agentes autónomos:** no resuelven el problema central y aumentan el riesgo.

### ¿Qué demostraría que el proyecto está bien hecho?

1. Documentos procesados correctamente.
2. Respuestas con fuentes verificables.
3. Reconocimiento explícito de falta de información.
4. Aislamiento entre organizaciones probado.
5. Tiempos y costos medidos.
6. Tests automatizados y evaluación RAG.
7. Proveedores desacoplados.
8. Instalación documentada y reproducible.
