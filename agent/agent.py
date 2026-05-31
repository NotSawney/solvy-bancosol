"""
Solvy — Agente virtual de BancoSol

Etiquetas del flujo:
  00_inicio → awaiting_main_choice
    ├─ 1 → 01_recibir_ayuda → form_datos
    │         ↓ (nombre+CI+app completos)
    │       02_solicitar_tipo_problema → awaiting_problem_type
    │         ├─ 1 → 03A_solicitar_codigo_error → awaiting_error_code
    │         │         ↓ (código PROB-NNN válido)
    │         │       04A_buscar_solucion → 05A_mostrar_solucion → solution_presented
    │         │         ├─ 1 → 06A_cierre_encuesta → awaiting_survey → done
    │         │         └─ 2 → 07A_derivar_solvycall → done
    │         └─ 2 → 03B_solicitar_descripcion → awaiting_problem_description
    │                   ↓ (descripción libre del cliente)
    │                 03B_derivar_solvycall → done
    └─ 2 → 01B_consultar_estado → done
"""
import os
import re
import json
import time
from datetime import datetime

import state_store as store
from evolution_client import send_text
from backend_client import open_case
from llm_client import (
    is_frustrated,
    classify_main_choice,
    extract_form_data,
    classify_problem_type,
    classify_resolution,
    rank_candidates,
    adapt_for_client,
    summarize_problem,
)
from kb import (load_index, find_by_id, filter_by_product,
                score_candidates, get_client_context, get_title, PRODUCT_MAP)
from gate import is_cancelled

ALLOWED_NUMBERS  = set(os.getenv("ALLOWED_NUMBERS", "59160879844").split(","))
SUPPORT_NUMBER   = os.getenv("SUPPORT_NUMBER", "59173188382")
SUPPORT_JID      = SUPPORT_NUMBER + "@s.whatsapp.net"
INACTIVITY_HOURS = float(os.getenv("INACTIVITY_HOURS", "24"))
CASE_STATUS_URL  = os.getenv("CASE_STATUS_URL", "[ENLACE]")

RESET_WORDS = {"reset", "/reset", "reiniciar", "inicio", "empezar", "salir"}
BACK_WORDS  = {"volver", "atras", "atrás", "regresar", "anterior", "/volver"}

BACK_NAV = {
    "awaiting_error_code":          ("awaiting_problem_type", "02_solicitar_tipo_problema"),
    "awaiting_problem_type":        ("awaiting_main_choice",  "00_inicio"),
    "awaiting_problem_description": ("awaiting_problem_type", "02_solicitar_tipo_problema"),
    "form_datos":                   ("awaiting_main_choice",  "00_inicio"),
}


def normalize_error_code(text: str) -> str | None:
    """
    Accepts PROB-### in any reasonable form and normalizes to 'PROB-NNN'.
    Handles: 'PROB-001', 'PROB-1', 'prob 42', '42', 'mi código es PROB-023'.
    Returns None if no valid code found.
    """
    m = re.search(r'PROB[-\s]?(\d{1,3})', text, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 999:
            return f"PROB-{n:03d}"
    m = re.search(r'\b(\d{1,3})\b', text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 999:
            return f"PROB-{n:03d}"
    return None


# ── Mensajes del script ──────────────────────────────────────────────────────

MSG = {
    "00_inicio": (
        "*¡Hola! Soy Solvy*, asistente virtual de BancoSol. 👋\n\n"
        "Gracias por comunicarte conmigo.\n\n"
        "¿En qué puedo ayudarte?\n\n"
        "1️⃣ Recibir ayuda\n"
        "2️⃣ Consultar el estado de un caso\n\n"
        "Respondé con 1 o 2, o escribime tu consulta."
    ),
    "01_recibir_ayuda": (
        "Gracias por elegir 1️⃣ Recibir ayuda.\n\n"
        "Para poder orientarte mejor, por favor compartinos estos datos:\n\n"
        "1. Nombre completo\n"
        "2. Número de carnet de identidad\n"
        "3. Aplicación que usás actualmente: AppSol, SolNet o Altoke"
    ),
    "02_solicitar_tipo_problema": (
        "Gracias por compartir tus datos.\n\n"
        "Ahora contame qué tipo de problema estás experimentando:\n\n"
        "1️⃣ Me aparece un código de error en pantalla\n"
        "2️⃣ Tengo otro problema\n\n"
        "Respondé con 1 o 2.\n\n"
        "⬅️ Para volver al menú principal, escribí *volver*."
    ),
    "03A_solicitar_codigo_error": (
        "Gracias por elegir 1️⃣ Me aparece un código de error en pantalla.\n\n"
        "Por favor, reescribí el código de error tal como aparece en la pantalla de tu aplicación.\n\n"
        "Podés escribirlo como *PROB-001* o simplemente el número: *001*\n\n"
        "⬅️ Para volver al paso anterior, escribí *volver*."
    ),
    "03B_solicitar_descripcion": (
        "Gracias por elegir 2️⃣ Tengo otro problema.\n\n"
        "Para que el equipo pueda ayudarte mejor, describime con tus propias palabras "
        "qué está pasando con tu aplicación.\n\n"
        "⬅️ Para volver al paso anterior, escribí *volver*."
    ),
    "04A_buscar_solucion": (
        "Gracias por compartir el código.\n\n"
        "Estoy buscando una solución específica para tu consulta. "
        "Esto puede tomar unos segundos."
    ),
    "06A_cierre_encuesta": (
        "¡Qué bueno saber que se resolvió! 😊\n\n"
        "Gracias por comunicarte con Solvy, asistente virtual de BancoSol.\n"
        "Cuando necesités ayuda nuevamente, estaré aquí para orientarte.\n\n"
        "Antes de finalizar, ¿cómo calificarías la atención recibida?\n\n"
        "1️⃣ Buena\n"
        "2️⃣ Regular\n"
        "3️⃣ Mala"
    ),
    "07A_derivar_solvycall": (
        "Lamentamos que la solución no haya resuelto tu consulta. "
        "Para ayudarte mejor, ya registramos la información que compartiste, "
        "incluyendo el código de error y el detalle inicial del caso.\n\n"
        "Por favor, comunicate con el SolvyCall de BancoSol al:\n\n"
        "📞 73188382\n\n"
        "El asesor ya contará con tus datos y la información registrada, "
        "para poder orientarte con mayor rapidez.\n\n"
        "Gracias por comunicarte con Solvy, asistente virtual de BancoSol."
    ),
    "03B_derivar_solvycall": (
        "Gracias por compartir los detalles de tu caso.\n\n"
        "Ya registramos toda la información para que el equipo pueda ayudarte mejor.\n\n"
        "Por favor, comunicate con el SolvyCall de BancoSol al:\n\n"
        "📞 73188382\n\n"
        "El asesor ya contará con tus datos y el detalle de tu consulta, "
        "para poder orientarte con mayor rapidez.\n\n"
        "Gracias por comunicarte con Solvy, asistente virtual de BancoSol."
    ),
    "01B_consultar_estado": (
        "Gracias por elegir 2️⃣ Consultar el estado de un caso.\n\n"
        "Podés hacer seguimiento a tu caso ingresando al siguiente enlace:\n\n"
        f"🔗 {CASE_STATUS_URL}\n\n"
        "Tené a mano tu número de caso para consultar el estado actualizado.\n\n"
        "Gracias por comunicarte con Solvy, asistente virtual de BancoSol.\n"
        "Estoy aquí para orientarte cuando lo necesités."
    ),
    "V01_opcion_no_valida": (
        "No pude identificar la opción seleccionada.\n\n"
        "Por favor, respondé con una de estas opciones:\n\n"
        "1️⃣ Recibir ayuda\n"
        "2️⃣ Consultar el estado de un caso\n\n"
        "También podés escribirme tu consulta directamente."
    ),
    "V02_codigo_invalido": (
        "No encontré un código válido en tu mensaje. 🔍\n\n"
        "Por favor, reescribí el código tal como aparece en la pantalla de tu aplicación.\n\n"
        "Podés escribirlo como *PROB-001* o simplemente el número: *001*\n\n"
        "⬅️ Para volver al paso anterior, escribí *volver*."
    ),
    "V03_respuesta_confusa": (
        "Entiendo. Estoy aquí para ayudarte.\n\n"
        "Para poder orientarte mejor, compartime brevemente qué está pasando "
        "o elegí una opción:\n\n"
        "1️⃣ Recibir ayuda\n"
        "2️⃣ Consultar el estado de un caso"
    ),
}


# ── Helper de envío con historial ────────────────────────────────────────────

async def _send(remote_jid: str, phone: str, text: str) -> None:
    """Send to client and record the bot turn in conversation history."""
    await send_text(remote_jid, text)
    store.append_history(phone, "bot", text, int(time.time()))


# ── Handler principal ────────────────────────────────────────────────────────

async def handle_message(remote_jid: str, text: str, msg_ts: int | None = None):
    phone = remote_jid.replace("@s.whatsapp.net", "")

    if phone not in ALLOWED_NUMBERS:
        print(f"[Solvy] Ignorado: {phone}")
        return

    text_l = text.lower().strip()
    now    = msg_ts or int(time.time())

    # Reset: clears history first; greeting becomes first entry of new session
    if text_l in RESET_WORDS:
        store.reset(phone)
        store.touch(phone, now)
        await _send(remote_jid, phone, MSG["00_inicio"])
        store.update(phone, stage="awaiting_main_choice")
        return

    conv  = store.get(phone)
    stage = conv["stage"]
    print(f"[Solvy] {phone} | {stage} | {text[:60]!r}")

    if text_l in BACK_WORDS:
        store.append_history(phone, "cliente", text, now)
        nav = BACK_NAV.get(stage)
        if nav:
            target_stage, msg_key = nav
            store.update(phone, stage=target_stage)
            await _send(remote_jid, phone, MSG[msg_key])
        else:
            await _send(remote_jid, phone,
                "No es posible volver desde aquí. 😊\n\n"
                "Escribí *reiniciar* para empezar una nueva consulta."
            )
        return

    # ── Guardrail de inactividad — reset automático, 0 tokens ────────────────
    last_seen = conv.get("last_seen_at", 0)
    elapsed_hours = (now - last_seen) / 3600 if last_seen else 0
    if last_seen and elapsed_hours >= INACTIVITY_HOURS and stage not in ("initial", "done"):
        print(f"[Solvy] {phone} | inactividad {elapsed_hours:.1f}h → reset automático")
        store.reset(phone)
        store.touch(phone, now)
        await _send(remote_jid, phone, MSG["00_inicio"])
        store.update(phone, stage="awaiting_main_choice")
        return

    store.touch(phone, now)
    store.append_history(phone, "cliente", text, now)

    # ── 00: primer mensaje ───────────────────────────────────────────────────
    if stage == "initial":
        await _send(remote_jid, phone, MSG["00_inicio"])
        store.update(phone, stage="awaiting_main_choice")

    # ── Elección principal ───────────────────────────────────────────────────
    elif stage == "awaiting_main_choice":
        if is_frustrated(text):
            await _send(remote_jid, phone, MSG["V03_respuesta_confusa"])
            return

        choice = await classify_main_choice(text)
        if choice == "help":
            await _send(remote_jid, phone, MSG["01_recibir_ayuda"])
            store.update(phone, stage="form_datos")
        elif choice == "status":
            await _send(remote_jid, phone, MSG["01B_consultar_estado"])
            store.update(phone, stage="done")
        else:
            await _send(remote_jid, phone, MSG["V01_opcion_no_valida"])

    # ── Formulario: nombre + CI + aplicación ─────────────────────────────────
    elif stage == "form_datos":
        extracted = await extract_form_data(text)
        form = conv["form"].copy()

        for field in ("nombre", "ci", "aplicacion"):
            if extracted.get(field):
                form[field] = extracted[field]
        store.update(phone, form=form)

        missing = [f for f in ("nombre", "ci", "aplicacion") if not form.get(f)]
        if not missing:
            await _send(remote_jid, phone, MSG["02_solicitar_tipo_problema"])
            store.update(phone, stage="awaiting_problem_type")
        else:
            labels = {
                "nombre":     "Nombre completo",
                "ci":         "Número de carnet de identidad",
                "aplicacion": "Aplicación que usás: AppSol, SolNet o Altoke",
            }
            faltan = "\n".join(f"• *{labels[m]}*" for m in missing)
            await _send(remote_jid, phone, f"⚠️ El mensaje enviado no tiene el formato correcto.\nPara poder continuar con la atención, por favor enviá estos datos:\n\n{faltan}")

    # ── Tipo de problema ─────────────────────────────────────────────────────
    elif stage == "awaiting_problem_type":
        if is_frustrated(text):
            await _send(remote_jid, phone, MSG["V03_respuesta_confusa"])
            store.update(phone, stage="awaiting_main_choice")
            return

        ptype = await classify_problem_type(text)
        if ptype == "error_code":
            await _send(remote_jid, phone, MSG["03A_solicitar_codigo_error"])
            store.update(phone, stage="awaiting_error_code")
        elif ptype == "other":
            await _send(remote_jid, phone, MSG["03B_solicitar_descripcion"])
            store.update(phone, stage="awaiting_problem_description")
        else:
            await _send(remote_jid, phone,
                "No pude identificar la opción. Respondé con *1* (código de error) "
                "o *2* (otro problema)."
            )

    # ── Descripción libre (otro problema) ────────────────────────────────────
    elif stage == "awaiting_problem_description":
        form = {**conv["form"], "descripcion": text}
        resumen = await summarize_problem(text, form.get("aplicacion", ""))
        if is_cancelled(phone):
            return
        form["resumen"] = resumen
        store.update(phone, form=form)

        await _notify_support_other(phone, form)
        await _send(remote_jid, phone, MSG["03B_derivar_solvycall"])
        store.update(phone, stage="done")

    # ── Código de error ──────────────────────────────────────────────────────
    elif stage == "awaiting_error_code":
        error_code = normalize_error_code(text)
        if not error_code:
            await _send(remote_jid, phone, MSG["V02_codigo_invalido"])
            return
        form = {**conv["form"], "error_code": error_code}
        store.update(phone, form=form, stage="searching")

        await _send(remote_jid, phone, MSG["04A_buscar_solucion"])
        await _search_and_present(remote_jid, phone, form)

    # ── ¿Se resolvió? ────────────────────────────────────────────────────────
    elif stage == "solution_presented":
        resolution = await classify_resolution(text)
        if resolution == "resolved":
            await _send(remote_jid, phone, MSG["06A_cierre_encuesta"])
            store.update(phone, stage="awaiting_survey")
        elif resolution == "not_resolved":
            conv = store.get(phone)
            await _notify_support_unresolved(phone, conv["form"], conv.get("solutions_tried", []))
            await _send(remote_jid, phone, MSG["07A_derivar_solvycall"])
            store.update(phone, stage="done")
        else:
            await _send(remote_jid, phone,
                "No pude entender tu respuesta. ¿La solución te ayudó?\n\n"
                "1️⃣ Sí, se resolvió\n"
                "2️⃣ No, necesito más ayuda"
            )

    # ── Encuesta ─────────────────────────────────────────────────────────────
    elif stage == "awaiting_survey":
        ratings = {"1": "Buena", "2": "Regular", "3": "Mala",
                   "buena": "Buena", "regular": "Regular", "mala": "Mala"}
        rating = ratings.get(text.strip().lower())
        if rating:
            print(f"[Solvy] Encuesta {phone}: {rating}")
        await _send(remote_jid, phone, "¡Gracias por tu valoración! ✨ ¡Hasta luego!")
        store.reset(phone)

    # ── Conversación terminada → reiniciar ───────────────────────────────────
    elif stage in ("done", "searching"):
        store.reset(phone)
        store.touch(phone, now)
        await _send(remote_jid, phone, MSG["00_inicio"])
        store.update(phone, stage="awaiting_main_choice")

    else:
        store.reset(phone)
        store.touch(phone, now)
        await _send(remote_jid, phone, MSG["00_inicio"])
        store.update(phone, stage="awaiting_main_choice")


# ── Helpers de búsqueda y soporte ────────────────────────────────────────────

async def _search_and_present(remote_jid: str, phone: str, form: dict):
    error_code = form.get("error_code", "")
    app_name   = form.get("aplicacion", "")
    index      = load_index()

    # Paso 0 — lookup directo por ID (error_code ya normalizado = PROB-NNN)
    direct = find_by_id(error_code, index)
    if direct:
        expected_producto = PRODUCT_MAP.get(app_name, app_name)
        if direct["producto"].lower() != expected_producto.lower():
            print(f"[KB] WARN: {error_code} es de '{direct['producto']}' "
                  f"pero cliente reportó app '{app_name}'")
        matched_ids = [error_code]
    else:
        print(f"[KB] {error_code} sin match directo — usando pipeline semántica")
        filtered    = filter_by_product(app_name, index)
        candidates  = score_candidates(error_code, filtered, top_n=12)
        matched_ids = await rank_candidates(error_code, app_name, candidates)
        if is_cancelled(phone):
            print(f"[Solvy] {phone} | búsqueda cancelada por reset")
            return

    if not matched_ids:
        await _notify_support_unresolved(phone, form, [])
        await _send(remote_jid, phone,
            f"Gracias por compartir el código *{error_code}*.\n\n"
            "En este momento no encontramos una solución registrada para este código, pero no te preocupés: ya guardamos la información que compartiste para que puedan ayudarte mejor.\n\n"
            "Para continuar con la atención, por favor comunicate con SolvyCall al:\n\n"
            "📞 73188382\n\n"
            "El asesor ya contará con tus datos y el detalle inicial de tu consulta.\n\n"
            "Gracias por comunicarte con Solvy, asistente virtual de BancoSol. ✨"
        )
        store.update(phone, stage="done")
        return

    store.update(phone, solutions_tried=matched_ids, stage="solution_presented")

    response = f"Encontramos información relacionada al código *{error_code}*.\n\nSeguí estos pasos:\n\n"
    for pid in matched_ids:
        title, context = get_client_context(pid)
        client_steps = await adapt_for_client(title, context, app_name, error_code)
        if is_cancelled(phone):
            print(f"[Solvy] {phone} | adaptación cancelada por reset")
            return
        response += f"*{title}*\n\n{client_steps}\n\n"
    response += (
        "─────────────────\n"
        "¿La solución te ayudó?\n\n"
        "1️⃣ Sí, se resolvió\n"
        "2️⃣ No, necesito más ayuda"
    )
    await _send(remote_jid, phone, response)


def _build_support_msg(phone: str, conv: dict, form: dict, solutions_tried: list, reason: str) -> str:
    started_at   = conv.get("started_at", 0)
    contact_time = (
        datetime.fromtimestamp(started_at).strftime("%d/%m/%Y %H:%M")
        if started_at else "N/A"
    )

    if solutions_tried:
        sol_lines = "\n".join(
            f"• {sid}: {get_title(sid)}" for sid in solutions_tried
        )
        sol_block = f"\n*Soluciones intentadas:*\n{sol_lines}"
    else:
        sol_block = "\n*Soluciones intentadas:* Ninguna"

    parts = [
        "🚨 *CASO DERIVADO — SolvyCall BancoSol*",
        f"_Motivo: {reason}_\n",
        "*Datos del cliente:*",
        f"👤 Nombre: {form.get('nombre', 'N/A')}",
        f"🪪 CI: {form.get('ci', 'N/A')}",
        f"📱 App: {form.get('aplicacion', 'N/A')}",
        f"🕐 Contacto inicial: {contact_time}",
        f"🔢 Código de error: {form.get('error_code') or 'N/A'}",
        sol_block,
    ]

    if form.get("descripcion"):
        parts += ["", "*En palabras del cliente:*", form["descripcion"]]

    if form.get("resumen"):
        parts += ["", "*Resumen del problema:*", form["resumen"]]

    return "\n".join(parts)


def _build_backend_payload(phone: str, conv: dict, form: dict) -> dict:
    """Build the AgentReportRequest payload matching the Java DTO."""
    started_at = conv.get("started_at", 0)
    return {
        "cliente": {
            "nombre":     form.get("nombre"),
            "ci":         form.get("ci"),
            "telefono":   phone,
            "aplicacion": form.get("aplicacion"),
        },
        "contacto_inicial": (
            datetime.fromtimestamp(started_at).isoformat() if started_at else datetime.now().isoformat()
        ),
        "codigo_error": form.get("error_code"),
        "descripcion_cliente": (
            form.get("descripcion")
            or f"El cliente reporta el código de error {form.get('error_code', 'desconocido')}."
        ),
        "resumen": form.get("resumen"),
        "historial": conv.get("history", []),
    }


def _build_history_block(phone: str, conv: dict, form: dict) -> str:
    """Serialize the full session as JSON to embed inline in the support message."""
    started_at = conv.get("started_at", 0)
    payload = {
        "cliente": {
            "nombre":    form.get("nombre"),
            "ci":        form.get("ci"),
            "telefono":  phone,
            "aplicacion": form.get("aplicacion"),
        },
        "contacto_inicial": (
            datetime.fromtimestamp(started_at).isoformat() if started_at else None
        ),
        "codigo_error":        form.get("error_code"),
        "descripcion_cliente": form.get("descripcion"),
        "resumen":             form.get("resumen"),
        "historial":           conv.get("history", []),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def _notify_support_unresolved(phone: str, form: dict, solutions_tried: list):
    conv = store.get(phone)
    header  = _build_support_msg(phone, conv, form, solutions_tried, "solución no efectiva")
    history = _build_history_block(phone, conv, form)
    await send_text(SUPPORT_JID, f"{header}\n\n\n📎 Historial JSON:\n{history}")
    await open_case(_build_backend_payload(phone, conv, form))


async def _notify_support_other(phone: str, form: dict):
    conv = store.get(phone)
    header  = _build_support_msg(phone, conv, form, [], "otro problema sin código de error")
    history = _build_history_block(phone, conv, form)
    await send_text(SUPPORT_JID, f"{header}\n\n\n📎 Historial JSON:\n{history}")
    await open_case(_build_backend_payload(phone, conv, form))
