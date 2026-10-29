"""Audita comparabilidade temporal e duplicidade exata em snapshots SINAN/Dengue.

O relatório contém somente contagens agregadas. Não exporta nem registra linhas individuais.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

MUNICIPIOS = {
    "350560": "Barrinha", "350780": "Brodowski", "351310": "Cravinhos",
    "351885": "Guatapará", "352430": "Jardinópolis", "354020": "Pontal",
    "354090": "Pradópolis", "354340": "Ribeirão Preto", "355150": "Serrana",
    "355170": "Sertãozinho",
}


def municipio(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[:6] if len(digits) in (6, 7) else None


def year_date(value):
    raw = str(value or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return raw[:4]
    if len(raw) == 8 and raw.isdigit():
        return raw[:4]
    if len(raw) == 10 and raw[2] == "/" and raw[5] == "/" and raw[-4:].isdigit():
        return raw[-4:]
    return "ausente_ou_invalida"


def analyze_csv(stream):
    sample = stream.read(8192)
    stream.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(stream, dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV sem cabeçalho")
    headers = [str(x or "").strip() for x in reader.fieldnames]
    cols = {x.upper(): x for x in headers if x}
    year_col = cols.get("NU_ANO")
    notify_col = cols.get("DT_NOTIFIC")
    symptom_col = cols.get("DT_SIN_PRI")
    class_col = cols.get("CLASSI_FIN")
    residence_col = cols.get("ID_MN_RESI")
    ndup_col = cols.get("NDUPLIC_N")

    totals = Counter()
    by_nu_ano = Counter()
    by_notify_year = Counter()
    by_symptom_year = Counter()
    by_class = Counter()
    by_year_class = Counter()
    by_municipality_year = Counter()
    ndup_distribution = Counter()
    # Disk-backed set prevents keeping millions of hashes in RAM.
    with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp:
        db = sqlite3.connect(tmp.name)
        db.execute("CREATE TABLE seen (digest TEXT PRIMARY KEY)")
        duplicate_exact_rows = 0
        for row in reader:
            if not row or all(v in (None, "") for v in row.values()):
                continue
            totals["linhas"] += 1
            nu = str(row.get(year_col) or "").strip() if year_col else "(coluna ausente)"
            notify_year = year_date(row.get(notify_col)) if notify_col else "coluna_ausente"
            symptom_year = year_date(row.get(symptom_col)) if symptom_col else "coluna_ausente"
            klass = str(row.get(class_col) or "").strip() if class_col else "(coluna ausente)"
            klass = klass if klass else "(vazio)"
            by_nu_ano[nu or "(vazio)"] += 1
            by_notify_year[notify_year] += 1
            by_symptom_year[symptom_year] += 1
            by_class[klass] += 1
            by_year_class[(nu or "(vazio)", klass)] += 1
            ndup = str(row.get(ndup_col) or "").strip() if ndup_col else ""
            if ndup_col:
                ndup_distribution[ndup or "(vazio)"] += 1
            code = municipio(row.get(residence_col)) if residence_col else None
            if code in MUNICIPIOS:
                by_municipality_year[(MUNICIPIOS[code], symptom_year)] += 1

            # Hash all source fields in header order; exact duplicate rows only.
            canonical = "\x1f".join(str(row.get(h) or "").strip() for h in headers)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            cur = db.execute("INSERT OR IGNORE INTO seen(digest) VALUES (?)", (digest,))
            if cur.rowcount == 0:
                duplicate_exact_rows += 1
            if totals["linhas"] % 50000 == 0:
                db.commit()
        db.commit()
        distinct_hashes = db.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
        db.close()

    return {
        "linhas": totals["linhas"],
        "hashes_de_linhas_exatas_distintas": distinct_hashes,
        "linhas_repetidas_por_hash_exato": duplicate_exact_rows,
        "distribuicao_NU_ANO": dict(sorted(by_nu_ano.items())),
        "distribuicao_ano_DT_NOTIFIC": dict(sorted(by_notify_year.items())),
        "distribuicao_ano_DT_SIN_PRI": dict(sorted(by_symptom_year.items())),
        "distribuicao_CLASSI_FIN": dict(sorted(by_class.items())),
        "distribuicao_NU_ANO_e_CLASSI_FIN": [
            {"NU_ANO": y, "CLASSI_FIN": c, "registros": n}
            for (y, c), n in sorted(by_year_class.items())
        ],
        "distribuicao_NDUPLIC_N": dict(sorted(ndup_distribution.items())),
        "municipios_alvo_por_ano_inicio_sintomas": [
            {"municipio": m, "ano_inicio_sintomas": y, "registros": n}
            for (m, y), n in sorted(by_municipality_year.items())
        ],
        "observacao": (
            "Hash idêntico significa linha idêntica em todas as colunas exportadas; "
            "não detecta duplicidade clínica entre linhas diferentes nem prova duplicidade de pessoas. "
            "NDUPLIC_N é reportado como código bruto, sem inferir seu significado."
        ),
    }


def analyze_archive(year, path):
    with zipfile.ZipFile(path) as archive:
        members = [x for x in archive.infolist() if not x.is_dir() and x.filename.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"{year}: esperado exatamente um CSV, encontrados {len(members)}")
        with archive.open(members[0]) as raw:
            report = analyze_csv(io.TextIOWrapper(raw, encoding="latin-1", newline=""))
    return {"ano_snapshot": year, "arquivo_zip": path.name, **report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arquivo", action="append", required=True, metavar="ANO=CAMINHO_ZIP")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    files = {}
    for item in args.arquivo:
        y, sep, p = item.partition("=")
        if not sep or not y.isdigit() or not Path(p).is_file():
            parser.error(f"Formato/caminho inválido: {item!r}")
        if int(y) in files:
            parser.error(f"Ano repetido: {y}")
        files[int(y)] = Path(p)
    report = {
        "titulo": "Validação de comparabilidade temporal e duplicidade exata SINAN/Dengue",
        "metodo": "Agregações por ano/código e hash SHA-256 das linhas completas, com índice temporário em disco.",
        "snapshots": {str(y): analyze_archive(y, p) for y, p in sorted(files.items())},
        "limites": [
            "Contagens são registros/notificações, não pessoas únicas.",
            "Duplicidade exata de linha não equivale a duplicidade clínica.",
            "Diferenças entre anos precisam ser interpretadas com o dicionário e o histórico de publicação oficiais.",
        ],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "relatorio": str(output),
        "resumo": {y: {k: v for k, v in data.items() if k in ("linhas", "hashes_de_linhas_exatas_distintas", "linhas_repetidas_por_hash_exato")} for y, data in report["snapshots"].items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
