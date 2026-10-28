"""Gera série agregada do SINAN por início dos sintomas sem alterar registros brutos.

A série principal usa DT_SIN_PRI válida. Datas ausentes/inválidas são reportadas
à parte; datas fora do ano nominal do snapshot permanecem no ano da data.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

CONFIRMED = {"10": "dengue", "11": "dengue_com_sinais_de_alarme", "12": "dengue_grave"}
CLASSIFICATION = {
    "5": "descartado",
    "8": "inconclusivo",
    "10": "dengue",
    "11": "dengue_com_sinais_de_alarme",
    "12": "dengue_grave",
    "13": "chikungunya",
    "": "classificacao_ausente",
}


def parse_date(value):
    value = str(value or "").strip()
    if not value:
        return None, "ausente"
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date(), "valida"
        except ValueError:
            pass
    return None, "invalida"


def classification_bucket(value):
    code = str(value or "").strip()
    return CLASSIFICATION.get(code, "classificacao_fora_do_dominio")


def aggregate_records(records):
    """Agrega dicionários com ano_arquivo, municipio e registro SINAN."""
    by_symptom_year = Counter()
    by_municipality_symptom_year = Counter()
    by_notification_year = Counter()
    by_symptom_year_classification = Counter()
    symptom_date_quality = Counter()
    future_to_snapshot = Counter()
    total = 0

    for item in records:
        total += 1
        snapshot_year = int(item["ano_arquivo"])
        record = item["registro"]
        municipality = str(item.get("municipio") or "(vazio)")
        symptoms, quality = parse_date(record.get("DT_SIN_PRI"))
        notification, notification_quality = parse_date(record.get("DT_NOTIFIC"))
        bucket = classification_bucket(record.get("CLASSI_FIN"))
        symptom_date_quality[quality] += 1

        if symptoms is None:
            # Mantém ausentes/inválidas fora da série anual, mas visíveis no relatório.
            by_symptom_year_classification[("data_" + quality, bucket)] += 1
        else:
            year = symptoms.year
            by_symptom_year[year] += 1
            by_municipality_symptom_year[(municipality, year)] += 1
            by_symptom_year_classification[(year, bucket)] += 1
            if year > snapshot_year:
                future_to_snapshot[(snapshot_year, year)] += 1

        if notification is not None:
            by_notification_year[notification.year] += 1

    return {
        "fonte": "SINAN/Dengue — série temporal investigativa por início dos sintomas",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "criterio_serie_principal": "Ano de DT_SIN_PRI quando a data é válida. Datas ausentes/inválidas ficam em categorias separadas. Nenhum registro é corrigido, excluído ou imputado.",
        "criterio_classificacao": "Somente CLASSI_FIN 10, 11 e 12 são agrupados como dengue classificados; códigos 8, vazio, descartado, chikungunya e valores desconhecidos permanecem separados.",
        "total_registros_origem": total,
        "qualidade_data_inicio_sintomas": dict(sorted(symptom_date_quality.items())),
        "registros_por_ano_inicio_sintomas": dict(sorted(by_symptom_year.items())),
        "registros_por_ano_notificacao": dict(sorted(by_notification_year.items())),
        "registros_por_municipio_e_ano_sintomas": [
            {"municipio": municipality, "ano_inicio_sintomas": year, "registros": count}
            for (municipality, year), count in sorted(by_municipality_symptom_year.items())
        ],
        "registros_por_ano_sintomas_e_classificacao": [
            {"ano_inicio_sintomas": year, "classificacao": bucket, "registros": count}
            for (year, bucket), count in sorted(by_symptom_year_classification.items(), key=lambda x: (str(x[0][0]), x[0][1]))
        ],
        "datas_sintomas_posteriores_ao_snapshot": [
            {"ano_arquivo": snapshot, "ano_inicio_sintomas": symptom_year, "registros": count}
            for (snapshot, symptom_year), count in sorted(future_to_snapshot.items())
        ],
        "observacao": "Contagens são notificações/registros, não pessoas únicas. A categoria dengue classificada não deve ser interpretada como total confirmado sem validar o dicionário e as regras oficiais da versão da base.",
    }


def load_records(db_path, years):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """SELECT municipio, ano_referencia, registro_json
               FROM oficiais_registros
               WHERE fonte='sinan_dengue' AND ano_referencia IN ({})
               ORDER BY ano_referencia, municipio, chave_registro""".format(
                ",".join("?" for _ in years)
            ), tuple(years),
        ).fetchall()
    if not rows:
        raise ValueError("Nenhum registro SINAN encontrado para os anos solicitados.")
    records = []
    for municipality, snapshot_year, raw in rows:
        record = json.loads(raw)
        if not isinstance(record, dict):
            raise ValueError("registro_json SINAN não é um objeto.")
        records.append({"municipio": municipality, "ano_arquivo": snapshot_year, "registro": record})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--years", default="2023,2024,2025")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    years = [int(value.strip()) for value in args.years.split(",") if value.strip()]
    if not years:
        parser.error("--years precisa conter ao menos um ano.")
    report = aggregate_records(load_records(args.db, years))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
