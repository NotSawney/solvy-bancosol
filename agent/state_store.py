import json
from pathlib import Path

STATE_FILE = Path(__file__).parent / "conversation_state.json"

_DEFAULT_CONV = lambda: {
    "stage": "initial",
    "started_at": 0,
    "last_seen_at": 0,
    "form": {
        "nombre":     None,
        "ci":         None,
        "aplicacion": None,
        "error_code": None,
        "descripcion": None,
        "resumen":    None,
    },
    "solutions_tried": [],
    "history": [],
}


def _load() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get(phone: str) -> dict:
    state = _load()
    if phone not in state:
        state[phone] = _DEFAULT_CONV()
        _save(state)
    return state[phone]


def update(phone: str, **kwargs):
    state = _load()
    if phone not in state:
        state[phone] = _DEFAULT_CONV()
    state[phone].update(kwargs)
    _save(state)


def touch(phone: str, timestamp: int):
    """Update last_seen_at; also set started_at on first touch after a reset."""
    state = _load()
    if phone not in state:
        state[phone] = _DEFAULT_CONV()
    conv = state[phone]
    conv["last_seen_at"] = timestamp
    if not conv.get("started_at"):
        conv["started_at"] = timestamp
    _save(state)


def append_history(phone: str, role: str, text: str, ts: int):
    """Append one turn to the conversation history. Safe for old state files."""
    state = _load()
    if phone not in state:
        state[phone] = _DEFAULT_CONV()
    conv = state[phone]
    if "history" not in conv:
        conv["history"] = []
    conv["history"].append({"role": role, "text": text, "ts": ts})
    _save(state)


def reset(phone: str):
    state = _load()
    state[phone] = _DEFAULT_CONV()
    _save(state)
