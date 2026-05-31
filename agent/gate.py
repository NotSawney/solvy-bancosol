"""
Per-phone message serialization gate.

Prevents concurrent LLM calls for the same phone and buffers the latest
message that arrives while a call is in progress.

Flow when phone is BUSY:
  - Reset word  → flag cancellation + queue the reset (processed after current task).
  - Normal text → send "please wait" (throttled) + keep latest message queued.

Flow when phone is FREE:
  - Acquire lock, run handler, drain any pending message, release lock.
"""
import asyncio
import time

from evolution_client import send_text

_locks:     dict[str, asyncio.Lock] = {}
_pending:   dict[str, tuple]        = {}   # phone → (jid, text, ts)
_wait_ts:   dict[str, float]        = {}   # phone → time last "please wait" was sent
_cancelled: set[str]                = set()

_WAIT_MSG      = "⏳ Un momento, estoy procesando tu mensaje anterior. Ya te respondo."
_WAIT_COOLDOWN = 10  # seconds between consecutive "please wait" messages


def _get_lock(phone: str) -> asyncio.Lock:
    if phone not in _locks:
        _locks[phone] = asyncio.Lock()
    return _locks[phone]


def is_cancelled(phone: str) -> bool:
    """True if a reset arrived while this task was running its LLM call."""
    return phone in _cancelled


async def dispatch(handle_fn, remote_jid: str, text: str, msg_ts, reset_words: set):
    """
    Gate entry point — called from the webhook background task instead of
    calling handle_fn directly.
    """
    phone = remote_jid.replace("@s.whatsapp.net", "")
    lk    = _get_lock(phone)

    if lk.locked():
        if text.lower().strip() in reset_words:
            # Signal the running task to abort at its next checkpoint
            _cancelled.add(phone)
        else:
            now = time.time()
            if now - _wait_ts.get(phone, 0) >= _WAIT_COOLDOWN:
                await send_text(remote_jid, _WAIT_MSG)
                _wait_ts[phone] = now
        # Keep only the latest message — no unbounded queue
        _pending[phone] = (remote_jid, text, msg_ts)
        return

    async with lk:
        _cancelled.discard(phone)
        try:
            await handle_fn(remote_jid, text, msg_ts)
        except Exception as e:
            print(f"[Gate] ERROR {phone}: {e}")
            _pending.pop(phone, None)
            await send_text(remote_jid,
                "⚠️ Ocurrió un error procesando tu mensaje.\n"
                "Escribí *reiniciar* para comenzar una nueva consulta."
            )
            return

        # After the main task finishes, process whatever arrived while we were busy
        while phone in _pending:
            jid, t, ts = _pending.pop(phone)
            _cancelled.discard(phone)
            try:
                await handle_fn(jid, t, ts)
            except Exception as e:
                print(f"[Gate] ERROR {phone} (pending): {e}")
                _pending.pop(phone, None)
                await send_text(jid,
                    "⚠️ Ocurrió un error procesando tu mensaje.\n"
                    "Escribí *reiniciar* para comenzar una nueva consulta."
                )
                break
