"""Exporta pendências semânticas do SINAN para revisão, sem alterar os registros.

Gera um resumo agregado e um CSV de ocorrências com chaves de origem e campos
mínimos para investigação. Não identifica pacientes nem remove registros.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

DATE_RULES = (
    ("inicio_sintomas_apos_notificacao", "DT_SIN_PRI", "DT_NOTIFIC", "greater"),
    ("investigacao_antes_notificacao", "DT_INVEST", "DT_NOTIFIC", "less"),
    ("encerramento_antes_investigacao", "DT_ENCERRA", "DT_INVEST", "less"),
    ("encerramento_antes_notificacao", "DT_ENCERRA", "DT_NOTIFIC", "less"),
    ("obito_antes_inicio_sintomas", "DT_OBITO", "DT_SIN_PRI", "less"),
)

CSV_FIELDS = [
    "tipo_pendencia", "ano_arquivo", "chave_registro", "municipio", "municipio_ibge",
    "NU_ANO", "DT_NOTIFIC", "DT_SIN_PRI", "DT_INVEST", "DT_ENCERRA",
    "CLASSI_FIN", "EVOLUCAO", "CRITERIO", "CS_SEXO", "NU_IDADE_N", "SEM_PRI",
    "detalhe",
]


def norm(value) -> str:
    return str(value or "").strip()


def parse_date(value):
    value = norm(value)
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _fingerprint(record: dict) -> str:
    clinical = {
        k: v for k, v in record.items()
        if k not in {"_sinan_linha_fonte", "id_mn_resi"}
    }
    payload = json.dumps(clinical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def audit_pending(db_path: str, years: tuple[int, ...]) -> tuple[dict, list[dict]]:
    pending: list[dict] = []
    summary = {
        "fonte": "SINAN/Dengue — detalhamento de pendências semânticas",
        "gerado_em_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "anos_arquivo": list(years),
        "registros_por_ano": {},
        "classificacao_por_ano": {},
        "evolucao_por_ano": {},
        "pendencias_por_tipo": {},
        "grupos_conteudo_clinico_repetido_por_ano": {},
        "observacao": (
            "Relatório investigativo. Os alertas não provam erro ou duplicidade de paciente. "
            "Nenhum registro é corrigido, excluído ou fundido automaticamente."
        ),
    }

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for year in years:
            rows = conn.execute(
                """SELECT chave_registro, municipio_ibge, municipio, ano_referencia, registro_json
                   FROM oficiais_registros
                   WHERE fonte='sinan_dengue' AND ano_referencia=?
                   ORDER BY chave_registro""", (year,)
            ).fetchall()
            if not rows:
                raise ValueError(f"Nenhum registro SINAN encontrado para {year}.")
            summary["registros_por_ano"][str(year)] = len(rows)
            class_counts = Counter()
            evolution_counts = Counter()
            fingerprints = defaultdict(list)

            for row in rows:
                try:
                    record = json.loads(row["registro_json"])
                    if not isinstance(record, dict):
                        raise ValueError("JSON não é objeto")
                except (TypeError, ValueError, json.JSONDecodeError):
                    pending.append({
                        "tipo_pendencia": "json_invalido", "ano_arquivo": year,
                        "chave_registro": row["chave_registro"], "municipio": row["municipio"],
                        "municipio_ibge": row["municipio_ibge"], "detalhe": "registro_json inválido",
                    })
                    continue

                class_code = norm(record.get("CLASSI_FIN")) or "(vazio)"
                evolution_code = norm(record.get("EVOLUCAO")) or "(vazio)"
                class_counts[class_code] += 1
                evolution_counts[evolution_code] += 1
                common = {
                    "ano_arquivo": year,
                    "chave_registro": row["chave_registro"],
                    "municipio": row["municipio"],
                    "municipio_ibge": row["municipio_ibge"],
                    "NU_ANO": norm(record.get("NU_ANO")),
                    "DT_NOTIFIC": norm(record.get("DT_NOTIFIC")),
                    "DT_SIN_PRI": norm(record.get("DT_SIN_PRI")),
                    "DT_INVEST": norm(record.get("DT_INVEST")),
                    "DT_ENCERRA": norm(record.get("DT_ENCERRA")),
                    "CLASSI_FIN": class_code,
                    "EVOLUCAO": evolution_code,
                    "CRITERIO": norm(record.get("CRITERIO")),
                    "CS_SEXO": norm(record.get("CS_SEXO")),
                    "NU_IDADE_N": norm(record.get("NU_IDADE_N")),
                    "SEM_PRI": norm(record.get("SEM_PRI")),
                }

                if not norm(record.get("CLASSI_FIN")):
                    pending.append({**common, "tipo_pendencia": "classificacao_final_vazia",
                                    "detalhe": "CLASSI_FIN ausente; não inferir classificação"})
                elif class_code == "8":
                    pending.append({**common, "tipo_pendencia": "classificacao_inconclusiva",
                                    "detalhe": "CLASSI_FIN=8; inconclusivo, não contar como dengue confirmada"})

                if not norm(record.get("EVOLUCAO")):
                    pending.append({**common, "tipo_pendencia": "evolucao_vazia",
                                    "detalhe": "EVOLUCAO ausente; desfecho não informado"})

                notification = parse_date(record.get("DT_NOTIFIC"))
                symptoms = parse_date(record.get("DT_SIN_PRI"))
                if norm(record.get("NU_ANO")).isdigit() and int(norm(record.get("NU_ANO"))) != year:
                    pending.append({**common, "tipo_pendencia": "NU_ANO_diferente_arquivo",
                                    "detalhe": f"NU_ANO={norm(record.get('NU_ANO'))}; ano do snapshot={year}"})
                if notification and notification.year != year:
                    pending.append({**common, "tipo_pendencia": "ano_notificacao_diferente_arquivo",
                                    "detalhe": f"DT_NOTIFIC pertence a {notification.year}; snapshot={year}"})
                if symptoms and symptoms.year != year:
                    pending.append({**common, "tipo_pendencia": "ano_sintomas_diferente_arquivo",
                                    "detalhe": f"DT_SIN_PRI pertence a {symptoms.year}; snapshot={year}"})

                parsed = {field: parse_date(record.get(field)) for field in
                          ("DT_NOTIFIC", "DT_SIN_PRI", "DT_INVEST", "DT_ENCERRA", "DT_OBITO")}
                for label, left_field, right_field, relation in DATE_RULES:
                    left, right = parsed[left_field], parsed[right_field]
                    if left is None or right is None:
                        continue
                    violated = left > right if relation == "greater" else left < right
                    if violated:
                        pending.append({**common, "tipo_pendencia": label,
                                        "detalhe": f"{left_field}={left.isoformat()} versus {right_field}={right.isoformat()}"})

                fingerprints[_fingerprint(record)].append(common)

            summary["classificacao_por_ano"][str(year)] = dict(sorted(class_counts.items()))
            summary["evolucao_por_ano"][str(year)] = dict(sorted(evolution_counts.items()))
            duplicate_groups = [group for group in fingerprints.values() if len(group) > 1]
            summary["grupos_conteudo_clinico_repetido_por_ano"][str(year)] = len(duplicate_groups)
            for group in duplicate_groups:
                digest = _fingerprint({k: v for k, v in json.loads("{}").items()})
                # The rows share the same complete clinical payload; only output the source key and review fields.
                for item in group:
                    pending.append({**item, "tipo_pendencia": "conteudo_clinico_repetido",
                                    "detalhe": f"grupo com {len(group)} linhas; comparar antes de qualquer deduplicação"})

    counts = Counter(row.get("tipo_pendencia", "desconhecida") for row in pending)
    summary["pendencias_por_tipo"] = dict(sorted(counts.items()))
    summary["total_linhas_pendencia"] = len(pending)
    return summary, pending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--years", default="2023,2024,2025")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    years = tuple(int(part.strip()) for part in args.years.split(",") if part.strip())
    if not years:
        parser.error("Informe pelo menos um ano.")
    summary, pending = audit_pending(args.db, years)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pendencias_semanticas_sinan.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (out_dir / "pendencias_semanticas_sinan.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(pending)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
