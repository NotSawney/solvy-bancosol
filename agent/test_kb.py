"""
Prueba aislada del lookup de Obsidian + Owl Alpha.
No requiere Evolution API ni WhatsApp.

Uso:
    python test_kb.py
    python test_kb.py "mi tarjeta no funciona"
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from kb import load_index, get_solution_text
from llm_client import find_best_problems


async def run(description: str):
    print(f"\nProblema: {description!r}\n")

    index = load_index()
    if not index:
        print(f"ERROR: No se encontraron artículos en KB.")
        print(f"       Ruta actual: {os.getenv('OBSIDIAN_KB_PATH')}")
        return

    print(f"KB cargada: {len(index)} artículos")
    matched_ids = await find_best_problems(description, index)

    if not matched_ids:
        print("Sin coincidencias — el caso se escalaría a soporte.")
        return

    for prob_id in matched_ids:
        title, steps = get_solution_text(prob_id)
        print(f"\n{'─'*50}")
        print(f"[{prob_id}] {title}")
        print(f"{'─'*50}")
        print(steps)


if __name__ == "__main__":
    description = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Describe el problema: ").strip()
    asyncio.run(run(description))
