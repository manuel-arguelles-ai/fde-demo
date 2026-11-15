"""Dataset de calibración del gate (pregunta, contexto, etiqueta) + benchmark LLM vs Jev.

12 preguntas hand-written (2 por sección del corpus) × contextos:
  - positivo: top-3 de BM25 tal como el retriever lo arma (contexto correcto)
  - 2 negativos: top-3 de OTRAS preguntas de OTRA sección (mismatch duro)
  → los "negativos" de la misma sección se EXCLUYEN (el contexto suele contener
    la respuesta: la etiqueta 'insuficiente' sería inválida)

Modos:
  .venv/bin/python calibrate_gate.py build          # regenera gate_calib.json
  .venv/bin/python calibrate_gate.py                # benchmark: Jev + LLM-judge sobre el set
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import app as fde  # BM25 real + llm_quiet (judge LLM) + retrieve
import gate_jev

# (pregunta, sección de la pregunta)
QUESTIONS = [
    ("me quedó filtrada la API key en un repo, qué hago?", "Autenticación"),
    ("cómo roto una API key sin romper producción?", "Autenticación"),
    ("cuál es el rate limit del plan Pro y qué pasa si lo excedo?", "Límites de la API"),
    ("qué significa el error 409 version_conflict y cómo lo resuelvo?", "Errores comunes"),
    ("mi webhook no responde en 5 segundos, qué pasa?", "Webhooks"),
    ("cómo verifico la firma de un webhook?", "Webhooks"),
    ("cuánto cuesta el plan Enterprise y qué incluye?", "Plan y precios"),
    ("qué incluye el plan Starter gratis?", "Plan y precios"),
    ("el downgrade cuándo aplica y cómo es el prorrateo?", "Plan y precios"),
    ("qué SLA tiene el plan Pro y cómo reclamo créditos?", "SLA y status"),
    ("dónde veo el estado de los incidentes?", "SLA y status"),
    ("el payload máximo de la API cuánto es y qué pasa si lo paso?", "Límites de la API"),
]


def context_for(question: str, mode: str) -> str:
    """mode: 'pos' = top-3 real del retriever; 'negA'/'negB' = top-3 de otra pregunta."""
    if mode == "pos":
        docs = fde.retrieve(question, k=3)
    else:
        qs = [q for q, _ in QUESTIONS]
        idx = qs.index(question)
        other = qs[(idx + (3 if mode == "negA" else 7)) % len(qs)]
        docs = fde.retrieve(other, k=3)
    return "\n\n".join(f"[{d['title']}]\n{d['body']}" for d in docs)


def build():
    pairs = []
    qs = [q for q, _ in QUESTIONS]
    for idx, (q, section) in enumerate(QUESTIONS):
        pairs.append({"question": q, "section_q": section, "context": context_for(q, "pos"),
                      "label": "suficiente", "kind": "pos", "section_ctx": section})
        for mode in ("negA", "negB"):
            other_idx = (idx + (3 if mode == "negA" else 7)) % len(qs)
            other_section = QUESTIONS[other_idx][1]
            pairs.append({"question": q, "section_q": section, "context": context_for(q, mode),
                          "label": "insuficiente", "kind": mode, "section_ctx": other_section})
    Path(__file__).with_name("gate_calib.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=1))
    n = len(pairs)
    print(f"gate_calib.json: {n} pares ({sum(p['label'] == 'suficiente' for p in pairs)} pos)")


def load_pairs():
    pairs = json.loads(Path(__file__).with_name("gate_calib.json").read_text())
    excluded = [p for p in pairs if p["kind"] != "pos" and p["section_ctx"] == p["section_q"]]
    pairs = [p for p in pairs if p not in excluded]
    if excluded:
        print(f"excluidos {len(excluded)} negativos de la misma sección (etiqueta inválida)")
    return pairs


def llm_gate(question: str, context: str) -> str:
    ctx = context
    msg = fde.llm_quiet.invoke([
        fde.SystemMessage(content="Responde SOLO si o no, minúscula."),
        fde.HumanMessage(content=f"Pregunta: {question}\n\n¿Este contexto permite responder con fidelidad?\n\n{ctx}"),
    ])
    return "suficiente" if msg.content.strip().lower().startswith("s") else "insuficiente"


def main():
    pairs = load_pairs()
    results = []
    for i, p in enumerate(pairs):
        jev = gate_jev.classify(p["question"], p["context"])
        llm = llm_gate(p["question"], p["context"])
        results.append({**p, "jev_choice": jev["choice"], "jev_conf": round(jev["confidence"], 2),
                        "llm_choice": llm,
                        "jev_ok": jev["choice"] == p["label"], "llm_ok": llm == p["label"]})
        print(f"{i+1:2}/{len(pairs)} [{p['kind']}] {p['question'][:34]:34} "
              f"jev:{jev['choice'][:4]}({jev['confidence']:.2f}){'✅' if jev['choice'] == p['label'] else '❌'} "
              f"llm:{llm[:4]}{'✅' if llm == p['label'] else '❌'}")
    n = len(results)
    summary = {
        "n": n,
        "jev_accuracy": round(sum(r["jev_ok"] for r in results) / n, 3),
        "llm_accuracy": round(sum(r["llm_ok"] for r in results) / n, 3),
        "jev_precision_pos": round(sum(r["jev_ok"] for r in results if r["label"] == "suficiente") / max(1, sum(1 for r in results if r["label"] == "suficiente")), 3),
        "jev_precision_neg": round(sum(r["jev_ok"] for r in results if r["label"] == "insuficiente") / max(1, sum(1 for r in results if r["label"] == "insuficiente")), 3),
        "results": results,
    }
    # umbrales Jev sobre los positivos/negativos bien clasificados
    pos_ok = [r["jev_conf"] for r in results if r["label"] == "suficiente" and r["jev_ok"]]
    neg_ok = [r["jev_conf"] for r in results if r["label"] == "insuficiente" and r["jev_ok"]]
    hi = min(pos_ok) if pos_ok else 0.9
    lo = max(neg_ok) if neg_ok else 0.5
    summary["jev_hi"] = round(hi, 2)
    summary["jev_lo"] = round(lo, 2)
    summary["jev_separable"] = lo < hi
    Path(__file__).with_name("gate_benchmark.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"\nexactitud  jev {summary['jev_accuracy']:.0%} · llm {summary['llm_accuracy']:.0%}")
    print(f"jev precision pos {summary['jev_precision_pos']} / neg {summary['jev_precision_neg']} · hi {hi} · lo {lo} · separable={summary['jev_separable']}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        main()
