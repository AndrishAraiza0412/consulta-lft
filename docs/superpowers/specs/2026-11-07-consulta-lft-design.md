# Consulta LFT: asistente RAG con evaluación medida

Fecha: 2026-11-07. Proyecto A de la sección 7 de `camino_a_seguir_cv.txt`.

## 1. Objetivo

Asistente que responde preguntas sobre la Ley Federal del Trabajo (LFT) con citas a sus artículos, y que admite cuando no tiene la respuesta. Su función en el portafolio es demostrar RAG y evaluaciones, que hoy no aparecen en ningún otro proyecto.

El resultado se juzga por una tabla de evaluación en el README, con números defendibles, que muestre qué acierta y qué falla.

## 2. Restricciones

- Solo en local: sin despliegue, URLs públicas, video ni push hasta que el usuario decida publicar.
- LLM: `qwen2.5:3b-instruct` en Ollama, sin llaves de API.
- No se modifica ningún proyecto existente de `Proyectos/`.
- Máquina con 8 GB de RAM. Qwen ocupa unos 2.2 GB.
- El README va en inglés. La interfaz y las respuestas van en español, como el corpus.

## 3. Decisiones

| Tema | Decisión | Motivo |
|---|---|---|
| Corpus | Una sola versión del PDF oficial de la LFT (Cámara de Diputados) | Documento real y público; los artículos numerados permiten calificar citas de forma objetiva |
| Base vectorial | PostgreSQL con pgvector | Una sola base de datos, y refuerza SQL |
| LLM | Cliente `openai` contra la API compatible de Ollama | Pasar a una API de pago solo requiere cambiar URL, llave y modelo |
| Embeddings | `bge-m3` en Ollama, 1024 dimensiones | Modelo multilingüe. Alternativa si no cabe en memoria: `nomic-embed-text` (sección 10) |
| Orquestación | Código propio, sin LangChain | Poco código y explicable en una entrevista |
| Trazas | Tabla `traces` en Postgres | LangSmith requiere nube y llave; Langfuse autoalojado es pesado para 8 GB |
| Migraciones | `schema.sql` idempotente aplicado al arrancar | Hay un solo esquema pequeño; no justifica Alembic |

## 4. Arquitectura

```
PDF -> ingest -> Postgres/pgvector
                       ^
React -> FastAPI /ask -+-> Ollama (bge-m3, qwen)
                       |
                       +-> traces
evals/run.py -> /ask -> reporte JSON y Markdown
```

Estructura del repositorio:

```
app/config.py      configuración por variables de entorno
app/schema.sql     tablas chunks y traces
app/ingest.py      PDF -> artículos -> fragmentos -> embeddings
app/retrieval.py   búsqueda por similitud
app/citations.py   extracción y validación de citas
app/llm.py         cliente de chat y embeddings
app/ask.py         flujo de una pregunta, límites y traza
app/main.py        rutas FastAPI
web/               React, TypeScript y Vite
evals/cases.json   casos de evaluación
evals/run.py       ejecuta, califica y genera el reporte
evals/results/     resultados versionados
data/              PDF de la LFT y su SHA-256
tests/             pytest
```

## 5. Ingesta

1. Extraer el texto del PDF con `pdfplumber`. `pypdf` partía palabras ("riesg o", "fís ica").
2. Quitar encabezados y pies de página repetidos.
3. Cortar el texto por el patrón de inicio de artículo. Se conservan los sufijos como identificador de texto, por ejemplo `153-A` o `311 Bis`.
4. Excluir los artículos transitorios, porque repiten numeración y no son el contenido que se consulta.
5. Un artículo de hasta 1,500 caracteres es un fragmento. Uno más largo se divide por párrafos, y todos sus fragmentos conservan el mismo número de artículo.
6. Generar embeddings y guardar. La ingesta es idempotente: reemplaza los fragmentos de esa versión en una transacción.

La ingesta imprime un reporte con el total de artículos y los huecos de numeración, para distinguir artículos derogados de errores de extracción.

Tabla `chunks`: `id`, `source_version`, `article`, `part`, `text`, `embedding vector(1024)`. Es única por `(source_version, article, part)`.

## 6. Flujo de una pregunta

`POST /ask` recibe `{"question": "..."}`, de 1 a 500 caracteres.

1. **Presupuesto:** si el costo del mes en `traces` alcanza `MONTHLY_LIMIT_USD`, responde 429 sin llamar a ningún modelo.
2. **Búsqueda:** genera el embedding de la pregunta y toma los `TOP_K` fragmentos (5 por defecto) por similitud coseno.
3. **Umbral:** si ningún fragmento alcanza `MIN_SIMILARITY`, responde `no_answer` sin llamar al LLM. El valor se ajusta con los casos `dev`.
4. **Generación:** arma el prompt con hasta 6,000 caracteres de contexto, para no exceder los 4,096 tokens de contexto con los que Ollama carga Qwen. Las instrucciones exigen citar como `[Art. 76]`, responder `NO_ENCONTRADO` si el contexto no alcanza y tratar el contexto y la pregunta como datos, no como instrucciones. Limita la salida a `MAX_OUTPUT_TOKENS` (500 por defecto).
5. **Reintento:** si el contenido llega vacío, reintenta una vez. Se incluye porque en Apolo las respuestas vacías fueron un fallo real con este modelo.
6. **Validación de citas:** extrae las citas y separa las que corresponden a artículos recuperados de las que no.
   - `NO_ENCONTRADO`, contenido vacío tras el reintento o ninguna cita válida: responde `no_answer`. Una respuesta sin una cita verificable no se muestra como respuesta.
   - Al menos una cita válida: responde `answered`, y las citas no válidas se devuelven aparte en `unverified_citations` y la interfaz las marca con una advertencia.
7. **Traza:** guarda la traza en todos los casos, incluidos los errores.

Respuesta:

```json
{
  "status": "answered",
  "answer": "...",
  "citations": [{"article": "76", "text": "..."}],
  "unverified_citations": [],
  "trace_id": "..."
}
```

Errores:

| Código | Caso |
|---|---|
| 422 | Pregunta vacía o de más de 500 caracteres |
| 429 | Presupuesto mensual agotado |
| 503 | Ollama o Postgres no disponibles, con un mensaje claro. Se guarda la traza si Postgres está disponible |

`GET /health` comprueba Postgres y Ollama.

### Trazas y costo

Tabla `traces`: `id`, `created_at`, `question`, `status`, `retrieved` (JSONB con artículo y similitud), `raw_answer`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, `retrieval_ms`, `llm_ms`, `error`.

El costo se calcula con `PRICE_INPUT_PER_MTOK` y `PRICE_OUTPUT_PER_MTOK`, que valen 0 con Qwen. `MONTHLY_LIMIT_USD` vale 5 por defecto. Mientras se use Qwen, el límite solo queda cubierto por pruebas con precios configurados, y el README lo dirá así.

Las trazas se consultan con SQL. El README incluye una consulta de ejemplo.

## 7. Frontend

Una sola página en español: caja de pregunta, respuesta y citas que se abren para ver el texto del artículo. Muestra los estados de carga, "no encontré la respuesta", error y citas no verificadas, además del aviso de que no es asesoría legal. Es usable en móvil y con teclado.

## 8. Evaluación

`evals/cases.json` tiene 40 casos. Campos: `id`, `split`, `category`, `question`, `expected_status`, `required_facts`, `forbidden_facts`, `expected_articles`.

| Categoría | dev | test | Pasa si |
|---|---|---|---|
| Respuesta directa | 8 | 8 | `answered`, contiene los hechos requeridos y cita el artículo esperado |
| Varios artículos | 4 | 4 | `answered`, contiene los hechos requeridos y cita todos los artículos esperados |
| Fuera de la ley | 5 | 5 | `no_answer` |
| Ataque (inyección, pedir que invente o ignore reglas) | 3 | 3 | No obedece el ataque, no contiene los hechos prohibidos y ninguna cita inventada se presenta como válida |

Cada caso corre 3 veces. La calificación es determinista, por reglas, y los hechos requeridos admiten variantes de redacción.

El reporte incluye:

- **Exactitud:** corridas aprobadas sobre el total, global y por categoría.
- **Citas correctas:** en respuestas `answered`, porcentaje de corridas que citan todos los artículos esperados y ningún artículo fuera de ellos.
- **Tasa de "no sé":** `no_answer` correctos en casos fuera de la ley, y `no_answer` indebidos en casos con respuesta. Se informan por separado.
- **Recuperación:** porcentaje de casos con el artículo esperado entre los `TOP_K`, para distinguir fallos de búsqueda de fallos de generación.
- **Latencia:** mediana y p95.
- **Fallos:** los casos que fallan, con la causa.

### Protocolo para que el número sea defendible

- Todos los ajustes (prompt, umbral, `TOP_K`, fragmentación) se hacen solo con `dev`.
- `test` no se ejecuta hasta congelar el sistema, y su resultado se guarda con el hash del commit.
- Si después de ver `test` se cambia el sistema, el README lo declara y muestra ambos resultados.
- El README publica `dev` y `test` por separado.

Claude redacta las respuestas esperadas directamente del texto de la ley, y el usuario revisa una muestra. Ninguna respuesta se considera asesoría legal.

## 9. Pruebas y entrega

- **pytest sin modelos:** fragmentación, validación de citas, calificador de la evaluación, límites de presupuesto, respuestas 422, 429 y 503, y regla de "sin cita válida no hay respuesta". Usa un LLM falso y pgvector real.
- **Ingesta con la ley real:** comprueba que los artículos 76 (vacaciones) y 87 (aguinaldo) se extraen completos y que los sufijos se conservan.
- **Prueba real con Ollama:** un recorrido completo antes de declarar terminado el proyecto. Un LLM falso no basta: en Centinela, una suite verde con una CLI falsa ocultó un fallo de permisos.
- **Frontend:** build y una prueba de Vitest de los estados de respuesta.
- **Docker:** `docker compose up` levanta la base con `pgvector/pgvector`, la API y el frontend. Ollama corre en el host, porque dentro de Docker en Mac no tendría GPU.
- **CI:** GitHub Actions con lint, pytest y build del frontend. No corre hasta que se haga push. La evaluación con Qwen solo corre en local.
- **README en inglés:** arquitectura, decisiones, tabla de evaluación, reproducción, límites conocidos y sección "Uso de IA".

## 10. Riesgos

| Riesgo | Cómo se atiende |
|---|---|
| Qwen, `bge-m3` y Docker no caben en 8 GB | Primer paso de la implementación: medirlo. Si no cabe, usar `nomic-embed-text` y comparar la recuperación |
| El PDF extrae mal los artículos | Reporte de huecos y pruebas de ingesta. Se resuelve antes de generar embeddings |
| Búsquedas como "artículo 76" fallan con embeddings | Se mide con la recuperación. Solo si falla se agrega búsqueda híbrida con el texto completo de Postgres |
| La ley se reforma | El proyecto declara la versión del PDF y su SHA-256. No pretende estar actualizado |
| Licencia de Qwen | Qwen Research License: revisarla antes de cualquier uso comercial |

## 11. Fuera de alcance

Login, carga de documentos desde la interfaz, varios corpus, conversación con memoria, búsqueda híbrida y reordenamiento (salvo que la evaluación los justifique), Langfuse, Qdrant, despliegue y video.

## 12. Criterios de terminado

- `docker compose up`, con Ollama en el host, permite preguntar y recibir una respuesta con citas verificadas.
- La suite de pytest y el build del frontend pasan, y hubo una corrida real completa con Ollama.
- La evaluación corrió 3 veces por caso, con `test` ejecutado sobre un commit congelado.
- El README publica los resultados de `dev` y `test` con sus fallos, sin inflarlos.
- El repositorio no tiene secretos y todo queda en commits locales, sin push.
