"""Auditoria semântica e de qualidade dos registros SINAN já carregados no SQLite.

Alertas semânticos são reportados, não corrigidos nem descartados automaticamente.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

MUNICIPIOS = {
    "350560": ("3505601", "Barrinha"), "350780": ("3507805", "Brodowski"),
    "351310": ("3513108", "Cravinhos"), "351885": ("3518859", "Guatapará"),
    "352430": ("3524303", "Jardinópolis"), "354020": ("3540200", "Pontal"),
    "354090": ("3540903", "Pradópolis"), "354340": ("3543402", "Ribeirão Preto"),
    "355150": ("3551504", "Serrana"), "355170": ("3551702", "Sertãozinho"),
}
DATE_FIELDS = (
    "DT_NOTIFIC", "DT_SIN_PRI", "DT_INVEST", "DT_ENCERRA", "DT_OBITO",
    "DT_DIGITA", "DT_ALRM", "DT_INTERNA", "DT_NS1", "DT_PCR", "DT_SORO",
    "DT_PRNT", "DT_VIRAL",
)
KEY_FIELDS = ("ID_AGRAVO", "ID_MN_RESI", "NU_ANO", "DT_NOTIFIC", "DT_SIN_PRI",
              "CS_SEXO", "NU_IDADE_N", "CLASSI_FIN", "EVOLUCAO")
DATE_ORDER_RULES = (
    ("inicio_sintomas_apos_notificacao", "DT_SIN_PRI", "DT_NOTIFIC", "greater"),
    ("investigacao_antes_notificacao", "DT_INVEST", "DT_NOTIFIC", "less"),
    ("encerramento_antes_investigacao", "DT_ENCERRA", "DT_INVEST", "less"),
    ("encerramento_antes_notificacao", "DT_ENCERRA", "DT_NOTIFIC", "less"),
    ("obito_antes_notificacao", "DT_OBITO", "DT_NOTIFIC", "less"),
)

def _value(value):
    return str(value or "").strip()

def _parse_date(value):
    value = _value(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return "INVALID"

def audit(db_path: str, year: int) -> dict:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT chave_registro, municipio_ibge, municipio, ano_referencia, registro_json
               FROM oficiais_registros
               WHERE fonte='sinan_dengue' AND ano_referencia=?
               ORDER BY chave_registro""", (year,)
        ).fetchall()
    if not rows:
        raise ValueError(f"Nenhum registro SINAN encontrado para {year}.")

    category_fields = ("ID_AGRAVO", "CLASSI_FIN", "EVOLUCAO", "CS_SEXO",
                       "CRITERIO", "NU_ANO", "SEM_PRI", "TP_NOT", "EVOLUCAO")
    categories = {field: Counter() for field in category_fields}
    missing_required = Counter()
    date_invalid = Counter()
    chronology = Counter()
    chronology_examples = {}
    issue_counts = Counter()
    issue_examples = {}
    municipality_counts = Counter()
    unknown_municipalities = Counter()
    code_mismatch_examples = []
    years_notification = Counter()
    years_symptom = Counter()
    invalid_weeks = []
    invalid_week_count = 0
    duplicate_fingerprints = Counter()
    invalid_json = 0
    municipality_code_mismatch = 0

    for row in rows:
        try:
            record = json.loads(row["registro_json"])
            if not isinstance(record, dict):
                raise ValueError("registro_json não é objeto")
        except (ValueError, TypeError, json.JSONDecodeError):
            invalid_json += 1
            continue

        key = row["chave_registro"]
        for field in KEY_FIELDS:
            value = _value(record.get(field))
            if not value:
                missing_required[field] += 1
        for field in category_fields:
            categories[field][_value(record.get(field)) or "(vazio)"] += 1

        if _value(record.get("ID_AGRAVO")) != "A90":
            issue_counts["agravo_diferente_A90"] += 1
        code = re.sub(r"\D", "", _value(record.get("ID_MN_RESI")))[:6]
        municipality_counts[row["municipio"] or "(vazio)"] += 1
        if code not in MUNICIPIOS:
            unknown_municipalities[code or "(vazio)"] += 1
        elif row["municipio"] != MUNICIPIOS[code][1]:
            municipality_code_mismatch += 1
            if len(code_mismatch_examples) < 10:
                code_mismatch_examples.append({
                    "chave": key, "codigo_residencia": code,
                    "municipio_sqlite": row["municipio"],
                    "municipio_esperado": MUNICIPIOS[code][1],
                })

        parsed_dates = {}
        for field in DATE_FIELDS:
            raw = _value(record.get(field))
            parsed = _parse_date(raw)
            parsed_dates[field] = parsed
            if raw and parsed == "INVALID":
                date_invalid[field] += 1
                exkey = "data_invalida_" + field
                if len(issue_examples.get(exkey, [])) < 5:
                    issue_examples.setdefault(exkey, []).append({"chave": key, "valor": raw})

        notification = parsed_dates.get("DT_NOTIFIC")
        symptoms = parsed_dates.get("DT_SIN_PRI")
        if isinstance(notification, date):
            years_notification[notification.year] += 1
            if notification.year != year:
                issue_counts["ano_notificacao_diferente_arquivo"] += 1
        if isinstance(symptoms, date):
            years_symptom[symptoms.year] += 1
            if symptoms.year != year:
                issue_counts["ano_inicio_sintomas_diferente_arquivo"] += 1
        raw_year = _value(record.get("NU_ANO"))
        if raw_year.isdigit() and int(raw_year) != year:
            issue_counts["nu_ano_diferente_arquivo"] += 1
            if len(issue_examples.get("nu_ano_diferente_arquivo", [])) < 10:
                issue_examples.setdefault("nu_ano_diferente_arquivo", []).append(
                    {"chave": key, "NU_ANO": raw_year, "DT_NOTIFIC": record.get("DT_NOTIFIC")}
                )

        for label, left_field, right_field, relation in DATE_ORDER_RULES:
            left, right = parsed_dates.get(left_field), parsed_dates.get(right_field)
            if not isinstance(left, date) or not isinstance(right, date):
                continue
            violated = left > right if relation == "greater" else left < right
            if violated:
                chronology[label] += 1
                if len(chronology_examples.get(label, [])) < 10:
                    chronology_examples.setdefault(label, []).append({
                        "chave": key, left_field: record.get(left_field),
                        right_field: record.get(right_field),
                    })

        week = _value(record.get("SEM_PRI"))
        if week and (not re.fullmatch(r"\d{6}", week) or not 1 <= int(week[-2:]) <= 53):
            invalid_week_count += 1
            if len(invalid_weeks) < 20:
                invalid_weeks.append({"chave": key, "SEM_PRI": week})

        # Identifica conteúdo clínico repetido sem apagar linhas legítimas.
        clinical = {k: v for k, v in record.items()
                    if k not in {"_sinan_linha_fonte", "id_mn_resi"}}
        fingerprint = json.dumps(clinical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        duplicate_fingerprints[fingerprint] += 1

    duplicate_group_sizes = [n for n in duplicate_fingerprints.values() if n > 1]
    integrity_errors = invalid_json + issue_counts["agravo_diferente_A90"] + municipality_code_mismatch + sum(unknown_municipalities.values())
    has_alerts = bool(date_invalid or chronology or missing_required or invalid_weeks
                      or duplicate_group_sizes or issue_counts or invalid_json)
    report = {
        "fonte": "SINAN/Dengue — validação semântica dos registros SQLite",
        "ano_arquivo": year,
        "auditado_em_utc": datetime.now(timezone.utc).isoformat(),
        "registros_analisados": len(rows),
        "status_integridade": "aprovado" if integrity_errors == 0 else "falha",
        "status_semantico": "revisar_pendencias" if has_alerts else "sem_alertas",
        "contagens": {
            "por_municipio": dict(sorted(municipality_counts.items())),
            "ano_notificacao": dict(sorted(years_notification.items())),
            "ano_inicio_sintomas": dict(sorted(years_symptom.items())),
            "campos_categoricos": {k: dict(sorted(v.items())) for k, v in categories.items()},
            "campos_chave_vazios": dict(missing_required),
            "datas_invalidas_por_campo": dict(date_invalid),
            "inconsistencias_cronologicas": dict(chronology),
            "semanas_epidemiologicas_invalidas": invalid_week_count,
            "grupos_de_conteudo_clinico_duplicado": len(duplicate_group_sizes),
            "linhas_nesses_grupos_duplicados": sum(duplicate_group_sizes),
            "municipio_codigo_divergente": municipality_code_mismatch,
            "municipios_desconhecidos": dict(unknown_municipalities),
            "alertas_ano_e_dominio": dict(issue_counts),
            "json_invalidos": invalid_json,
        },
        "amostras": {
            "inconsistencias_cronologicas": chronology_examples,
            "datas_invalidas": {k: v for k, v in issue_examples.items() if k.startswith("data_invalida_")},
            "NU_ANO_diferente_arquivo": issue_examples.get("nu_ano_diferente_arquivo", []),
            "municipio_codigo_divergente": code_mismatch_examples,
            "semanas_invalidas": invalid_weeks,
        },
        "observacao": (
            "Integridade estrutural e qualidade semântica são avaliadas separadamente. "
            "Alertas não significam automaticamente erro do ETL: revisar dicionário oficial, "
            "regras de notificação e possíveis atualizações retrospectivas. Linhas com conteúdo "
            "clínico repetido são sinalizadas, nunca removidas automaticamente."
        ),
    }
    return report

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(args.db, args.year)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status_integridade"] != "aprovado":
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
