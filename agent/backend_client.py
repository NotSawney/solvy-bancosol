import os
import httpx

BASE_URL = os.getenv("BASE_URL", "").rstrip("/")


async def open_case(payload: dict) -> None:
    """POST escalation payload to the main system. Silent — never raises."""
    if not BASE_URL:
        print("[Backend] BASE_URL no configurada, saltando notificación al sistema principal.")
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{BASE_URL}/api/cases/open", json=payload)
            r.raise_for_status()
            print(f"[Backend] Caso abierto OK: {r.status_code}")
    except Exception as e:
        print(f"[Backend] ERROR al abrir caso: {e}")
