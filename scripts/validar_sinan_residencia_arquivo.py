"""Valida a distribuição SINAN por residência usando o arquivo oficial anual.

O arquivo nacional é processado localmente em streaming; nenhuma linha individual
é impressa, persistida no repositório ou enviada como artefato. Só sai um resumo.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import TextIO

import requests

MUNICIPIOS = {
    "350560": "Barrinha",
    "350780": "Brodowski",
    "351310": "Cravinhos",
    "351880": "Guatapará",
    "352430": "Jardinópolis",
    "354020": "Pontal",
    "354090": "Pradópolis",
    "354340": "Ribeirão Preto",
    "355150": "Serrana",
    "355170": "Sertãozinho",
}
URL_TEMPLATE = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/csv/DENGBR{ano2}.csv.zip"


def normalizar_codigo(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) in (6, 7):
        return digits[:6]
    return None


def analisar_csv(stream: TextIO) -> dict:
    sample = stream.read(8192)
    stream.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(stream, dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV sem cabeçalho.")
    by_upper = {name.strip().upper(): name for name in reader.fieldnames if name}
    residence_col = next((by_upper[k] for k in ("ID_MN_RESI", "ID_MUN_RES", "CO_MUN_RES") if k in by_upper), None)
    notifier_col = next((by_upper[k] for k in ("ID_MUNIC", "ID_MUN_NOT", "CO_MUN_NOT") if k in by_upper), None)
    if not residence_col:
        raise ValueError("Não encontrei coluna de município de residência (ex.: ID_MN_RESI). Cabeçalhos: " + ", ".join(reader.fieldnames[:40]))
    if not notifier_col:
        raise ValueError("Não encontrei coluna de município notificador (ex.: ID_MUNIC). Cabeçalhos: " + ", ".join(reader.fieldnames[:40]))

    residence = Counter()
    notifier = Counter()
    cross = Counter()
    hashes = set()
    rows = 0
    missing_residence = 0
    duplicates = 0
    for row in reader:
        if not row or all(v in (None, "") for v in row.values()):
            continue
        rows += 1
        signature = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).digest()
        if signature in hashes:
            duplicates += 1
        else:
            hashes.add(signature)
        res_code = normalizar_codigo(row.get(residence_col))
        not_code = normalizar_codigo(row.get(notifier_col))
        if res_code is None:
            missing_residence += 1
        elif res_code in MUNICIPIOS:
            residence[res_code] += 1
        if not_code in MUNICIPIOS:
            notifier[not_code] += 1
        if not_code in MUNICIPIOS and res_code in MUNICIPIOS:
            cross[(not_code, res_code)] += 1

    return {
        "registros_lidos_arquivo": rows,
        "registros_distintos_por_hash_exato": len(hashes),
        "linhas_repetidas_por_hash_exato": duplicates,
        "registros_sem_codigo_residencia": missing_residence,
        "por_municipio_residencia": {name: residence[code] for code, name in MUNICIPIOS.items()},
        "por_municipio_notificador": {name: notifier[code] for code, name in MUNICIPIOS.items()},
        "cruzamento_notificador_residencia_alvo": [
            {"notificador": MUNICIPIOS[n], "residencia": MUNICIPIOS[r], "registros": count}
            for (n, r), count in sorted(cross.items())
        ],
    }


def executar(ano: int, timeout: int = 180) -> dict:
    if not 2000 <= ano <= 2026:
        raise ValueError("Ano fora do intervalo esperado (2000–2026).")
    url = URL_TEMPLATE.format(ano2=str(ano)[-2:])
    digest = hashlib.sha256()
    with tempfile.TemporaryDirectory(prefix="sinan-validacao-") as tmp:
        archive = Path(tmp) / "sinan.zip"
        with requests.get(url, stream=True, timeout=(20, timeout), headers={"User-Agent": "Projeto-Vacina-Dengue/1.0", "Accept": "application/zip"}) as response:
            response.raise_for_status()
            with archive.open("wb") as out:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        digest.update(chunk)
                        out.write(chunk)
        with zipfile.ZipFile(archive) as zf:
            members = [info for info in zf.infolist() if not info.is_dir() and info.filename.lower().endswith(".csv")]
            if len(members) != 1:
                raise ValueError(f"Esperava exatamente um CSV no ZIP; encontrei {len(members)}.")
            with zf.open(members[0]) as raw:
                # Microdados do SINAN podem usar codificação Windows-1252/Latin-1.
                text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
                summary = analisar_csv(text)
    return {
        "fonte": "Portal de Dados Abertos do SUS — SINAN/Dengue",
        "ano": ano,
        "url_arquivo": url,
        "sha256_arquivo_zip": digest.hexdigest(),
        "arquivo_processado": members[0].filename,
        "metodo": "Arquivo anual nacional CSV/ZIP; contagem local por ID_MN_RESI e comparação por ID_MUNIC.",
        "dados_pessoais": "Nenhuma linha individual é impressa ou persistida; só agregados e hash do arquivo.",
        **summary,
        "alertas": [
            "Contagens são registros/notificações, não automaticamente casos confirmados.",
            "Hash exato identifica linhas integralmente idênticas; não é identificador epidemiológico de duplicidade.",
            "Arquivo anual pode divergir de painéis atualizados; guardar a data/hash da extração para reprodutibilidade.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=2024)
    args = parser.parse_args()
    print(json.dumps(executar(args.ano), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
