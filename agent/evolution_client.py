import os
import httpx

EVOLUTION_URL = os.getenv("EVOLUTION_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "change-me-before-production")
INSTANCE = os.getenv("EVOLUTION_INSTANCE", "banco-prueba")

HEADERS = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}


async def send_text(to_jid: str, text: str):
    """Send a WhatsApp text message. to_jid can be bare number or JID."""
    number = to_jid.replace("@s.whatsapp.net", "").replace("@g.us", "")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{EVOLUTION_URL}/message/sendText/{INSTANCE}",
            json={"number": number, "text": text},
            headers=HEADERS,
        )
        r.raise_for_status()
        return r.json()
