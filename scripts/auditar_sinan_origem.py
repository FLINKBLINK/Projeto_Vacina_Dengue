"""Reconcilia o SQLite do ETL com uma leitura independente do CSV oficial do SINAN."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/csv/DENGBR{year2}.csv.zip"
MUNICIPIOS = {
    "350560": ("3505601", "Barrinha"),
    "350780": ("3507805", "Brodowski"),
    "351310": ("3513108", "Cravinhos"),
    "351885": ("3518859", "Guatapará"),
    "352430": ("3524303", "Jardinópolis"),
    "354020": ("3540200", "Pontal"),
    "354090": ("3540903", "Pradópolis"),
    "354340": ("3543402", "Ribeirão Preto"),
    "355150": ("3551504", "Serrana"),
    "355170": ("3551702", "Sertãozinho"),
}


def norm_code(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[:6] if len(digits) in (6, 7) else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--zip", dest="zip_path", default=None,
                        help="ZIP oficial já usado pelo ETL, para garantir auditoria do mesmo snapshot.")
    args = parser.parse_args()

    url = URL.format(year2=str(args.year)[-2:])
    if args.zip_path:
        archive_bytes = Path(args.zip_path).read_bytes()
    else:
        request = urllib.request.Request(url, headers={"User-Agent": "Projeto-Vacina-Dengue/1.0 (etl-auditoria)", "Accept": "application/zip"})
        with urllib.request.urlopen(request, timeout=240) as response:
            archive_bytes = response.read()

    zip_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        csv_files = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_files) != 1:
            raise RuntimeError(f"Esperava exatamente um CSV no ZIP oficial; encontrei {len(csv_files)}: {csv_files}")
        raw = archive.read(csv_files[0])

    text = io.TextIOWrapper(io.BytesIO(raw), encoding="latin-1", newline="")
    sample = text.read(8192)
    text.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text, dialect=dialect)
    if not reader.fieldnames:
        raise RuntimeError("CSV oficial sem cabeçalho.")
    fields = {field.strip().upper(): field for field in reader.fieldnames if field}
    residence_col = next((fields[key] for key in ("ID_MN_RESI", "ID_MUN_RES", "CO_MUN_RES") if key in fields), None)
    if residence_col is None:
        raise RuntimeError(f"Coluna de residência não encontrada. Cabeçalho: {reader.fieldnames}")

    total_csv_rows = 0
    expected_by_municipality: Counter[str] = Counter()
    expected_ordinals: set[str] = set()
    for ordinal, row in enumerate(reader, start=1):
        total_csv_rows += 1
        code = norm_code(row.get(residence_col))
        if code in MUNICIPIOS:
            expected_by_municipality[MUNICIPIOS[code][1]] += 1
            expected_ordinals.add(f"{args.year}:linha:{ordinal}")

    with sqlite3.connect(args.db) as conn:
        db_rows = conn.execute(
            """SELECT chave_registro, municipio_ibge, municipio
               FROM oficiais_registros
               WHERE fonte='sinan_dengue' AND ano_referencia=?""",
            (args.year,),
        ).fetchall()

    actual_keys = {row[0] for row in db_rows}
    actual_by_municipality = Counter(row[2] for row in db_rows)
    missing_keys = sorted(expected_ordinals - actual_keys)
    unexpected_keys = sorted(actual_keys - expected_ordinals)
    municipality_report = []
    for prefix, (ibge, name) in MUNICIPIOS.items():
        actual = actual_by_municipality.get(name, 0)
        expected = expected_by_municipality.get(name, 0)
        municipality_report.append({
            "municipio": name,
            "codigo_ibge": ibge,
            "linhas_csv_oficial": expected,
            "linhas_sqlite": actual,
            "diferenca": actual - expected,
            "status": "ok" if actual == expected else "divergencia",
        })

    report = {
        "fonte": "Ministério da Saúde — Portal de Dados Abertos do SUS / SINAN-Dengue",
        "ano": args.year,
        "url": url,
        "arquivo_csv_no_zip": csv_files[0],
        "auditado_em_utc": datetime.now(timezone.utc).isoformat(),
        "sha256_zip_auditado": zip_sha256,
        "bytes_zip": len(archive_bytes),
        "bytes_csv_descompactado": len(raw),
        "total_linhas_csv_sem_cabecalho": total_csv_rows,
        "coluna_residencia": residence_col,
        "linhas_regionais_csv": len(expected_ordinals),
        "linhas_sqlite": len(db_rows),
        "chaves_origem_ausentes_no_sqlite": len(missing_keys),
        "chaves_sqlite_nao_encontradas_no_csv_auditado": len(unexpected_keys),
        "primeiras_chaves_ausentes": missing_keys[:20],
        "primeiras_chaves_nao_encontradas": unexpected_keys[:20],
        "municipios": municipality_report,
        "status": "aprovado" if not missing_keys and not unexpected_keys and all(x["status"] == "ok" for x in municipality_report) else "divergencia",
        "modo_snapshot": "arquivo_compartilhado" if args.zip_path else "download_independente",
        "observacao": "Quando --zip é informado, o ETL e a auditoria devem usar a mesma cópia do ZIP. Sem esse parâmetro, a auditoria baixa uma cópia independente e pode encontrar snapshot diferente.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "aprovado":
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
