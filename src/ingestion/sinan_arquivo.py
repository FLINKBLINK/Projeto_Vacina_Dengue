"""Leitura em streaming do arquivo anual oficial SINAN/Dengue por residência.

O ZIP nacional é baixado para arquivo temporário e o CSV é lido em streaming.
Somente linhas com ID_MN_RESI pertencente aos municípios-alvo são entregues ao ETL.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable, TextIO, Any

import requests

MUNICIPIOS_RESIDENCIA = {
    "350560": "Barrinha",
    "350780": "Brodowski",
    "351310": "Cravinhos",
    "351885": "Guatapará",
    "352430": "Jardinópolis",
    "354020": "Pontal",
    "354090": "Pradópolis",
    "354340": "Ribeirão Preto",
    "355150": "Serrana",
    "355170": "Sertãozinho",
}
URL_TEMPLATE = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/csv/DENGBR{ano2}.csv.zip"
USER_AGENT = "Projeto-Vacina-Dengue/1.0 (etl-dados-publicos)"


def normalizar_codigo_residencia(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[:6] if len(digits) in (6, 7) else None


def iterar_csv_residencia(stream: TextIO, *, page_size: int = 1000) -> Iterable[list[dict[str, str]]]:
    """Emite lotes apenas de residentes nos municípios-alvo; não acumula o CSV inteiro."""
    if page_size < 1:
        raise ValueError("page_size deve ser >= 1.")
    sample = stream.read(8192)
    stream.seek(0)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(stream, dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV do SINAN sem cabeçalho.")
    columns = {name.strip().upper(): name for name in reader.fieldnames if name}
    residence_col = next((columns[key] for key in ("ID_MN_RESI", "ID_MUN_RES", "CO_MUN_RES") if key in columns), None)
    if residence_col is None:
        raise ValueError("CSV do SINAN sem coluna de município de residência (ID_MN_RESI).")
    batch: list[dict[str, str]] = []
    for row in reader:
        code = normalizar_codigo_residencia(row.get(residence_col))
        if code not in MUNICIPIOS_RESIDENCIA:
            continue
        # Padroniza um campo canônico para que o ETL não use acidentalmente ID_MUNICIP.
        row["id_mn_resi"] = code
        batch.append(row)
        if len(batch) >= page_size:
            yield batch
            batch = []
    if batch:
        yield batch


def iterar_sinan_arquivo(
    ano: int,
    *,
    page_size: int = 1000,
    session: requests.Session | None = None,
    timeout: int = 180,
) -> Iterable[list[dict[str, str]]]:
    """Baixa e processa o ZIP anual oficial; só emite linhas dos municípios-alvo."""
    if not 2000 <= ano <= 2026:
        raise ValueError("Ano fora do intervalo esperado (2000–2026).")
    url = URL_TEMPLATE.format(ano2=str(ano)[-2:])
    client = session or requests
    with tempfile.TemporaryDirectory(prefix="sinan-etl-") as tmp:
        archive = Path(tmp) / "sinan.zip"
        with client.get(
            url, stream=True, timeout=(20, timeout),
            headers={"User-Agent": USER_AGENT, "Accept": "application/zip"},
        ) as response:
            response.raise_for_status()
            with archive.open("wb") as out:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        out.write(chunk)
        with zipfile.ZipFile(archive) as zf:
            members = [info for info in zf.infolist() if not info.is_dir() and info.filename.lower().endswith(".csv")]
            if len(members) != 1:
                raise ValueError(f"Esperava exatamente um CSV no ZIP; encontrei {len(members)}.")
            with zf.open(members[0]) as raw:
                text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
                yield from iterar_csv_residencia(text, page_size=page_size)
