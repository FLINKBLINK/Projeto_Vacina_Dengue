"""Compara estrutura e distribuições agregadas dos snapshots nacionais SINAN/Dengue.

Processa CSVs dentro dos ZIPs em streaming. Não grava nem imprime linhas individuais;
o relatório contém apenas metadados, contagens agregadas e hashes dos arquivos.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import TextIO

URL_TEMPLATE = (
    "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/"
    "SINAN/Dengue/csv/DENGBR{ano2}.csv.zip"
)
MUNICIPIOS = {
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


def _codigo_municipio(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[:6] if len(digits) in (6, 7) else None


def _ano_data(value: object) -> str:
    raw = str(value or "").strip()
    if len(raw) >= 4 and raw[:4].isdigit():
        return raw[:4]
    if len(raw) == 8 and raw.isdigit():
        return raw[-4:]
    if len(raw) == 10 and raw[2] == "/" and raw[5] == "/" and raw[-4:].isdigit():
        return raw[-4:]
    return "ausente_ou_formato_nao_reconhecido"


def _achar_coluna(columns: dict[str, str], *names: str) -> str | None:
    return next((columns[name] for name in names if name in columns), None)


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

    original_headers = [str(name or "").strip() for name in reader.fieldnames]
    normalized = {name.upper(): name for name in original_headers if name}
    residence_col = _achar_coluna(
        normalized, "ID_MN_RESI", "ID_MUN_RES", "CO_MUN_RES"
    )
    notifier_col = _achar_coluna(
        normalized, "ID_MUNICIP", "ID_MUNIC", "ID_MUN_NOT", "CO_MUN_NOT"
    )
    notification_date_col = _achar_coluna(normalized, "DT_NOTIFIC")
    notification_year_col = _achar_coluna(normalized, "NU_ANO")
    classification_col = _achar_coluna(normalized, "CLASSI_FIN")

    rows = 0
    missing_residence = 0
    residence_counts: Counter[str] = Counter()
    notification_year_counts: Counter[str] = Counter()
    classification_counts: Counter[str] = Counter()
    notifier_residence_mismatch = 0
    date_year_vs_nu_ano_mismatch = 0
    date_year_counts: Counter[str] = Counter()

    for row in reader:
        if not row or all(value in (None, "") for value in row.values()):
            continue
        rows += 1

        if residence_col:
            code = _codigo_municipio(row.get(residence_col))
            if code is None:
                missing_residence += 1
            elif code in MUNICIPIOS:
                residence_counts[MUNICIPIOS[code]] += 1

        if notifier_col and residence_col:
            notifier = _codigo_municipio(row.get(notifier_col))
            residence = _codigo_municipio(row.get(residence_col))
            if notifier in MUNICIPIOS and residence in MUNICIPIOS and notifier != residence:
                notifier_residence_mismatch += 1

        if classification_col:
            value = str(row.get(classification_col) or "").strip()
            classification_counts[value if value else "(vazio)"] += 1

        if notification_year_col:
            year = str(row.get(notification_year_col) or "").strip()
            notification_year_counts[year if year else "(vazio)"] += 1

        if notification_date_col:
            date_year = _ano_data(row.get(notification_date_col))
            date_year_counts[date_year] += 1
            if notification_year_col:
                declared_year = str(row.get(notification_year_col) or "").strip()
                if date_year.isdigit() and declared_year.isdigit() and date_year != declared_year:
                    date_year_vs_nu_ano_mismatch += 1

    return {
        "linhas_csv": rows,
        "quantidade_colunas": len(original_headers),
        "cabecalhos": original_headers,
        "colunas_chave_disponiveis": {
            "municipio_residencia": residence_col,
            "municipio_notificador": notifier_col,
            "data_notificacao": notification_date_col,
            "ano_notificacao_declarado": notification_year_col,
            "classificacao_final": classification_col,
        },
        "registros_sem_codigo_residencia": missing_residence if residence_col else None,
        "registros_por_municipio_residencia_alvo": dict(sorted(residence_counts.items())),
        "distribuicao_NU_ANO": dict(sorted(notification_year_counts.items())),
        "distribuicao_ano_DT_NOTIFIC": dict(sorted(date_year_counts.items())),
        "divergencias_ano_DT_NOTIFIC_vs_NU_ANO": (
            date_year_vs_nu_ano_mismatch
            if notification_date_col and notification_year_col
            else None
        ),
        "registros_notificador_e_residencia_em_municipios_alvo_diferentes": (
            notifier_residence_mismatch if notifier_col and residence_col else None
        ),
        "distribuicao_CLASSI_FIN": dict(sorted(classification_counts.items())),
    }


def analisar_arquivo(ano: int, archive_path: Path) -> dict:
    digest = hashlib.sha256()
    with archive_path.open("rb") as archive_file:
        for chunk in iter(lambda: archive_file.read(1024 * 1024), b""):
            digest.update(chunk)

    with zipfile.ZipFile(archive_path) as archive:
        csv_members = [
            info for info in archive.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".csv")
        ]
        if len(csv_members) != 1:
            raise ValueError(
                f"{ano}: esperado exatamente um CSV no ZIP; encontrados {len(csv_members)}."
            )
        member = csv_members[0]
        with archive.open(member) as raw:
            stream = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            summary = analisar_csv(stream)

    return {
        "ano_snapshot": ano,
        "url_fonte_oficial": URL_TEMPLATE.format(ano2=str(ano)[-2:]),
        "arquivo_zip": archive_path.name,
        "sha256_zip": digest.hexdigest(),
        "csv_interno": member.filename,
        "tamanho_csv_descompactado_bytes": member.file_size,
        **summary,
    }


def comparar(arquivos: dict[int, Path]) -> dict:
    snapshots = {
        str(year): analisar_arquivo(year, path)
        for year, path in sorted(arquivos.items())
    }
    years = sorted(snapshots, key=int)
    header_sets = {
        year: set(snapshots[year]["cabecalhos"])
        for year in years
    }
    all_headers = set().union(*header_sets.values())
    common_headers = set.intersection(*header_sets.values()) if header_sets else set()
    comparisons = []
    for year in years:
        current = header_sets[year]
        other_years = [other for other in years if other != year]
        comparisons.append({
            "ano": int(year),
            "colunas_ausentes_em_relacao_a_uniao": sorted(all_headers - current),
            "colunas_exclusivas_deste_ano": sorted(
                current - set.union(*(header_sets[o] for o in other_years))
            ) if other_years else sorted(current),
        })

    return {
        "titulo": "Auditoria estrutural comparativa dos snapshots nacionais SINAN/Dengue",
        "metodo": (
            "Leitura em streaming dos CSVs dentro dos ZIPs oficiais. "
            "Relatório agregado; não armazena nem publica linhas individuais."
        ),
        "anos_analisados": [int(year) for year in years],
        "quantidade_colunas_comuns": len(common_headers),
        "colunas_comuns": sorted(common_headers),
        "comparacao_cabecalhos": comparisons,
        "snapshots": snapshots,
        "alertas": [
            "Diferença de volume ou estrutura não prova, isoladamente, erro ou mudança epidemiológica.",
            "NU_ANO e DT_NOTIFIC são comparados descritivamente; divergências precisam ser interpretadas pelo dicionário oficial da versão.",
            "Contagens de municípios referem-se a registros/notificações por residência, não a pessoas únicas nem automaticamente a casos confirmados.",
            "CLASSI_FIN é reportado por código bruto; a interpretação clínica depende do dicionário oficial correspondente ao snapshot.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arquivo", action="append", required=True, metavar="ANO=CAMINHO_ZIP",
        help="Informe uma vez por ano, por exemplo --arquivo 2024=/tmp/sinan_2024.zip",
    )
    parser.add_argument("--output", required=True, help="Caminho do relatório JSON.")
    args = parser.parse_args()

    files: dict[int, Path] = {}
    for value in args.arquivo:
        year_text, separator, path_text = value.partition("=")
        if not separator or not year_text.isdigit() or not path_text:
            parser.error(f"Formato inválido para --arquivo: {value!r}")
        year = int(year_text)
        path = Path(path_text)
        if year in files:
            parser.error(f"Ano informado mais de uma vez: {year}")
        if not path.is_file():
            parser.error(f"Arquivo não encontrado para {year}: {path}")
        files[year] = path
    if len(files) < 2:
        parser.error("Informe ao menos dois anos para comparação.")

    report = comparar(files)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "relatorio": str(output),
        "anos": report["anos_analisados"],
        "linhas_por_ano": {
            year: details["linhas_csv"]
            for year, details in report["snapshots"].items()
        },
        "colunas_por_ano": {
            year: details["quantidade_colunas"]
            for year, details in report["snapshots"].items()
        },
        "sha256_por_ano": {
            year: details["sha256_zip"]
            for year, details in report["snapshots"].items()
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
