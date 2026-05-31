import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, BackgroundTasks, Request
import uvicorn
from agent import handle_message, RESET_WORDS
from gate import dispatch

app = FastAPI(title="Banco Prueba - Agente Virtual")


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
        event = payload.get("event", "")

        if event.lower().replace("_", ".") != "messages.upsert":
            return {"status": "ignored"}

        data = payload.get("data", {})
        key  = data.get("key", {})

        if key.get("fromMe"):
            return {"status": "ignored_own"}

        remote_jid: str = key.get("remoteJid", "")
        if "@s.whatsapp.net" not in remote_jid:
            return {"status": "ignored_group_or_broadcast"}

        message_obj = data.get("message", {})
        text = (
            message_obj.get("conversation")
            or message_obj.get("extendedTextMessage", {}).get("text")
            or ""
        ).strip()

        # Evolution sends messageTimestamp as Unix seconds
        msg_ts = int(data.get("messageTimestamp") or 0) or None

        if text:
            background_tasks.add_task(
                dispatch, handle_message, remote_jid, text, msg_ts, RESET_WORDS
            )

        return {"status": "ok"}

    except Exception as e:
        print(f"[Webhook Error] {e}")
        return {"status": "error", "detail": str(e)}


@app.get("/health")
async def health():
    return {"status": "running", "agent": "Banco Prueba - Agente Virtual"}


if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "3000"))
    print(f"Agente virtual iniciando en http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
