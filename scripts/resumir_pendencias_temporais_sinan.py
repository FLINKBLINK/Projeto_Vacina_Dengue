"""Classifica alertas temporais do relatório semântico SINAN sem modificar os dados."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

TEMPORAL_TYPES = {
    "NU_ANO_diferente_arquivo",
    "ano_notificacao_diferente_arquivo",
    "ano_sintomas_diferente_arquivo",
}
FIELDS = [
    "tipo_pendencia", "ano_arquivo", "chave_registro", "municipio", "municipio_ibge",
    "NU_ANO", "DT_NOTIFIC", "DT_SIN_PRI", "DT_INVEST", "DT_ENCERRA", "SEM_PRI",
    "categoria_temporal", "ano_data_avaliada", "data_avaliada", "criterio_classificacao",
]


def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return date.fromisoformat(value) if fmt == "%Y-%m-%d" else date.strptime(value, fmt)
        except (ValueError, TypeError, AttributeError):
            continue
    return None


def classify(row: dict) -> dict | None:
    kind = row.get("tipo_pendencia", "")
    if kind not in TEMPORAL_TYPES:
        return None
    snapshot_year = int(row["ano_arquivo"])
    date_field = {
        "NU_ANO_diferente_arquivo": "DT_NOTIFIC",
        "ano_notificacao_diferente_arquivo": "DT_NOTIFIC",
        "ano_sintomas_diferente_arquivo": "DT_SIN_PRI",
    }[kind]
    parsed = parse_date(row.get(date_field, ""))
    if kind == "NU_ANO_diferente_arquivo":
        try:
            field_year = int(row.get("NU_ANO", ""))
        except (TypeError, ValueError):
            field_year = None
        if field_year == snapshot_year:
            return None
    else:
        field_year = parsed.year if parsed else None

    category = "revisao_manual"
    rationale = "A divergência não se enquadra na janela heurística de virada do ano."
    if field_year is not None and field_year < snapshot_year and parsed and parsed.month == 12 and parsed.day >= 25:
        category = "transicao_fim_ano_anterior"
        rationale = "Data entre 25 e 31 de dezembro do ano anterior ao snapshot; plausível transição de ano, requer validação da definição temporal."
    elif field_year is not None and field_year > snapshot_year and parsed and parsed.month == 1 and parsed.day <= 7:
        category = "transicao_inicio_ano_seguinte"
        rationale = "Data entre 1 e 7 de janeiro após o ano do snapshot; plausível transição de ano, requer validação."
    elif field_year is not None and field_year > snapshot_year:
        category = "ano_posterior_ao_snapshot"
        rationale = "O ano da data/campo é posterior ao ano nominal do arquivo; verificar período coberto e atualização do arquivo de origem."
    elif field_year is not None and field_year < snapshot_year:
        category = "ano_anterior_fora_da_janela_de_virada"
        rationale = "A data/campo pertence a ano anterior e não está na janela heurística de fim de ano."
    return {
        **row,
        "categoria_temporal": category,
        "ano_data_avaliada": field_year if field_year is not None else "",
        "data_avaliada": parsed.isoformat() if parsed else "",
        "criterio_classificacao": rationale,
    }


def build_report(input_csv: str) -> tuple[dict, list[dict]]:
    classified = []
    with open(input_csv, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            result = classify(row)
            if result:
                classified.append(result)

    by_category = Counter(row["categoria_temporal"] for row in classified)
    by_year_category = Counter((row["ano_arquivo"], row["categoria_temporal"]) for row in classified)
    by_municipality = Counter((row["ano_arquivo"], row["categoria_temporal"], row["municipio"]) for row in classified)
    summary = {
        "fonte": "SINAN/Dengue — classificação investigativa de pendências temporais",
        "regra": "Heurística de triagem, não correção nem decisão epidemiológica. Janela de virada definida provisoriamente como 25–31/dezembro e 1–7/janeiro.",
        "ocorrencias_temporais_classificadas": len(classified),
        "observacao": "As ocorrências não equivalem necessariamente a registros únicos: um registro pode gerar alertas para mais de um campo. Nenhum dado original é alterado.",
        "por_categoria": dict(sorted(by_category.items())),
        "por_ano_arquivo_e_categoria": [
            {"ano_arquivo": year, "categoria_temporal": category, "ocorrencias": count}
            for (year, category), count in sorted(by_year_category.items())
        ],
        "por_municipio": [
            {"ano_arquivo": year, "categoria_temporal": category, "municipio": municipality, "ocorrencias": count}
            for (year, category, municipality), count in sorted(by_municipality.items())
        ],
    }
    return summary, classified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True, help="CSV produzido por auditar_pendencias_sinan")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    summary, rows = build_report(args.input_csv)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "classificacao_temporal_sinan.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = FIELDS
    with (output / "classificacao_temporal_sinan.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
