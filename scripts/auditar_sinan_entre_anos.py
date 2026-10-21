"""Gera diagnóstico temporal e de possíveis duplicidades entre snapshots SINAN anuais.

O relatório é conservador: sinaliza padrões para revisão, sem excluir ou fundir registros.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


SIGNATURE_FIELDS = (
    "ID_MN_RESI", "DT_NOTIFIC", "DT_SIN_PRI", "CS_SEXO",
    "NU_IDADE_N", "CLASSI_FIN", "CRITERIO",
)
DATE_FIELDS = ("DT_NOTIFIC", "DT_SIN_PRI", "DT_INVEST", "DT_ENCERRA")


def _norm(value):
    return str(value or "").strip()


def auditar(db_path: str, years: tuple[int, ...]) -> dict:
    by_year = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for year in years:
            rows = conn.execute(
                """SELECT chave_registro, ano_referencia, registro_json
                   FROM oficiais_registros
                   WHERE fonte='sinan_dengue' AND ano_referencia=?
                   ORDER BY chave_registro""", (year,)
            ).fetchall()
            if not rows:
                raise ValueError(f"Nenhum registro SINAN encontrado para {year}.")
            by_year[year] = rows

    mismatches = []
    invalid_json = 0
    date_years = Counter()
    signature_index = defaultdict(list)
    year_counts = {}
    for year, rows in by_year.items():
        year_counts[str(year)] = len(rows)
        for row in rows:
            try:
                record = json.loads(row["registro_json"])
                if not isinstance(record, dict):
                    raise ValueError("JSON não é objeto")
            except (ValueError, TypeError, json.JSONDecodeError):
                invalid_json += 1
                continue
            nu_ano = _norm(record.get("NU_ANO"))
            if nu_ano and nu_ano != str(year):
                mismatches.append({
                    "ano_arquivo": year,
                    "chave_registro": row["chave_registro"],
                    "NU_ANO": nu_ano,
                    "DT_NOTIFIC": _norm(record.get("DT_NOTIFIC")),
                })
            for field in DATE_FIELDS:
                value = _norm(record.get(field))
                if len(value) >= 4 and value[:4].isdigit():
                    date_years[f"{field}:{value[:4]}"] += 1
            signature = tuple(_norm(record.get(field)) for field in SIGNATURE_FIELDS)
            if all(signature):
                digest = hashlib.sha256(json.dumps(signature, ensure_ascii=False).encode("utf-8")).hexdigest()
                signature_index[digest].append({
                    "ano_arquivo": year,
                    "chave_registro": row["chave_registro"],
                })

    cross_year_groups = []
    for digest, occurrences in signature_index.items():
        distinct_years = sorted({item["ano_arquivo"] for item in occurrences})
        if len(distinct_years) > 1:
            cross_year_groups.append({
                "assinatura_sha256": digest,
                "anos_arquivo": distinct_years,
                "ocorrencias": occurrences,
            })

    return {
        "fonte": "SINAN/Dengue — diagnóstico temporal entre snapshots anuais",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "anos_arquivo": list(years),
        "registros_por_ano": year_counts,
        "registros_com_NU_ANO_divergente": len(mismatches),
        "exemplos_NU_ANO_divergente": mismatches[:100],
        "contagem_ano_por_campo_data": dict(sorted(date_years.items())),
        "grupos_assinatura_clinica_presentes_em_multiplos_anos": len(cross_year_groups),
        "exemplos_assinaturas_multiano": cross_year_groups[:100],
        "json_invalidos": invalid_json,
        "interpretacao": (
            "Divergências e assinaturas repetidas são alertas para revisão, não prova de erro ou duplicidade de paciente. "
            "NU_ANO, ano do arquivo e datas podem divergir em snapshots oficiais; nenhum registro é removido."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--years", default="2023,2024,2025")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    years = tuple(int(item.strip()) for item in args.years.split(",") if item.strip())
    if not years:
        parser.error("Informe pelo menos um ano.")
    report = auditar(args.db, years)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
