"""Evaluación del fde-demo (patrón LangSmith del curso 8, versión offline).

Métricas por caso: correctness (¿answer vs escalate según expect?) y
groundedness (¿la respuesta cita la sección esperada?).
Run: .venv/bin/python eval.py  (requiere GROQ_API_KEY)
"""
import json
import os
import sys

if not os.environ.get("GROQ_API_KEY"):
    print("Falta GROQ_API_KEY"); sys.exit(1)

import app as fde

cases = json.load(open("eval_set.json"))
correct = grounded = 0
print(f"{'caso':52} esperado   obtenido   cites?   result")
for c in cases:
    state = fde.app_graph.invoke({"question": c["question"]})
    got_answer = not state.get("escalated")
    ok = (c["expect"] == "answer") == got_answer
    cites = (c["must_cite"] in state.get("answer", "")) if c["expect"] == "answer" else None
    correct += ok
    grounded += bool(cites) if cites is not None else 0
    flag = "✅" if ok and (cites is not False) else "❌"
    print(f"{c['question'][:50]:52} {c['expect']:10} {'answer' if got_answer else 'escalate':10} "
          f"{'—' if cites is None else ('✔' if cites else '✘')}     {flag}")

n = len(cases)
print(f"\nCorrectness: {correct}/{n} ({correct/n:.0%})")
print(f"Groundedness (cita esperada): {grounded}/{sum(1 for c in cases if c['expect']=='answer')}")
