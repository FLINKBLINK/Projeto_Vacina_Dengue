"""Diagnóstico controlado da paginação SINAN com filtro local por residência.

Não salva registros nem imprime dados de pacientes. Por padrão, lê no máximo
10 páginas de 1.000 linhas do ano de 2024 para estimar volume e cobertura.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from typing import Any

import requests

BASE = "https://apidadosabertos.saude.gov.br"
ROTA = "/arboviroses/dengue"
PAGE_SIZE = 1000
TIMEOUT = 60
CHAVES_REGISTROS = (
    "data", "dados", "results", "resultados", "items", "registros",
    "content", "records", "value", "dengue",
)
CHAVES_ERRO = ("message", "detail", "erro", "error", "mensagem")
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


def lista_registros(payload: Any) -> list[dict[str, Any]]:
    """Extrai a lista de registros de formatos JSON comuns sem expor os dados."""
    if isinstance(payload, list):
        if all(isinstance(item, dict) for item in payload):
            return payload
        raise ValueError(
            "A API SINAN retornou uma lista JSON, mas os itens não são objetos."
        )

    if isinstance(payload, dict):
        # Algumas APIs envolvem a lista em mais de um nível, por exemplo
        # {"data": {"results": [...]}}.
        for key in CHAVES_REGISTROS:
            if key in payload:
                value = payload[key]
                if isinstance(value, list) and all(
                    isinstance(item, dict) for item in value
                ):
                    return value
                if isinstance(value, dict):
                    try:
                        return lista_registros(value)
                    except ValueError:
                        pass

        chaves = ", ".join(sorted(str(key) for key in payload.keys())[:20])
        detalhe = next(
            (str(payload[key])[:240] for key in CHAVES_ERRO
             if payload.get(key) not in (None, "")),
            None,
        )
        mensagem = (
            f"Formato JSON inesperado na API SINAN. "
            f"Chaves recebidas: [{chaves or 'nenhuma'}]."
        )
        if detalhe:
            mensagem += f" Mensagem da API: {detalhe}"
        raise ValueError(mensagem)

    raise ValueError(
        f"Formato JSON inesperado na API SINAN: tipo {type(payload).__name__}."
    )


def codigo_residencia(row: dict[str, Any]) -> str | None:
    value = row.get("id_mn_resi")
    if value in (None, ""):
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    # SINAN pode retornar código municipal sem o dígito verificador IBGE.
    return digits[:6] if len(digits) in (6, 7) else None


def resumir_linhas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    contagem = Counter()
    codigos = Counter()
    sem_codigo = 0
    for row in rows:
        codigo = codigo_residencia(row)
        if codigo is None:
            sem_codigo += 1
        else:
            codigos[codigo] += 1
            if codigo in MUNICIPIOS:
                contagem[codigo] += 1
    return {
        "linhas_lidas": len(rows),
        "linhas_sem_codigo_residencia": sem_codigo,
        "linhas_por_municipio_residencia_alvo": {
            MUNICIPIOS[codigo]: contagem.get(codigo, 0)
            for codigo in MUNICIPIOS
        },
        "codigos_residencia_mais_frequentes": [
            {"codigo_6_digitos": codigo, "ocorrencias": n}
            for codigo, n in codigos.most_common(15)
        ],
    }


def diagnosticar(ano: int, max_pages: int, page_size: int, pausa: float) -> dict[str, Any]:
    if max_pages < 1:
        raise ValueError("max_pages deve ser >= 1.")
    if not 1 <= page_size <= PAGE_SIZE:
        raise ValueError(f"page_size deve estar entre 1 e {PAGE_SIZE}.")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Projeto-Vacina-Dengue/1.0 (diagnostico-paginacao)",
        "Accept": "application/json",
    })
    total_lido = 0
    paginas = 0
    todos_codigos = Counter()
    contagem_alvos = Counter()
    sem_codigo = 0
    ultima_pagina_cheia = False
    for pagina in range(max_pages):
        # Nesta API, offset representa o número da página (0, 1, 2...),
        # não a quantidade de registros a pular. Ver Swagger do endpoint SINAN.
        offset = pagina
        response = session.get(
            f"{BASE}{ROTA}",
            params={"nu_ano": str(ano), "limit": page_size, "offset": offset},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            content_type = response.headers.get("Content-Type", "desconhecido")
            raise ValueError(
                "A API SINAN não retornou JSON válido "
                f"(Content-Type: {content_type})."
            ) from exc
        rows = lista_registros(payload)
        paginas += 1
        total_lido += len(rows)
        resumo = resumir_linhas(rows)
        sem_codigo += resumo["linhas_sem_codigo_residencia"]
        for nome, quantidade in resumo["linhas_por_municipio_residencia_alvo"].items():
            contagem_alvos[nome] += quantidade
        for item in resumo["codigos_residencia_mais_frequentes"]:
            todos_codigos[item["codigo_6_digitos"]] += item["ocorrencias"]
        ultima_pagina_cheia = len(rows) == page_size
        if len(rows) < page_size:
            break
        if pausa:
            time.sleep(pausa)
    completo = not ultima_pagina_cheia
    return {
        "fonte": "SINAN dengue",
        "ano": ano,
        "filtro_api": {"nu_ano": ano},
        "filtro_municipio": "local, usando id_mn_resi; nenhum filtro municipal enviado à API",
        "tamanho_pagina": page_size,
        "limite_paginas": max_pages,
        "paginas_lidas": paginas,
        "registros_lidos": total_lido,
        "varredura_terminou_em_pagina_curta": completo,
        "varredura_completa": completo,
        "registros_sem_codigo_residencia": sem_codigo,
        "registros_por_municipio_residencia_alvo": {
            nome: contagem_alvos.get(nome, 0) for nome in MUNICIPIOS.values()
        },
        "codigos_residencia_mais_frequentes_na_amostra": [
            {"codigo_6_digitos": codigo, "ocorrencias": n}
            for codigo, n in todos_codigos.most_common(15)
        ],
        "alertas": [] if completo else [
            "Limite de páginas atingido antes de uma página curta; contagens são parciais."
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=2024)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    parser.add_argument("--pausa", type=float, default=0.2)
    args = parser.parse_args()
    print(json.dumps(
        diagnosticar(args.ano, args.max_pages, args.page_size, args.pausa),
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
