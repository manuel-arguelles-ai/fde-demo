"""Gate anti-alucinación vía Jev (TypeSafe) — decisión estructurada con confianza.

Reemplaza el judge LLM conversacional por una clasificación nativa:
POST /v1/systemone con una pregunta `choice` de dos clases
(suficiente / insuficiente) → {choice, confidence, probabilities}.

La API key NO vive en el repo: variable de entorno JEV_API_KEY.
Si no está seteada, app.py hace fallback al gate LLM original.
"""
from __future__ import annotations

import json
import os
import urllib.request

BASE_URL = "https://api.typesafe.ai"
MODEL = os.environ.get("JEV_MODEL", "jev-latest")

INSTRUCTIONS = (
    "Decide si el CONTEXTO RECUPERADO permite responder la PREGUNTA DEL USUARIO "
    "con fidelidad, usando solo el contexto. 'suficiente' si el contexto contiene "
    "la información necesaria para responder; 'insuficiente' si no la contiene, "
    "es parcial, tangencial o corresponde a otro tema."
)
CRITERIA = {
    "suficiente": (
        "El contexto contiene la información necesaria para responder la pregunta "
        "del usuario de forma fiel y completa."
    ),
    "insuficiente": (
        "El contexto no contiene la información necesaria, es parcial, tangencial "
        "o corresponde a otro tema distinto de la pregunta."
    ),
}


def available() -> bool:
    return bool(os.environ.get("JEV_API_KEY"))


def _key() -> str:
    k = os.environ.get("JEV_API_KEY")
    if not k:
        raise RuntimeError("JEV_API_KEY no seteada")
    return k


def classify(question: str, context: str) -> dict:
    """Devuelve {choice, confidence, probabilities, usage}."""
    body = {
        "model": MODEL,
        "state": f"PREGUNTA DEL USUARIO:\n{question}\n\nCONTEXTO RECUPERADO:\n{context}",
        "questions": {
            "gate": {
                "type": "choice",
                "instructions": INSTRUCTIONS,
                "criteria": CRITERIA,
            }
        },
    }
    last: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"{BASE_URL}/v1/systemone",
                data=json.dumps(body).encode(),
                headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/json"},
                method="POST",
            )
            r = json.loads(urllib.request.urlopen(req, timeout=90).read())
            a = r["answers"]["gate"]
            return {
                "choice": a["choice"],
                "confidence": a["confidence"],
                "probabilities": a.get("probabilities", {}),
                "usage": r.get("usage"),
            }
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"Jev gate falló tras 3 intentos: {last}")
