"""Auditoria somente leitura do esquema SQLite e das categorias da fonte vacinal.

Exemplo:
    python -m scripts.auditar_modelagem
    python -m scripts.auditar_modelagem --db data/processed/dengue.db \
        --workbook DADOS_EXTRAIDOS.xlsx --saida reports/auditoria_modelagem.md

O script não altera o banco nem a planilha.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PADRAO = ROOT / "data" / "processed" / "dengue.db"
PLANILHA_PADRAO = ROOT / "DADOS_EXTRAIDOS.xlsx"


def auditar_banco(db_path: str | Path) -> dict:
    """Coleta metadados, restrições, índices e possíveis duplicidades sem escrever."""
    caminho = Path(db_path)
    if not caminho.exists():
        raise FileNotFoundError(f"Banco SQLite não encontrado: {caminho}")

    relatorio = {"arquivo": str(caminho), "tabelas": []}
    with sqlite3.connect(f"file:{caminho.resolve()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        nomes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()

        for item in nomes:
            tabela = item["name"]
            colunas = conn.execute(f'PRAGMA table_info("{tabela}")').fetchall()
            indices = conn.execute(f'PRAGMA index_list("{tabela}")').fetchall()
            fks = conn.execute(f'PRAGMA foreign_key_list("{tabela}")').fetchall()
            total = conn.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
            info_colunas = []
            for coluna in colunas:
                nome = coluna["name"]
                nulos = conn.execute(
                    f'SELECT COUNT(*) FROM "{tabela}" WHERE "{nome}" IS NULL'
                ).fetchone()[0]
                info_colunas.append({
                    "nome": nome,
                    "tipo": coluna["type"],
                    "not_null": bool(coluna["notnull"]),
                    "primary_key": bool(coluna["pk"]),
                    "nulos": nulos,
                })
            info_indices = []
            for indice in indices:
                detalhe = conn.execute(
                    f'PRAGMA index_info("{indice["name"]}")'
                ).fetchall()
                info_indices.append({
                    "nome": indice["name"],
                    "unico": bool(indice["unique"]),
                    "colunas": [linha["name"] for linha in detalhe],
                })
            relatorio["tabelas"].append({
                "nome": tabela,
                "linhas": total,
                "colunas": info_colunas,
                "indices": info_indices,
                "chaves_estrangeiras": [
                    {"coluna": fk["from"], "tabela_referenciada": fk["table"],
                     "coluna_referenciada": fk["to"]}
                    for fk in fks
                ],
            })
    return relatorio


def auditar_planilha(caminho: str | Path) -> dict:
    """Inspeciona nomes de abas, cabeçalhos e rótulos compostos; não altera a fonte."""
    arquivo = Path(caminho)
    if not arquivo.exists():
        raise FileNotFoundError(f"Planilha de vacinação não encontrada: {arquivo}")
    excel = pd.ExcelFile(arquivo)
    resultado = {"arquivo": str(arquivo), "abas": []}
    for aba in excel.sheet_names:
        cabecalhos = pd.read_excel(excel, sheet_name=aba, nrows=0).columns.tolist()
        compostos = [
            str(valor) for valor in cabecalhos
            if any(separador in str(valor) for separador in (" - ", " – ", " — ", ";", "|"))
        ]
        resultado["abas"].append({
            "nome": aba,
            "cabecalhos": [str(c) for c in cabecalhos],
            "rotulos_com_separadores": compostos,
        })
    return resultado


def _markdown(banco: dict, planilha: dict | None) -> str:
    linhas = [
        "# Auditoria preliminar da modelagem SQLite",
        "",
        "> Relatório somente leitura. Nenhum dado foi alterado.",
        "",
        f"Banco: `{banco['arquivo']}`",
        "",
        "## Esquema atual",
        "",
    ]
    for tabela in banco["tabelas"]:
        linhas += [f"### {tabela['nome']} — {tabela['linhas']} linhas", "",
                   "| Coluna | Tipo | PK | NOT NULL | Nulos |",
                   "|---|---|---:|---:|---:|"]
        for coluna in tabela["colunas"]:
            linhas.append(
                f"| {coluna['nome']} | {coluna['tipo'] or 'não declarado'} | "
                f"{'sim' if coluna['primary_key'] else 'não'} | "
                f"{'sim' if coluna['not_null'] else 'não'} | {coluna['nulos']} |"
            )
        linhas += ["", "**Índices:**"]
        if tabela["indices"]:
            for indice in tabela["indices"]:
                linhas.append(
                    f"- `{indice['nome']}` ({', '.join(indice['colunas'])}); "
                    f"único: {'sim' if indice['unico'] else 'não'}"
                )
        else:
            linhas.append("- Nenhum índice declarado.")
        linhas += ["", "**Chaves estrangeiras:**"]
        if tabela["chaves_estrangeiras"]:
            for fk in tabela["chaves_estrangeiras"]:
                linhas.append(
                    f"- {fk['coluna']} → {fk['tabela_referenciada']}.{fk['coluna_referenciada']}"
                )
        else:
            linhas.append("- Nenhuma declarada.")
        linhas.append("")
    if planilha:
        linhas += ["## Fonte de vacinação", "", f"Planilha: `{planilha['arquivo']}`", ""]
        for aba in planilha["abas"]:
            linhas += [f"### Aba {aba['nome']}", "",
                       "Cabeçalhos: " + (", ".join(f"`{c}`" for c in aba["cabecalhos"]) or "nenhum"),
                       ""]
            if aba["rotulos_com_separadores"]:
                linhas.append(
                    "Rótulos com separadores (investigar significado; não são prova de violação da 1FN): "
                    + ", ".join(f"`{c}`" for c in aba["rotulos_com_separadores"])
                )
                linhas.append("")
    linhas += [
        "## Observações metodológicas",
        "",
        "- Um rótulo com hífen não prova, isoladamente, violação da 1FN; é necessário conhecer sua semântica.",
        "- A ausência de chave estrangeira ou restrição UNIQUE é um ponto de investigação, não prova automática de dados incorretos.",
        "- A normalização será proposta somente após validar a granularidade e as dependências funcionais.",
        "- Este relatório não executa migração, exclusão, atualização ou inserção.",
        "",
    ]
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PADRAO)
    parser.add_argument("--workbook", type=Path, default=PLANILHA_PADRAO)
    parser.add_argument("--sem-planilha", action="store_true")
    parser.add_argument("--saida", type=Path)
    args = parser.parse_args()

    banco = auditar_banco(args.db)
    planilha = None if args.sem_planilha else auditar_planilha(args.workbook)
    conteudo = _markdown(banco, planilha)
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(conteudo, encoding="utf-8")
        print(f"Relatório salvo em: {args.saida}")
    else:
        print(conteudo)


if __name__ == "__main__":
    main()
