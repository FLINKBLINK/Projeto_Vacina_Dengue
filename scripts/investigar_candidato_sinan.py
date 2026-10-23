"""Compara um alvo do snapshot SINAN 2025 com candidatos no snapshot 2026.

Exporta hashes e indicadores de igualdade por campo, nunca valores clínicos brutos.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scripts.auditar_snapshots_sinan import (
    digest_fields, iter_snapshot_records, norm, signature_hash, with_month_keys,
)

TARGET_FIELDS = (
    "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N",
    "DT_NOTIFIC", "DT_SIN_PRI", "SEM_PRI", "CLASSI_FIN", "CRITERIO", "EVOLUCAO",
)
LAYERS = {
    "meses_sexo_idade_classificacao_desfecho": (
        "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N",
        "DT_NOTIFIC_ANO_MES", "DT_SIN_PRI_ANO_MES",
        "CLASSI_FIN", "CRITERIO", "EVOLUCAO",
    ),
    "meses_sexo_idade_classificacao": (
        "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N",
        "DT_NOTIFIC_ANO_MES", "DT_SIN_PRI_ANO_MES", "CLASSI_FIN", "CRITERIO",
    ),
    "meses_sexo_idade": (
        "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N",
        "DT_NOTIFIC_ANO_MES", "DT_SIN_PRI_ANO_MES",
    ),
}


def row_hash(record: dict[str, str]) -> str:
    fields = tuple(sorted(k for k in record if not k.endswith("_ANO_MES")))
    return digest_fields(record, fields)


def compare_target(path_2025: Path, path_2026: Path, target_prefix: str) -> tuple[dict, list[dict]]:
    targets = []
    for _, record in iter_snapshot_records(path_2025):
        enriched = with_month_keys(record)
        if row_hash(enriched).startswith(target_prefix):
            targets.append(enriched)
    if len(targets) != 1:
        raise ValueError(
            f"O prefixo deve identificar exatamente um alvo; encontrados: {len(targets)}"
        )
    target = targets[0]
    target_hash = row_hash(target)
    candidate_records = []
    for _, record in iter_snapshot_records(path_2026):
        enriched = with_month_keys(record)
        candidate_records.append(enriched)

    output = {}
    for layer, fields in LAYERS.items():
        target_signature = signature_hash(target, fields)
        if target_signature is None:
            output[layer] = []
            continue
        matches = []
        for candidate in candidate_records:
            if signature_hash(candidate, fields) == target_signature:
                candidate_hash = row_hash(candidate)
                matches.append((candidate_hash, candidate))
        output[layer] = matches

    detail_by_key = {}
    for layer, matches in output.items():
        for candidate_hash, candidate in matches:
            key = (layer, candidate_hash)
            row = {
                "hash_alvo_2025": target_hash,
                "hash_candidato_2026": candidate_hash,
                "camada_correspondencia": layer,
                "codigo_municipio_residencia": norm(target.get("ID_MN_RESI", "")),
            }
            for field in TARGET_FIELDS:
                row[f"{field}_igual"] = norm(target.get(field, "")) == norm(candidate.get(field, ""))
            detail_by_key[key] = row

    summary = {
        "alvo_hash": target_hash,
        "prefixo_solicitado": target_prefix,
        "codigo_municipio_residencia": norm(target.get("ID_MN_RESI", "")),
        "candidatos_por_camada": {
            layer: {
                "quantidade": len(matches),
                "hashes_candidatos": sorted({candidate_hash for candidate_hash, _ in matches}),
                "observacao": "Candidato por assinatura; não comprova identidade nem duplicidade.",
            }
            for layer, matches in output.items()
        },
        "campos_comparados": list(TARGET_FIELDS),
        "privacidade": "Sem exportação de valores clínicos brutos; apenas hashes e indicadores de igualdade.",
    }
    return summary, list(detail_by_key.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip-2025", required=True, type=Path)
    parser.add_argument("--zip-2026", required=True, type=Path)
    parser.add_argument("--target-hash-prefix", default="09ec2b5ba6c8")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary, details = compare_target(args.zip_2025, args.zip_2026, args.target_hash_prefix)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "investigacao_candidato_local.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = list(details[0]) if details else [
        "hash_alvo_2025", "hash_candidato_2026", "camada_correspondencia",
        "codigo_municipio_residencia",
        *[f"{field}_igual" for field in TARGET_FIELDS],
    ]
    with (args.output_dir / "investigacao_candidato_local.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(details)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
