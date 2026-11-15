"""fde-demo — Forward Deployed Engineer (Build del track DataCamp).

Bot de soporte N1 estilo Forward Deployed Engineer:
  retriever BM25 two-stage  →  gate de relevancia (LLM)  →  generador con citas
  └→ si el gate falla 2 veces → arista condicional a ESCALADO (nota humana)

Todo el grafo es un StateGraph de LangGraph (aristas condicionales + feedback
loop, patrón exacto de los cursos del track). Servido por FastAPI con
streaming SSE en /chat.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal, TypedDict

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import gate_jev
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

KB = Path(__file__).parent / "docs" / "kb.md"
MODEL = os.environ.get("FDE_MODEL", "openai/gpt-oss-120b")

llm = ChatGroq(model=MODEL, temperature=0, streaming=True)
llm_quiet = ChatGroq(model=MODEL, temperature=0, streaming=False)

# ---------------------------------------------------------------- Tools (curso 10)
from langchain_core.tools import tool

TICKETS = Path(__file__).parent / "tickets.jsonl"

@tool
def create_ticket(question: str, context: str) -> str:
    """Crea un ticket de escalado para el equipo de ingeniería. Retorna el ID del ticket."""
    tid = f"ESC-{uuid.uuid4().hex[:8].upper()}"
    TICKETS.parent.mkdir(exist_ok=True)
    with TICKETS.open("a") as f:
        f.write(json.dumps({"id": tid, "question": question, "context": context,
                            "created_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    return tid

# ---------------------------------------------------------------- Observabilidad (curso 16)
LOGS = Path(__file__).parent / "logs"
LOGS.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler(LOGS / "app.jsonl"), logging.StreamHandler()],
)
log = logging.getLogger("fde")

def log_event(event: str, **fields):
    log.info(json.dumps({"event": event, **fields, "ts": time.time()}))

# ---------------------------------------------------------------- RAG (BM25)
# Los cursos de embeddings/vector-store del track asumen un embedding provider;
# acá usamos BM25 two-stage (lexical) para no depender de una key extra.
# La arquitectura retriever→gate→generate es la misma: cambiar el retriever
# por un VectorStoreRetriever no toca el grafo.

def load_chunks() -> list[dict]:
    text = KB.read_text()
    sections = re.split(r"\n## ", text)[1:]
    chunks = []
    for i, sec in enumerate(sections):
        title, _, body = sec.partition("\n")
        chunks.append({"id": i, "title": title.strip(), "body": body.strip()})
    return chunks

CHUNKS = load_chunks()
TOKEN_RE = re.compile(r"[a-záéíóúñ0-9]{2,}", re.I)

def tokenize(s: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(s)]

BM25 = None
def build_bm25():
    global BM25
    from collections import Counter
    import math
    docs = [tokenize(c["title"] + " " + c["body"]) for c in CHUNKS]
    N, avgdl = len(docs), sum(map(len, docs)) / len(docs)
    df = Counter(t for d in docs for t in set(d))
    def score(query, index):
        q, d = Counter(tokenize(query)), Counter(docs[index])
        s = 0.0
        for t, qf in q.items():
            if t not in d: continue
            idf = math.log(1 + (N - df[t] + 0.5) / (df[t] + 0.5))
            tf = d[t]
            s += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(d) / avgdl))
        return s
    BM25 = score

build_bm25()

def retrieve(query: str, k: int = 3) -> list[dict]:
    ranked = sorted(range(len(CHUNKS)), key=lambda i: -BM25(query, i))
    return [CHUNKS[i] for i in ranked[:k] if BM25(query, i) > 0]

# ---------------------------------------------------------------- State

class State(TypedDict):
    question: str
    docs: list[dict]
    relevant: bool
    answer: str
    attempts: int
    escalated: bool
    jev: dict | None

def retrieve_node(state: State) -> dict:
    return {"docs": retrieve(state["question"]), "attempts": state.get("attempts", 0)}

def gate_node(state: State) -> dict:
    """Gate LLM-as-judge + segunda opinión Jev (opcional, defense in depth).

    Si JEV_API_KEY está seteada y el gate LLM dice 'suficiente', se consulta
    Jev (decisión estructurada con confianza). Si Jev disiente, el estado lo
    registra y el router lo trata como 'no relevante' → loop de reformulación.
    """
    if not state["docs"]:
        return {"relevant": False}
    ctx = "\n\n".join(f"[{d['title']}]\n{d['body']}" for d in state["docs"])
    msg = llm_quiet.invoke([
        SystemMessage(content="Responde SOLO si o no, minúscula."),
        HumanMessage(content=f"Pregunta: {state['question']}\n\n¿Este contexto permite responder con fidelidad?\n\n{ctx}"),
    ])
    relevant = msg.content.strip().lower().startswith("s")
    jev_info = None
    if relevant and gate_jev.available():
        try:
            jev = gate_jev.classify(state["question"], ctx)
            jev_info = {"choice": jev["choice"], "confidence": round(jev["confidence"], 2)}
            log_event("jev_gate", choice=jev["choice"], confidence=jev_info["confidence"], question=state["question"][:60])
            if jev["choice"] != "suficiente":
                relevant = False  # segunda opinión en contra → no generar
        except Exception as e:  # Jev caído no bloquea el demo
            log_event("jev_gate_error", error=str(e)[:120])
    return {"relevant": relevant, "jev": jev_info}

def generate_node(state: State) -> dict:
    ctx = "\n\n".join(f"[{d['title']}]\n{d['body']}" for d in state["docs"])
    msg = llm.invoke([
        SystemMessage(content=(
            "Sos soporte de Nix Cloud. Respondé en español, concreto, con pasos si aplica. "
            "CITÁ la sección entre corchetes que usaste, p.ej. [Webhooks]. "
            "Si no está en el contexto, decilo sin inventar."
        )),
        HumanMessage(content=f"Contexto:\n{ctx}\n\nPregunta: {state['question']}"),
    ])
    return {"answer": msg.content, "relevant": True, "escalated": False}

def escalate_node(state: State) -> dict:
    # Tool use real (curso 10): el LLM decide los argumentos del ticket vía function calling
    decision = llm_quiet.bind_tools([create_ticket]).invoke([
        SystemMessage(content="Escalás casos a ingeniería. Creá el ticket con la pregunta y un contexto breve del caso."),
        HumanMessage(content=f"Pregunta sin respuesta documentada: {state['question']}"),
    ])
    tid = None
    for call in (decision.tool_calls or []):
        if call["name"] == "create_ticket":
            result = create_ticket.invoke(call["args"])
            tid = result
            log_event("ticket_created", ticket_id=tid, question=state["question"])
    return {
        "answer": (f"No tengo esa información documentada. Creé el ticket de escalado "
                   f"**{tid}** para ingeniería con tu pregunta; te contactamos hoy."),
        "escalated": True,
        "relevant": False,
    }

def gate_router(state: State) -> Literal["generate", "retrieve", "escalate"]:
    if state["relevant"]:
        return "generate"
    # feedback loop: un re-retrieve con la pregunta reformulada antes de escalar
    if state.get("attempts", 0) < 1:
        return "retrieve"
    return "escalate"

def bump(state: State) -> dict:
    return {"attempts": state.get("attempts", 0) + 1}

# ---------------------------------------------------------------- Grafo
g = StateGraph(State)
g.add_node("retrieve", retrieve_node)
g.add_node("bump", bump)
g.add_node("gate", gate_node)
g.add_node("generate", generate_node)
g.add_node("escalate", escalate_node)
g.set_entry_point("retrieve")
g.add_edge("retrieve", "bump")
g.add_edge("bump", "gate")
g.add_conditional_edges("gate", gate_router, {"generate": "generate", "retrieve": "retrieve", "escalate": "escalate"})
g.add_edge("generate", END)
g.add_edge("escalate", END)
app_graph = g.compile()

# ---------------------------------------------------------------- FastAPI
api = FastAPI(title="fde-demo — Forward Deployed Engineer Build")

# Auth por API key (curso 16) — opcional: si FDE_API_KEY está seteada, exige el header X-API-Key
API_KEY = os.environ.get("FDE_API_KEY")

@api.middleware("http")
async def auth_and_log(request, call_next):
    if API_KEY and request.url.path.startswith("/chat"):
        if request.headers.get("X-API-Key") != API_KEY:
            log_event("auth_rejected", path=request.url.path)
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    t0 = time.time()
    resp = await call_next(request)
    log_event("request", path=request.url.path, status=resp.status_code, ms=round((time.time() - t0) * 1000))
    return resp

@api.get("/")
def root():
    return FileResponse(Path(__file__).parent / "static" / "index.html", media_type="text/html")

@api.get("/health")
def health():
    return {"ok": True, "chunks": len(CHUNKS), "model": MODEL}

@api.post("/chat")
def chat(body: dict):
    q = (body.get("question") or "").strip()
    if not q:
        return {"error": "falta 'question'"}
    result = app_graph.invoke({"question": q})
    return {
        "answer": result["answer"],
        "escalated": result.get("escalated", False),
        "sources": [d["title"] for d in result.get("docs", [])],
        "attempts": result.get("attempts", 0),
    }

@api.post("/chat/stream")
def chat_stream(body: dict):
    q = (body.get("question") or "").strip()
    result = app_graph.invoke({"question": q})

    def gen():
        if result.get("escalated"):
            yield f"data: {json.dumps({'delta': result['answer'], 'final': True})}\n\n"
            return
        sys = SystemMessage(content=(
            "Sos soporte de Nix Cloud. Respondé en español, concreto, con pasos si aplica. "
            "CITÁ la sección entre corchetes que usaste. Si no está en el contexto, decilo."
        ))
        ctx = "\n\n".join(f"[{d['title']}]\n{d['body']}" for d in result["docs"])
        for chunk in llm.stream([sys, HumanMessage(content=f"Contexto:\n{ctx}\n\nPregunta: {q}")]):
            if chunk.content:
                yield f"data: {json.dumps({'delta': chunk.content})}\n\n"
        yield f"data: {json.dumps({'final': True, 'sources': [d['title'] for d in result['docs']]})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(api, host="127.0.0.1", port=8899)
