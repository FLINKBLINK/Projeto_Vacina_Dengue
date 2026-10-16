"""Comando de linha de comando para criar/atualizar o banco SQLite."""
from __future__ import annotations

import json

from src.database.carga import recriar_banco
from src.database.conexao import DB_PATH


def main() -> None:
    contagens = recriar_banco()
    print(f"Banco SQLite criado em: {DB_PATH}")
    print("Registros importados por tabela:")
    print(json.dumps(contagens, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
