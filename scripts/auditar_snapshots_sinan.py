"""Compara snapshots oficiais do SINAN sem corrigir nem excluir registros."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
from collections import Counter
import zipfile
from datetime import datetime, timezone
from pathlib import Path

CLINICAL_FIELDS = (
    "ID_AGRAVO", "ID_MN_RESI", "DT_NOTIFIC", "DT_SIN_PRI", "CS_SEXO",
    "NU_IDADE_N", "SEM_PRI", "CLASSI_FIN", "CRITERIO", "EVOLUCAO",
)


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_fields(record: dict[str, str], fields: tuple[str, ...] | list[str]) -> str:
    payload = json.dumps(
        [(field, norm(record.get(field, ""))) for field in fields],
        ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def find_csv(zf: zipfile.ZipFile) -> str:
    candidates = [name for name in zf.namelist() if name.lower().endswith(".csv")]
    if len(candidates) != 1:
        raise ValueError(f"Esperado exatamente um CSV no ZIP; encontrados: {candidates[:5]}")
    return candidates[0]


def read_snapshot(db: sqlite3.Connection, year: int, path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        member = find_csv(zf)
        with zf.open(member) as raw:
            stream = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
            sample = stream.read(65536)
            stream.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(stream, dialect=dialect)
            if not reader.fieldnames:
                raise ValueError(f"CSV sem cabeçalho no snapshot {year}")
            fields = [norm(name) for name in reader.fieldnames]
            if not {"ID_MN_RESI", "DT_NOTIFIC"}.issubset(set(fields)):
                raise ValueError(
                    f"Layout inesperado em {year}; colunas de residência/notificação ausentes. "
                    f"Exemplo: {fields[:20]}"
                )
            strict_fields = tuple(sorted(fields))
            count = 0
            batch = []
            for record in reader:
                normalized = {norm(key): norm(value) for key, value in record.items() if key is not None}
                batch.append((year, "estrita", digest_fields(normalized, strict_fields)))
                batch.append((year, "clinica", digest_fields(normalized, CLINICAL_FIELDS)))
                count += 1
                if len(batch) >= 10000:
                    db.executemany(
                        "INSERT INTO fingerprints(ano, tipo, hash) VALUES (?, ?, ?) "
                        "ON CONFLICT(ano, tipo, hash) DO UPDATE SET quantidade=quantidade+1",
                        batch,
                    )
                    batch.clear()
            if batch:
                db.executemany(
                    "INSERT INTO fingerprints(ano, tipo, hash) VALUES (?, ?, ?) "
                    "ON CONFLICT(ano, tipo, hash) DO UPDATE SET quantidade=quantidade+1",
                    batch,
                )
    db.commit()
    return {
        "ano_snapshot": year,
        "arquivo": path.name,
        "sha256_zip": sha256_file(path),
        "csv_interno": member,
        "colunas": fields,
        "linhas_lidas": count,
        "campos_assinatura_clinica": list(CLINICAL_FIELDS),
    }


def compare(db: sqlite3.Connection, years: list[int]) -> tuple[dict, list[dict]]:
    comparisons = []
    detail = []
    for i, left in enumerate(years):
        for right in years[i + 1:]:
            for kind, label in (("estrita", "correspondencia_exata"), ("clinica", "assinatura_clinica")):
                rows = db.execute(
                    """SELECT a.hash, a.quantidade, b.quantidade
                       FROM fingerprints AS a
                       JOIN fingerprints AS b ON a.hash = b.hash
                       WHERE a.tipo = ? AND b.tipo = ? AND a.ano = ? AND b.ano = ?""",
                    (kind, kind, left, right),
                ).fetchall()
                matches = len(rows)
                occurrences = sum(min(a, b) for _, a, b in rows)
                comparisons.append({
                    "ano_a": left, "ano_b": right, "tipo_comparacao": label,
                    "hashes_compartilhados": matches,
                    "ocorrencias_correspondentes_minimas": occurrences,
                    "observacao": "Correspondência técnica para investigação; não prova duplicidade de pessoa nem erro.",
                })
                for hash_value, qty_a, qty_b in rows:
                    detail.append({
                        "ano_a": left, "ano_b": right, "tipo_comparacao": label,
                        "hash_sha256": hash_value, "quantidade_ano_a": qty_a,
                        "quantidade_ano_b": qty_b, "ocorrencias_correspondentes": min(qty_a, qty_b),
                    })
    return {"comparacoes": comparisons}, detail



def iter_snapshot_records(path: Path):
    """Itera registros normalizados sem persistir os dados clínicos brutos."""
    with zipfile.ZipFile(path) as zf:
        member = find_csv(zf)
        with zf.open(member) as raw:
            stream = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
            sample = stream.read(65536)
            stream.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(stream, dialect=dialect)
            if not reader.fieldnames:
                raise ValueError(f"CSV sem cabeçalho: {path.name}")
            fields = [norm(name) for name in reader.fieldnames]
            for record in reader:
                yield fields, {norm(key): norm(value) for key, value in record.items() if key is not None}


def years_in(value: str) -> set[str]:
    return set(re.findall(r"20\d{2}", value or ""))


def year_month(value: str) -> str:
    """Normaliza datas comuns do SINAN para AAAA-MM, sem inferir dia ou data ausente."""
    value = norm(value)
    match = re.search(r"(20\d{2})[-/.]?(\d{2})", value)
    if match:
        month = int(match.group(2))
        if 1 <= month <= 12:
            return f"{match.group(1)}-{month:02d}"
    match = re.search(r"\d{2}[-/.](\d{2})[-/.](20\d{2})", value)
    if match:
        month = int(match.group(1))
        if 1 <= month <= 12:
            return f"{match.group(2)}-{month:02d}"
    return ""


def with_month_keys(record: dict[str, str]) -> dict[str, str]:
    enriched = dict(record)
    enriched["DT_SIN_PRI_ANO_MES"] = year_month(record.get("DT_SIN_PRI", ""))
    enriched["DT_NOTIFIC_ANO_MES"] = year_month(record.get("DT_NOTIFIC", ""))
    return enriched


def signature_hash(record: dict[str, str], fields: tuple[str, ...]) -> str | None:
    """Retorna hash somente quando todos os campos discriminantes estão preenchidos."""
    if any(not norm(record.get(field, "")) for field in fields):
        return None
    return digest_fields(record, fields)


def audit_2025_targets_against_2026(path_2025: Path, path_2026: Path) -> tuple[dict, list[dict]]:
    """Compara alvos 2025 contra 2026 com camadas exatas e exploratórias; não identifica pessoas."""
    target_rows = []
    fields_2025 = []
    for fields, record in iter_snapshot_records(path_2025):
        fields_2025 = fields
        if ("2026" in record.get("NU_ANO", "")
                or "2026" in years_in(record.get("DT_NOTIFIC", ""))
                or "2026" in years_in(record.get("DT_SIN_PRI", ""))):
            target_rows.append(with_month_keys(record))

    levels = {
        "residencia_notificacao_sintomas_sexo_idade": (
            "ID_AGRAVO", "ID_MN_RESI", "DT_NOTIFIC", "DT_SIN_PRI", "CS_SEXO", "NU_IDADE_N"
        ),
        "residencia_sintomas_sexo_idade": (
            "ID_AGRAVO", "ID_MN_RESI", "DT_SIN_PRI", "CS_SEXO", "NU_IDADE_N"
        ),
        "residencia_sintomas_sexo": (
            "ID_AGRAVO", "ID_MN_RESI", "DT_SIN_PRI", "CS_SEXO"
        ),
        "residencia_sintomas": ("ID_AGRAVO", "ID_MN_RESI", "DT_SIN_PRI"),
        "residencia_sexo_idade": ("ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N"),
        "residencia_sintomas_ano_mes": ("ID_AGRAVO", "ID_MN_RESI", "DT_SIN_PRI_ANO_MES"),
        "residencia_notificacao_ano_mes": ("ID_AGRAVO", "ID_MN_RESI", "DT_NOTIFIC_ANO_MES"),
        "residencia_sexo_idade_sintomas_ano_mes": (
            "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N", "DT_SIN_PRI_ANO_MES"
        ),
        "residencia_sexo_idade_notificacao_ano_mes": (
            "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N", "DT_NOTIFIC_ANO_MES"
        ),
        "residencia_sexo_idade_notificacao_sintomas_ano_mes": (
            "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N",
            "DT_NOTIFIC_ANO_MES", "DT_SIN_PRI_ANO_MES"
        ),
        "residencia_sexo_idade_datas_semana": (
            "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N",
            "DT_NOTIFIC_ANO_MES", "DT_SIN_PRI_ANO_MES", "SEM_PRI"
        ),
        "residencia_sexo_idade_datas_classificacao": (
            "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N",
            "DT_NOTIFIC_ANO_MES", "DT_SIN_PRI_ANO_MES", "CLASSI_FIN", "CRITERIO"
        ),
        "residencia_sexo_idade_datas_classificacao_desfecho": (
            "ID_AGRAVO", "ID_MN_RESI", "CS_SEXO", "NU_IDADE_N",
            "DT_NOTIFIC_ANO_MES", "DT_SIN_PRI_ANO_MES",
            "CLASSI_FIN", "CRITERIO", "EVOLUCAO"
        ),
    }
    indexes = {name: Counter() for name in levels}
    fields_2026 = []
    rows_2026 = 0
    for fields, record in iter_snapshot_records(path_2026):
        fields_2026 = fields
        rows_2026 += 1
        enriched = with_month_keys(record)
        for name, key_fields in levels.items():
            key = signature_hash(enriched, key_fields)
            if key is not None:
                indexes[name][key] += 1

    detail = []
    for record in target_rows:
        target_id = digest_fields(record, tuple(sorted(k for k in record if not k.endswith("_ANO_MES"))))
        row = {
            "registro_2025_hash": target_id,
            "municipio_residencia_ibge": record.get("ID_MN_RESI", ""),
            "nu_ano": record.get("NU_ANO", ""),
            "ano_dt_notific": ",".join(sorted(years_in(record.get("DT_NOTIFIC", "")))),
            "ano_dt_sin_pri": ",".join(sorted(years_in(record.get("DT_SIN_PRI", "")))),
        }
        for name, key_fields in levels.items():
            key = signature_hash(record, key_fields)
            row[name + "_matches_2026"] = indexes[name][key] if key is not None else 0
        detail.append(row)

    layers = {}
    for name, key_fields in levels.items():
        matching_counts = [
            indexes[name][key] if (key := signature_hash(record, key_fields)) is not None else 0
            for record in target_rows
        ]
        layers[name] = {
            "campos": list(key_fields),
            "registros_alvo_com_alguma_correspondencia": sum(count > 0 for count in matching_counts),
            "ocorrencias_candidatas_somadas": sum(matching_counts),
            "alvos_com_mais_de_uma_correspondencia": sum(count > 1 for count in matching_counts),
            "observacao": (
                "Camada exploratória; coincidência parcial pode ser casual e não comprova "
                "identidade, duplicidade ou erro."
            ),
        }

    summary = {
        "criterio_alvo_2025": "NU_ANO contém 2026 ou DT_NOTIFIC/DT_SIN_PRI contém ano 2026",
        "registros_alvo_2025": len(target_rows),
        "registros_lidos_snapshot_2026": rows_2026,
        "colunas_snapshot_2025": fields_2025,
        "colunas_snapshot_2026": fields_2026,
        "camadas_de_correspondencia": layers,
        "limite": (
            "O relatório exporta hashes, código municipal e contagens de candidatos; "
            "não exporta campos clínicos brutos nem declara correspondência como identidade."
        ),
    }
    return summary, detail

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip-2024", required=True, type=Path)
    parser.add_argument("--zip-2025", required=True, type=Path)
    parser.add_argument("--zip-2026", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    paths = {2024: args.zip_2024, 2025: args.zip_2025, 2026: args.zip_2026}
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    db_path = output / "comparacao_snapshots.sqlite"
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA journal_mode=OFF")
        db.execute("PRAGMA synchronous=OFF")
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("""CREATE TABLE fingerprints (
            ano INTEGER NOT NULL, tipo TEXT NOT NULL, hash TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (ano, tipo, hash)
        )""")
        db.execute("CREATE INDEX idx_fingerprints_hash ON fingerprints(tipo, hash, ano)")
        snapshots = [read_snapshot(db, year, paths[year]) for year in paths]
        summary, details = compare(db, list(paths))
    target_summary, target_details = audit_2025_targets_against_2026(paths[2025], paths[2026])
    report = {
        "fonte": "Portal de Dados Abertos do SUS — SINAN/Dengue",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "snapshots": snapshots,
        **summary,
        "alvos_2025_contra_snapshot_2026": target_summary,
        "limites": [
            "A correspondência exata compara todos os campos normalizados presentes no CSV.",
            "A assinatura clínica usa campos selecionados e pode gerar coincidências não exclusivas.",
            "Uma coincidência não comprova identidade de paciente, duplicidade ou erro de classificação.",
            "Nenhum registro foi corrigido, removido, fundido ou reatribuído a outro ano.",
            "A comparação depende dos arquivos e hashes registrados neste relatório.",
        ],
    }
    (output / "comparacao_snapshots_sinan.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output / "correspondencias_snapshots_sinan.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["ano_a", "ano_b", "tipo_comparacao", "hash_sha256",
                  "quantidade_ano_a", "quantidade_ano_b", "ocorrencias_correspondentes"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(details)
    target_csv = output / "alvos_2025_contra_2026.csv"
    with target_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        fields = list(target_details[0].keys()) if target_details else [
            "registro_2025_hash", "municipio_residencia_ibge", "nu_ano", "ano_dt_notific", "ano_dt_sin_pri"
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(target_details)
    print(json.dumps({
        "snapshots": [{"ano": s["ano_snapshot"], "linhas": s["linhas_lidas"], "sha256": s["sha256_zip"]} for s in snapshots],
        "comparacoes": summary["comparacoes"],
        "arquivos": ["comparacao_snapshots_sinan.json", "correspondencias_snapshots_sinan.csv", "alvos_2025_contra_2026.csv", "comparacao_snapshots.sqlite"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
