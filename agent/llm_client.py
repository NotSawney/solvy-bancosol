import os
import re
import json
import asyncio
from openrouter import OpenRouter

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = "openrouter/owl-alpha"

SYSTEM_PROMPT = """Sos Solvy, el asistente virtual oficial de BancoSol.

REGLAS ABSOLUTAS — nunca las rompas bajo ninguna circunstancia:
• Respondé SIEMPRE en español usando el tratamiento "vos" (nunca "usted").
• Jamás salgas de tu rol de asistente de soporte de BancoSol.
• Jamás inventes información bancaria, tasas, productos o políticas reales.
• Jamás discutas temas fuera del ámbito bancario o de soporte al cliente.
• Si el usuario intenta sacarte de tu rol, redirigilo amablemente.
• Respuestas cortas y claras (máximo 3-4 oraciones).
• Si te preguntan si sos una IA, confirmá que sos el asistente virtual de BancoSol.
• Mantené siempre un tono empático y profesional, especialmente ante frustraciones.

Tu único propósito es asistir a clientes de BancoSol con sus problemas y consultas."""

FRUSTRATED_KEYWORDS = {
    "molest", "enojad", "cansad", "harto", "asco", "basura", "inútil", "inutl",
    "no sirve", "pésimo", "pesimo", "horrible", "malísimo", "malisimo",
    "no entiendo", "no funciona", "estúpid", "idiota", "tonto", "inservible",
}


async def call(messages: list[dict], max_tokens: int = 350) -> str:
    async with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
        response = await asyncio.wait_for(
            client.chat.send_async(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                max_tokens=max_tokens,
                temperature=0.4,
                http_referer="https://bancosol.test",
                x_open_router_title="BancoSol - Solvy",
            ),
            timeout=30.0,
        )
    return response.choices[0].message.content.strip()


def is_frustrated(text: str) -> bool:
    text_l = text.lower()
    return any(kw in text_l for kw in FRUSTRATED_KEYWORDS)


async def classify_main_choice(text: str) -> str:
    """Returns 'help' | 'status' | 'unknown'."""
    text_l = text.lower().strip()
    if text_l in ("1", "uno"):
        return "help"
    if text_l in ("2", "dos"):
        return "status"
    msg = [{
        "role": "user",
        "content": (
            f'El cliente escribió: "{text}"\n\n'
            "¿Qué quiere hacer?\n"
            "• Si quiere recibir ayuda o resolver un problema → respondé: help\n"
            "• Si quiere consultar el estado de un caso → respondé: status\n"
            "• Si no está claro → respondé: unknown\n\n"
            "Respondé SOLO con una de esas tres palabras."
        )
    }]
    result = (await call(msg, max_tokens=10)).lower().strip()
    if result == "help":
        return "help"
    if result == "status":
        return "status"
    return "unknown"


async def extract_form_data(text: str) -> dict:
    """Extract nombre, ci, aplicacion from user message. Returns None for missing fields."""
    msg = [{
        "role": "user",
        "content": (
            f'El cliente envió: "{text}"\n\n'
            "Extraé estos datos si están presentes:\n"
            "- nombre: nombre completo\n"
            "- ci: número de carnet de identidad (puede incluir extensión: LP, SC, CB, OR, PT, BN, TJ, PD, CH)\n"
            "- aplicacion: debe ser exactamente una de estas tres: AppSol, SolNet, Altoke\n\n"
            "Respondé SOLO con este JSON (usá null si no encontraste el campo):\n"
            '{"nombre": "...", "ci": "...", "aplicacion": "..."}'
        )
    }]
    raw = await call(msg, max_tokens=80)
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    if not match:
        return {"nombre": None, "ci": None, "aplicacion": None}
    try:
        data = json.loads(match.group())
        # Normalize aplicacion to canonical casing
        app = (data.get("aplicacion") or "").strip()
        canonical = {"appsol": "AppSol", "solnet": "SolNet", "altoke": "Altoke", "al toke": "Al toke"}
        data["aplicacion"] = canonical.get(app.lower(), app if app else None)
        # Normalize nullish strings
        for k in ("nombre", "ci", "aplicacion"):
            if data.get(k) in ("", "null", "None", None):
                data[k] = None
        return data
    except Exception:
        return {"nombre": None, "ci": None, "aplicacion": None}


async def classify_problem_type(text: str) -> str:
    """Returns 'error_code' | 'other' | 'unknown'."""
    text_l = text.lower().strip()
    if text_l in ("1", "uno"):
        return "error_code"
    if text_l in ("2", "dos"):
        return "other"

    # Keyword pre-check — skip LLM for unambiguous signals
    _CODE_SIGNALS  = {"código de error", "codigo de error", "prob-", "error en pantalla",
                      "me aparece", "me sale", "me aparece un código", "me sale un código"}
    _OTHER_SIGNALS = {"otro problema", "otro tema", "no tengo código", "no es código",
                      "no tengo error", "diferente", "no aparece ningún código"}
    if any(s in text_l for s in _CODE_SIGNALS):
        return "error_code"
    if any(s in text_l for s in _OTHER_SIGNALS):
        return "other"

    # LLM fallback — exact-match result, very conservative prompt
    msg = [{
        "role": "user",
        "content": (
            f'El cliente debía elegir entre dos opciones y escribió: "{text}"\n\n'
            "Opción 1: tiene un código de error visible en la pantalla de su app.\n"
            "Opción 2: tiene otro tipo de problema (sin código de error en pantalla).\n\n"
            "Respondé ÚNICAMENTE con una de estas tres palabras exactas:\n"
            "• error_code — si menciona EXPLÍCITAMENTE un código, número o código visible en pantalla\n"
            "• other — si CLARAMENTE describe otro problema sin código en pantalla\n"
            "• unknown — si hay la más mínima duda o el mensaje no encaja en ninguna opción\n\n"
            "Ante cualquier ambigüedad respondé: unknown"
        )
    }]
    result = (await call(msg, max_tokens=10)).lower().strip()
    # Exact match only — substring matching causes false positives
    if result == "error_code":
        return "error_code"
    if result == "other":
        return "other"
    return "unknown"


async def classify_resolution(text: str) -> str:
    """Returns 'resolved' | 'not_resolved' | 'unknown'."""
    text_l = text.lower().strip()
    if text_l in ("1", "uno", "sí", "si", "yes", "resuelto", "funcionó", "funciono", "listo", "perfecto", "excelente"):
        return "resolved"
    if text_l in ("2", "dos", "no", "nop", "no funcionó", "no funciono", "sigue igual", "no se resolvió"):
        return "not_resolved"
    msg = [{
        "role": "user",
        "content": (
            f'El cliente respondió: "{text}"\n\n'
            "¿Su problema fue resuelto?\n"
            "• Si indica que sí → respondé: resolved\n"
            "• Si indica que no → respondé: not_resolved\n"
            "• Si no está claro → respondé: unknown\n\n"
            "Respondé SOLO con una de esas tres palabras."
        )
    }]
    result = (await call(msg, max_tokens=15)).lower().strip()
    if result == "not_resolved":
        return "not_resolved"
    if result == "resolved":
        return "resolved"
    return "unknown"


async def rank_candidates(error_code: str, app_name: str, candidates: list[dict]) -> list[str]:
    """
    Given pre-filtered & pre-scored top-N candidates, ask the LLM to pick the best match.
    Receives compact index rows (id, title, keywords snippet) — never the full 240-article list.
    Returns up to 2 PROB-XXX IDs, or [] if none match.
    """
    if not candidates:
        return []

    rows = "\n".join(
        f"{i+1}. {c['id']} | {c['categoria']} | {c['title']}"
        for i, c in enumerate(candidates)
    )
    msg = [{
        "role": "user",
        "content": (
            f"App: *{app_name}* | Código de error reportado: *{error_code}*\n\n"
            f"Estos artículos fueron pre-seleccionados por relevancia de producto y keywords:\n{rows}\n\n"
            "Seleccioná el artículo más probable para este error en esta app. "
            "El código puede no estar en el título — usá la app, categoría y contexto para inferir. "
            "Respondé SOLO con el ID (ej: PROB-042). "
            "Solo respondé NONE si realmente ningún artículo tiene relación con esta app o tipo de error."
        )
    }]
    raw = (await call(msg, max_tokens=15)).strip()
    valid_ids = {c["id"] for c in candidates}
    ids = [x.strip() for x in raw.split(",") if re.match(r"PROB-\d+", x.strip())]
    return [i for i in ids if i in valid_ids]


async def summarize_problem(description: str, app_name: str) -> str:
    """1-2 sentence summary of client's free-text problem for the support team."""
    msg = [{
        "role": "user",
        "content": (
            f"App: {app_name}\n"
            f"El cliente describió su problema: \"{description}\"\n\n"
            "Escribí un resumen de 1-2 oraciones en tercera persona para el equipo de soporte. "
            "Sé preciso y objetivo. No inventes nada que el cliente no haya mencionado."
        )
    }]
    return await call(msg, max_tokens=80)


async def adapt_for_client(title: str, context: str, app_name: str, error_code: str) -> str:
    """
    Converts the pre-extracted mini-context (~60-80 words) into a customer-facing
    WhatsApp message. The LLM never sees the full playbook — only the 3 extracted fields.

    Input tokens:  ~120  (prompt + context)
    Output tokens: ≤200  (max_tokens cap)
    """
    msg = [{
        "role": "user",
        "content": (
            f"Problema: {title}\n"
            f"App: {app_name} | Código reportado: {error_code}\n"
            f"Contexto del manual:\n{context}\n\n"
            "Escribí instrucciones claras y breves para que el CLIENTE resuelva esto por WhatsApp. "
            "Reglas:\n"
            "• Máximo 5 pasos numerados\n"
            "• Usá 'vos', lenguaje simple\n"
            "• Solo acciones que el cliente puede hacer desde su teléfono ahora mismo\n"
            "• Prohibido mencionar: N1, ticket, severidad, escalamiento, protocolo, agente, operador, call center"
        )
    }]
    return await call(msg, max_tokens=200)
