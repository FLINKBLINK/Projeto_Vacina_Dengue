"""Diagnóstico SINAN por município notificador e residência.

Não grava nem imprime linhas individuais. Compara páginas em memória por hash
para detectar repetições e resume o município notificador (id_municip) versus
município de residência (id_mn_resi).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from typing import Any

import requests

BASE = "https://apidadosabertos.saude.gov.br"
ROTA = "/arboviroses/dengue"
TIMEOUT = 60
CHAVES_REGISTROS = (
    "data", "dados", "results", "resultados", "items", "registros",
    "content", "records", "value", "dengue",
)
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


def lista_registros(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list) and all(isinstance(x, dict) for x in payload):
        return payload
    if isinstance(payload, dict):
        for key in CHAVES_REGISTROS:
            value = payload.get(key)
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                return value
            if isinstance(value, dict):
                try:
                    return lista_registros(value)
                except ValueError:
                    pass
        keys = ", ".join(sorted(map(str, payload.keys()))[:20])
        raise ValueError(f"Formato inesperado na resposta SINAN; chaves: [{keys}]")
    raise ValueError(f"Formato inesperado na resposta SINAN: {type(payload).__name__}")


def codigo_municipal(row: dict[str, Any], campo: str) -> str | None:
    value = row.get(campo)
    if value in (None, ""):
        return None
    digits = "".join(c for c in str(value) if c.isdigit())
    return digits[:6] if len(digits) in (6, 7) else None


def assinatura_linha(row: dict[str, Any]) -> str:
    # Hash temporário em memória: não expõe nem grava dados individuais.
    canonical = json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def diagnosticar(ano: int, max_pages: int, page_size: int, pausa: float) -> dict[str, Any]:
    if max_pages < 1:
        raise ValueError("max_pages deve ser >= 1")
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size deve estar entre 1 e 1000")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Projeto-Vacina-Dengue/1.0 (diagnostico-municipios)",
        "Accept": "application/json",
    })
    resultados = {}
    for codigo, nome in MUNICIPIOS.items():
        hashes_vistos: set[str] = set()
        hashes_paginas: list[str] = []
        registros_lidos = 0
        repetidos = 0
        paginas_lidas = 0
        curta = False
        contagem_residencia: Counter[str] = Counter()
        sem_residencia = 0
        codigos_notificadores: Counter[str] = Counter()

        for pagina in range(max_pages):
            response = session.get(
                f"{BASE}{ROTA}",
                params={
                    "nu_ano": str(ano),
                    "id_municip": codigo,
                    "limit": page_size,
                    "offset": pagina,
                },
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            rows = lista_registros(response.json())
            paginas_lidas += 1
            registros_lidos += len(rows)
            pagina_hashes = []
            for row in rows:
                row_hash = assinatura_linha(row)
                pagina_hashes.append(row_hash)
                if row_hash in hashes_vistos:
                    repetidos += 1
                else:
                    hashes_vistos.add(row_hash)

                residencia = codigo_municipal(row, "id_mn_resi")
                if residencia is None:
                    sem_residencia += 1
                else:
                    contagem_residencia[residencia] += 1
                notificador = codigo_municipal(row, "id_municip")
                if notificador:
                    codigos_notificadores[notificador] += 1

            digest = hashlib.sha256("|".join(pagina_hashes).encode()).hexdigest()
            hashes_paginas.append(digest)
            curta = len(rows) < page_size
            if curta:
                break
            if pausa:
                time.sleep(pausa)

        resultados[nome] = {
            "codigo_consultado_id_municip": codigo,
            "paginas_lidas": paginas_lidas,
            "registros_lidos": registros_lidos,
            "registros_distintos_por_hash": len(hashes_vistos),
            "registros_repetidos_entre_paginas_ou_na_consulta": repetidos,
            "paginas_com_assinatura_repetida": len(hashes_paginas) - len(set(hashes_paginas)),
            "terminou_em_pagina_curta": curta,
            "varredura_completa": curta,
            "registros_sem_codigo_residencia": sem_residencia,
            "registros_por_residencia_nos_municipios_do_estudo": {
                MUNICIPIOS[c]: contagem_residencia.get(c, 0) for c in MUNICIPIOS
            },
            "codigos_notificadores_retornados": dict(codigos_notificadores.most_common(5)),
            "alertas": [] if curta and repetidos == 0 else [
                message for condition, message in [
                    (not curta, "Limite de páginas atingido; resultado parcial."),
                    (repetidos > 0, "Há registros repetidos; verificar semântica de offset."),
                ] if condition
            ],
        }

    return {
        "fonte": "SINAN dengue",
        "ano": ano,
        "objetivo": "Comparar filtro por município notificador (id_municip) com município de residência (id_mn_resi).",
        "parametros": {"page_size": page_size, "max_pages": max_pages, "offsets": "0, 1, 2..."},
        "dados_pessoais": "Nenhuma linha individual é impressa ou gravada; hashes usados apenas em memória.",
        "resultados_por_municipio_notificador": resultados,
        "observacao": "id_municip identifica município notificador, não residência; contagens não equivalem automaticamente a casos confirmados.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=2024)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--pausa", type=float, default=0.2)
    args = parser.parse_args()
    print(json.dumps(
        diagnosticar(args.ano, args.max_pages, args.page_size, args.pausa),
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
