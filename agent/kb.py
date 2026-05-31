import os
import re
from pathlib import Path

KB_PATH = Path(os.getenv(
    "OBSIDIAN_KB_PATH",
    r"D:\Obsidian\Claude Code\Banco Prueba\BancoSol_Playbook_Bolivia_CallCenter_AgentReady\Problemas"
))

# Map form aplicacion → KB producto field
PRODUCT_MAP = {
    "AppSol":   "AppSol",
    "Al Toque": "Altoke",
    "SolNet":   "Banca Web",
}

# In-process cache — built once on first call, lives for the process lifetime
_cache: list[dict] | None = None


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> dict:
    m = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ0-9]+', text.lower()))


# ── Public API ────────────────────────────────────────────────────────────────

def load_index() -> list[dict]:
    """Parse all PROB-*.md files once and cache the lightweight index."""
    global _cache
    if _cache is not None:
        return _cache

    index: list[dict] = []
    if not KB_PATH.exists():
        print(f"[KB] WARN: ruta no encontrada: {KB_PATH}")
        _cache = index
        return _cache

    for md_file in sorted(KB_PATH.glob("PROB-*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        fm = _parse_frontmatter(content)

        title_m = re.search(r'^# (.+)$', content, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else md_file.stem

        kw_m = re.search(r'^\*\*Keywords:\*\* (.+)$', content, re.MULTILINE)
        kw_raw = kw_m.group(1).strip() if kw_m else ""

        searchable = f"{title} {kw_raw} {fm.get('categoria', '')} {fm.get('producto', '')}"

        index.append({
            "id":       md_file.stem,
            "title":    title,
            "keywords": kw_raw,
            "tokens":   _tokenize(searchable),
            "producto": fm.get("producto", ""),
            "categoria": fm.get("categoria", ""),
            "severidad": fm.get("severidad", ""),
            "path":     md_file,
        })

    print(f"[KB] Índice cargado: {len(index)} artículos desde {KB_PATH}")
    _cache = index
    return _cache


def find_by_id(prob_id: str, index: list[dict]) -> dict | None:
    """Direct O(1)-ish lookup by exact PROB-NNN id. No scoring, no LLM."""
    return next((a for a in index if a["id"] == prob_id), None)


def filter_by_product(app_name: str, index: list[dict]) -> list[dict]:
    """Pre-filter by producto. Falls back to full index if no match."""
    producto = PRODUCT_MAP.get(app_name, app_name)
    filtered = [a for a in index if a["producto"].lower() == producto.lower()]
    if not filtered:
        print(f"[KB] Sin artículos para producto '{producto}', usando índice completo")
        return index
    return filtered


def score_candidates(query: str, candidates: list[dict], top_n: int = 12) -> list[dict]:
    """
    Word-overlap score against pre-tokenized index.
    Falls back to first top_n if query produces no signal (e.g. opaque error code).
    """
    q_tokens = _tokenize(query)
    scored = sorted(candidates, key=lambda a: len(q_tokens & a["tokens"]), reverse=True)
    top = scored[:top_n]

    # If every candidate scored 0, the query had no keyword overlap (e.g. bare "AB123")
    # → return first top_n from product-filtered list so LLM at least gets a relevant subset
    if all(len(q_tokens & a["tokens"]) == 0 for a in top):
        return candidates[:top_n]

    return top


def get_title(prob_id: str) -> str:
    """Return article title from in-memory cache — no file read."""
    index = load_index()
    article = next((a for a in index if a["id"] == prob_id), None)
    return article["title"] if article else prob_id


def get_client_context(prob_id: str) -> tuple[str, str]:
    """
    Extract the minimal client-relevant context from a playbook article.
    Reads the file once and pulls exactly 3 fields (~60-80 words total):
      - Señal principal   → what is happening
      - Validaciones      → what to check (problem-specific)
      - Resultado esperado → first sentence only (success definition)

    This mini-context is what gets sent to the LLM for client adaptation,
    instead of the full 12-step agent playbook (~500 words).
    """
    index = load_index()
    article = next((a for a in index if a["id"] == prob_id), None)
    if not article:
        return (prob_id, "")

    try:
        content = article["path"].read_text(encoding="utf-8")
    except Exception:
        return (article["title"], "")

    title = article["title"]
    parts: list[str] = []

    signal_m = re.search(r'- Señal principal: (.+)', content)
    if signal_m:
        parts.append(f"Señal: {signal_m.group(1).strip()}")

    val_m = re.search(r'- Validaciones específicas: (.+)', content)
    if val_m:
        parts.append(f"Verificar: {val_m.group(1).strip()}")

    result_m = re.search(r'## Resultado esperado\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
    if result_m:
        first_sentence = result_m.group(1).strip().split('.')[0]
        parts.append(f"Objetivo: {first_sentence}")

    return (title, "\n".join(parts) if parts else title)


# Legacy aliases so test_kb.py and any old callers don't break
def get_solution_steps(prob_id: str) -> tuple[str, str]:
    return get_client_context(prob_id)

def get_solution_text(prob_id: str) -> tuple[str, str]:
    return get_client_context(prob_id)
