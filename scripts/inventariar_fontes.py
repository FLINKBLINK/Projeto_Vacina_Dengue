"""Gera um inventário JSON dos recursos oficiais encontrados no catálogo."""
from __future__ import annotations

import json
from pathlib import Path

from src.ingestion.fontes_oficiais import gerar_inventario

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "artifacts" / "fontes_oficiais.json"


def main() -> None:
    inventario = gerar_inventario()
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(inventario, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    total = sum(
        len(conjuntos)
        for conjuntos in inventario["consultas"].values()
    )
    print(f"Inventário salvo em {DESTINO}; {total} conjuntos catalogados.")


if __name__ == "__main__":
    main()
