"""Gera um inventário JSON dos recursos oficiais encontrados no catálogo."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ao executar "python scripts/inventariar_fontes.py", o Python coloca
# scripts/ no sys.path. Incluímos a raiz do repositório para permitir
# importar o pacote src sem depender de PYTHONPATH configurado no runner.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.fontes_oficiais import gerar_inventario

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
