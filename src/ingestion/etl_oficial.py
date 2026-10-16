"""Cliente paginado e ETL conservador para as APIs oficiais do Ministério da Saúde.

A extração preserva a resposta original em JSON para auditoria. Não transforma
automaticamente todos os registros do PNI em vacinação contra dengue: a API
PNI contém imunizações diversas e precisa de filtro de imunobiológico validado.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

API_BASE = "https://apidadosabertos.saude.gov.br"
SWAGGER_URL = f"{API_BASE}/static/swagger.json"
TIMEOUT_SECONDS = 60
PAGE_SIZE = 1000
USER_AGENT = "Projeto-Vacina-Dengue/1.0 (etl-dados-publicos)"
MUNICIPIOS_IBGE = {
    "3505601": "Barrinha",
    "3507805": "Brodowski",
    "3513108": "Cravinhos",
    "3518800": "Guatapará",
    "3524303": "Jardinópolis",
    "3540200": "Pontal",
    "3540903": "Pradópolis",
    "3543402": "Ribeirão Preto",
    "3551504": "Serrana",
    "3551702": "Sertãozinho",
}
ENDPOINTS = {
    "sinan_dengue": "/arboviroses/dengue",
    "populacao": "/vigilancia-e-meio-ambiente/svsa-populacao-residente",
}
PNI_ENDPOINT_TEMPLATE = "/vacinacao/doses-aplicadas-pni-{ano}"


class ErroETLOficial(RuntimeError):
    """Erro de consulta, paginação ou validação de dados oficiais."""


def _lista_registros(payload: Any) -> list[dict[str, Any]]:
    """Extrai registros de formatos JSON comuns sem aceitar estruturas ambíguas."""
    if isinstance(payload, list):
        if not all(isinstance(row, dict) for row in payload):
            raise ErroETLOficial("A lista JSON contém elementos que não são objetos.")
        return payload
    if isinstance(payload, dict):
        for key in ("data", "dados", "results", "resultados", "items", "registros"):
            value = payload.get(key)
            if isinstance(value, list):
                if not all(isinstance(row, dict) for row in value):
                    raise ErroETLOficial(f"A chave {key!r} não contém somente objetos.")
                return value
        lists = [v for v in payload.values() if isinstance(v, list)]
        if len(lists) == 1 and all(isinstance(row, dict) for row in lists[0]):
            return lists[0]
    raise ErroETLOficial("Não foi possível identificar a lista de registros na resposta JSON.")


def consultar_pagina(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    session: requests.Session | None = None,
    timeout: int = TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Consulta uma página da API e falha explicitamente se a resposta não for JSON esperado."""
    client = session or requests
    response = client.get(
        f"{API_BASE}{path}",
        params=params or {},
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise ErroETLOficial(f"Resposta não é JSON válido: {path}") from exc
    return _lista_registros(payload)


def iterar_paginas(
    path: str,
    filtros: dict[str, Any] | None = None,
    *,
    page_size: int = PAGE_SIZE,
    max_pages: int | None = None,
    session: requests.Session | None = None,
    pausa_segundos: float = 0.0,
) -> Iterable[list[dict[str, Any]]]:
    """Percorre páginas usando offset=0, page_size, 2*page_size... até página curta."""
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size deve estar entre 1 e 1000.")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages deve ser >= 1.")
    offset = 0
    paginas = 0
    while True:
        params = dict(filtros or {})
        params.update({"limit": page_size, "offset": offset})
        rows = consultar_pagina(path, params, session=session)
        paginas += 1
        yield rows
        if len(rows) < page_size or (max_pages is not None and paginas >= max_pages):
            break
        offset += page_size
        if pausa_segundos:
            time.sleep(pausa_segundos)


def _serializar(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _hash_registro(row: dict[str, Any]) -> str:
    return hashlib.sha256(_serializar(row).encode("utf-8")).hexdigest()


def _campo(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
    lowered = {str(k).lower(): v for k, v in row.items()}
    for alias in aliases:
        if alias.lower() in lowered and lowered[alias.lower()] not in (None, ""):
            return lowered[alias.lower()]
    return None


def _codigo_municipio(row: dict[str, Any]) -> str | None:
    value = _campo(row, ("cod_mun", "id_municip", "codigo_municipio", "codigo_ibge", "co_mun_res", "co_mun_not", "co_mun_paciente", "codigo_municipio_estabelecimento", "codigo_municipio_paciente", "municipio_codigo"))
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 6:
        # Algumas tabelas do SUS usam o código municipal sem o último dígito.
        return next((codigo for codigo in MUNICIPIOS_IBGE if codigo.startswith(digits)), None)
    return digits if digits in MUNICIPIOS_IBGE else None


def inicializar_tabelas_oficiais(conn: sqlite3.Connection) -> None:
    """Cria tabelas aditivas, sem alterar as tabelas legadas do dashboard."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS oficiais_registros (
            fonte TEXT NOT NULL,
            chave_registro TEXT NOT NULL,
            municipio_ibge TEXT,
            municipio TEXT,
            ano_referencia INTEGER,
            extraido_em_utc TEXT NOT NULL,
            registro_json TEXT NOT NULL,
            PRIMARY KEY (fonte, chave_registro)
        );
        CREATE INDEX IF NOT EXISTS idx_oficiais_fonte_municipio
            ON oficiais_registros(fonte, municipio_ibge);
        CREATE TABLE IF NOT EXISTS oficiais_execucoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fonte TEXT NOT NULL,
            iniciado_em_utc TEXT NOT NULL,
            finalizado_em_utc TEXT,
            paginas INTEGER NOT NULL DEFAULT 0,
            registros_recebidos INTEGER NOT NULL DEFAULT 0,
            registros_regiao INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            detalhe TEXT
        );
    """)


def carregar_registros(
    conn: sqlite3.Connection,
    fonte: str,
    registros: Iterable[dict[str, Any]],
    *,
    ano_referencia: int | None = None,
) -> dict[str, int]:
    """Upsert idempotente dos registros brutos; ignora registros fora da região-alvo."""
    extraido = datetime.now(timezone.utc).isoformat()
    recebidos = 0
    regiao = 0
    for row in registros:
        recebidos += 1
        codigo = _codigo_municipio(row)
        if codigo is None:
            continue
        regiao += 1
        conn.execute(
            """INSERT INTO oficiais_registros
               (fonte, chave_registro, municipio_ibge, municipio, ano_referencia,
                extraido_em_utc, registro_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(fonte, chave_registro) DO UPDATE SET
                 municipio_ibge=excluded.municipio_ibge,
                 municipio=excluded.municipio,
                 ano_referencia=excluded.ano_referencia,
                 extraido_em_utc=excluded.extraido_em_utc,
                 registro_json=excluded.registro_json""",
            (fonte, _hash_registro(row), codigo, MUNICIPIOS_IBGE[codigo],
             ano_referencia, extraido, _serializar(row)),
        )
    return {"recebidos": recebidos, "regiao": regiao}


def executar_extracao(
    db_path: str | Path,
    *,
    anos_sinan: tuple[int, ...] = (2023, 2024, 2025),
    anos_populacao: tuple[int, ...] = (2023, 2024, 2025),
    incluir_pni: bool = False,
    anos_pni: tuple[int, ...] = (2024, 2025, 2026),
    page_size: int = PAGE_SIZE,
    max_pages_por_consulta: int | None = None,
    session: requests.Session | None = None,
    pausa_segundos: float = 0.0,
) -> dict[str, Any]:
    """Extrai fontes selecionadas e salva apenas registros da região em transações.

    O PNI é opcional porque a rota é nacional e não documenta filtro de município
    ou imunobiológico. A importação PNI não deve ser confundida com vacina dengue.
    """
    path_db = Path(db_path)
    path_db.parent.mkdir(parents=True, exist_ok=True)
    resumo: dict[str, Any] = {"db_path": str(path_db), "fontes": [], "alertas": []}
    with sqlite3.connect(path_db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        inicializar_tabelas_oficiais(conn)
        consultas: list[tuple[str, str, dict[str, Any], int]] = []
        for ano in anos_sinan:
            for codigo in MUNICIPIOS_IBGE:
                consultas.append(("sinan_dengue", ENDPOINTS["sinan_dengue"],
                                  {"nu_ano": str(ano), "id_municip": codigo[:-1]}, ano))
        for ano in anos_populacao:
            for codigo in MUNICIPIOS_IBGE:
                consultas.append(("populacao", ENDPOINTS["populacao"],
                                  {"ano": ano, "cod_mun": int(codigo)}, ano))
        if incluir_pni:
            resumo["alertas"].append(
                "PNI é uma base nacional de imunizações diversas; dados não foram classificados como vacina dengue."
            )
            for ano in anos_pni:
                consultas.append((f"pni_{ano}", PNI_ENDPOINT_TEMPLATE.format(ano=ano), {}, ano))

        for fonte, endpoint, filtros, ano in consultas:
            inicio = datetime.now(timezone.utc).isoformat()
            cur = conn.execute(
                "INSERT INTO oficiais_execucoes (fonte, iniciado_em_utc, status) VALUES (?, ?, 'executando')",
                (fonte, inicio),
            )
            exec_id = cur.lastrowid
            paginas = recebidos = regiao = 0
            try:
                with conn:
                    for page in iterar_paginas(
                        endpoint, filtros, page_size=page_size,
                        max_pages=max_pages_por_consulta, session=session,
                        pausa_segundos=pausa_segundos,
                    ):
                        paginas += 1
                        stats = carregar_registros(conn, fonte, page, ano_referencia=ano)
                        recebidos += stats["recebidos"]
                        regiao += stats["regiao"]
                conn.execute(
                    """UPDATE oficiais_execucoes SET finalizado_em_utc=?, paginas=?,
                       registros_recebidos=?, registros_regiao=?, status='sucesso'
                       WHERE id=?""",
                    (datetime.now(timezone.utc).isoformat(), paginas, recebidos, regiao, exec_id),
                )
            except Exception as exc:
                conn.execute(
                    """UPDATE oficiais_execucoes SET finalizado_em_utc=?, paginas=?,
                       registros_recebidos=?, registros_regiao=?, status='erro', detalhe=?
                       WHERE id=?""",
                    (datetime.now(timezone.utc).isoformat(), paginas, recebidos, regiao,
                     f"{type(exc).__name__}: {exc}"[:1000], exec_id),
                )
                raise
            resumo["fontes"].append({
                "fonte": fonte, "ano": ano, "paginas": paginas,
                "registros_recebidos": recebidos, "registros_regiao": regiao,
            })
    return resumo


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="ETL paginado das APIs oficiais do Ministério da Saúde")
    parser.add_argument("--db", default=os.getenv("DENGUE_DB_PATH", "data/processed/dengue.db"))
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Limita páginas por consulta para teste; não usar para carga completa.")
    parser.add_argument("--incluir-pni", action="store_true",
                        help="Extrai também PNI nacional (pode ser muito volumoso; não classifica vacina dengue).")
    parser.add_argument("--pausa", type=float, default=0.0, help="Pausa entre páginas, em segundos.")
    args = parser.parse_args()
    resumo = executar_extracao(
        args.db, incluir_pni=args.incluir_pni, page_size=args.page_size,
        max_pages_por_consulta=args.max_pages, pausa_segundos=args.pausa,
    )
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
