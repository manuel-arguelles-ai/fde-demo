# fde-demo — Build del track "Forward Deployed Engineer" (DataCamp)

Bot de soporte N1 que ejercita el stack completo del track (15-nov-2026).

## Qué demuestra

| Curso del track | Dónde se aplica acá |
|---|---|
| 1/2. OpenAI API + prompts | `ChatGroq` (interfaz OpenAI-compatible); system prompt con reglas de citación |
| 3. Seguridad y ética | Gate anti-alucinación: sin doc relevante no hay respuesta |
| 4. SW principles | Type hints, módulos separados, docstrings |
| 5. Responses API | (equivalencia: estado del grafo reemplaza statefulness del provider) |
| 6. LLMOps | `/health` + logs de intentos + decisiones trazables |
| 7. Fundamentos app LLM | app end-to-end: retrieval → validación → generación → API |
| 9. RAG | BM25 two-stage sobre `docs/kb.md`, chunks por sección |
| 8. LLM Application Evaluation | `eval.py` + `eval_set.json`: dataset de 9 casos, métricas correctness (9/9 = 100%) y groundedness con cita esperada (6/6) |
| 10. Tool use | function calling real: `create_ticket` (tool de LangChain) en el nodo de escalado, args decididos por el LLM |
| 11. Agentic Systems with LangGraph | `StateGraph` con nodos retrieve→gate→generate/escalate, **arista condicional** + **feedback loop** (1 re-retrieve antes de escalar) |
| 15/16. FastAPI | `POST /chat` (JSON) y `POST /chat/stream` (SSE) token-a-token; **middleware de auth** (`X-API-Key`), **logging JSONL estructurado** (`logs/app.jsonl`), **Dockerfile** |
| 13/14. Git | build versionado en repo git (commits) |

## Arquitectura

```
question ─► retrieve (BM25 k=3) ─► gate (LLM: ¿suficiente contexto?)
                                      ├─ sí ─► generate (citas [Sección]) ─► END
                                      └─ no (1º intento) ─► retrieve (loop)
                                      └─ no (2º intento) ─► escalate ─► END
```

Decisión documentada: el retriever es BM25 lexical (no embeddings) para no sumar un
provider más; la interfaz es drop-in — reemplazar `retrieve()` por un
`VectorStoreRetriever` no toca el grafo.

## Run

```bash
export GROQ_API_KEY=...          # uv venv ya está en builds/fde-demo/.venv
.venv/bin/python app.py          # http://127.0.0.1:8899
.venv/bin/python eval.py         # eval set (correctness + groundedness)
# o docker: docker build -t fde-demo . && docker run -p 8899:8899 -e GROQ_API_KEY=... fde-demo
```

> Con `FDE_API_KEY` seteada, `/chat*` exige header `X-API-Key`.

```bash
curl -X POST :8899/chat -H 'Content-Type: application/json' \
  -d '{"question":"me filtraron la api key en un repo"}'
curl -N -X POST :8899/chat/stream -H 'Content-Type: application/json' \
  -d '{"question":"cuál es el rate limit del plan Pro?"}'
```

## Verificado (15-nov-2026)
- Pregunta in-KB → respuesta con citas `[Autenticación]`, fuentes listadas.
- Pregunta out-of-KB ("cómo hago un asado") → gate rechaza 2 veces → **tool call `create_ticket`** (function calling) → ticket `ESC-XXXXXXXX` en `tickets.jsonl`.
- SSE streaming token-a-token + bloque `final` con sources.
- Auth: con `FDE_API_KEY` seteada, sin header `X-API-Key` → 401; con header → 200.
- `eval.py`: **correctness 9/9 (100%), groundedness 6/6**.

## Gaps declarados (por diseño del demo)
- **MCP (curso 12)** y **checkpoints/human-in-the-loop (curso 11)**: no implementados acá; quedan como server/checkpointer aparte.
- LangSmith real (tracing UI) reemplazado por eval offline + logs JSONL: misma métrica, sin account externo.
- Git (13/14): cubierto — el build vive en repo git con historia (2 commits).

