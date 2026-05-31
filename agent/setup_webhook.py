"""
Run once to:
  1. Create the Evolution instance 'banco-prueba'
  2. Configure the webhook to point to this agent
  3. Print QR connection instructions
"""
import os
import sys
import httpx
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

EVOLUTION_URL = os.getenv("EVOLUTION_URL", "http://localhost:8080")
API_KEY = os.getenv("EVOLUTION_API_KEY", "change-me-before-production")
INSTANCE = os.getenv("EVOLUTION_INSTANCE", "banco-prueba")
AGENT_PORT = os.getenv("AGENT_PORT", "3000")
WEBHOOK_URL = f"http://host.docker.internal:{AGENT_PORT}/webhook"

HEADERS = {"apikey": API_KEY, "Content-Type": "application/json"}


def setup():
    print(f"\n{'='*50}")
    print("  Banco Prueba — Configuración de Agente Virtual")
    print(f"{'='*50}\n")

    # 1. Create instance
    print(f"[1/2] Creando instancia '{INSTANCE}'...")
    r = httpx.post(
        f"{EVOLUTION_URL}/instance/create",
        json={"instanceName": INSTANCE, "qrcode": True, "integration": "WHATSAPP-BAILEYS"},
        headers=HEADERS,
        timeout=15,
    )
    if r.status_code in (200, 201):
        print(f"      OK Instancia '{INSTANCE}' creada.")
    elif r.status_code in (403, 409) and "already in use" in r.text:
        print(f"      -- Instancia '{INSTANCE}' ya existe, continuando...")
    else:
        print(f"      ERROR: {r.status_code} — {r.text}")
        return

    # 2. Configure webhook
    print(f"[2/2] Configurando webhook → {WEBHOOK_URL} ...")
    r = httpx.post(
        f"{EVOLUTION_URL}/webhook/set/{INSTANCE}",
        json={
            "webhook": {
                "enabled": True,
                "url": WEBHOOK_URL,
                "webhookByEvents": False,
                "webhookBase64": False,
                "events": ["MESSAGES_UPSERT"],
            }
        },
        headers=HEADERS,
        timeout=15,
    )
    if r.status_code in (200, 201):
        print(f"      OK Webhook configurado.")
    else:
        print(f"      ERROR configurando webhook: {r.status_code} — {r.text}")
        return

    print(f"\n{'='*50}")
    print("  PRÓXIMOS PASOS")
    print(f"{'='*50}")
    print(f"\n  1. Conecta el número de WhatsApp del bot escaneando el QR:")
    print(f"     GET http://localhost:8080/instance/connect/{INSTANCE}")
    print(f"     Header: apikey: {API_KEY}")
    print(f"\n     O ábrelo directo en el browser (ya tiene el header por defecto):")
    print(f"     http://localhost:8080/manager  → instancia '{INSTANCE}' → Connect")
    print(f"\n  2. Inicia el agente:")
    print(f"     cd D:\\evolution-solvy\\agent")
    print(f"     python main.py")
    print(f"\n  3. El agente escucha mensajes en http://localhost:{AGENT_PORT}/webhook")
    print(f"     Solo responde al número: {os.getenv('ALLOWED_NUMBER', '???')}")
    print()


if __name__ == "__main__":
    setup()
