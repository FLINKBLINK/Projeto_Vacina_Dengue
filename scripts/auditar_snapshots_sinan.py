"""Compara snapshots oficiais do SINAN sem corrigir nem excluir registros."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
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
        db.execute("""CREATE TABLE fingerprints (
            ano INTEGER NOT NULL, tipo TEXT NOT NULL, hash TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (ano, tipo, hash)
        )""")
        db.execute("CREATE INDEX idx_fingerprints_hash ON fingerprints(tipo, hash, ano)")
        snapshots = [read_snapshot(db, year, paths[year]) for year in paths]
        summary, details = compare(db, list(paths))
    report = {
        "fonte": "Portal de Dados Abertos do SUS — SINAN/Dengue",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
        "snapshots": snapshots,
        **summary,
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
    print(json.dumps({
        "snapshots": [{"ano": s["ano_snapshot"], "linhas": s["linhas_lidas"], "sha256": s["sha256_zip"]} for s in snapshots],
        "comparacoes": summary["comparacoes"],
        "arquivos": ["comparacao_snapshots_sinan.json", "correspondencias_snapshots_sinan.csv", "comparacao_snapshots.sqlite"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
