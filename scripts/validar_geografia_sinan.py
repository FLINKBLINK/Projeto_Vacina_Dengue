"""Valida filtros geográficos do SINAN sem expor dados individuais.

A consulta é uma amostra limitada; os resultados NÃO comprovam totais nacionais
ou municipais completos. O relatório imprime apenas contagens e códigos agregados.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

import requests

BASE = "https://apidadosabertos.saude.gov.br"
ROUTE = "/arboviroses/dengue"
LIMIT = 100
TIMEOUT = 30
MUNICIPIO_TESTE = "354340"  # Ribeirão Preto, código de seis dígitos usado no SINAN


def extrair_registros(payload: Any) -> list[dict[str, Any]]:
    """Extrai registros de envelopes conhecidos sem exibir o payload bruto."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("dengue", "data", "dados", "results", "resultados", "items", "registros"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        lists = [value for value in payload.values() if isinstance(value, list)]
        if len(lists) == 1:
            return [item for item in lists[0] if isinstance(item, dict)]
    raise ValueError("Formato JSON não reconhecido; conteúdo bruto omitido.")


def contar_codigos(registros: list[dict[str, Any]], campo: str) -> dict[str, int]:
    """Retorna frequências de códigos geográficos, nunca linhas individuais."""
    contagem = Counter()
    for registro in registros:
        valor = registro.get(campo)
        if valor not in (None, ""):
            contagem[str(valor)] += 1
    return dict(sorted(contagem.items(), key=lambda item: (-item[1], item[0]))[:20])


def resumir_resposta(payload: Any) -> dict[str, Any]:
    registros = extrair_registros(payload)
    campos = sorted({str(chave) for registro in registros for chave in registro})
    return {
        "registros_na_amostra": len(registros),
        "campos_geograficos_presentes": [
            campo for campo in ("id_municip", "id_mn_resi") if campo in campos
        ],
        "frequencias_id_municip": contar_codigos(registros, "id_municip"),
        "frequencias_id_mn_resi": contar_codigos(registros, "id_mn_resi"),
        "amostra_vazia": not registros,
    }


def consultar(nome: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        f"{BASE}{ROUTE}",
        params={**params, "limit": LIMIT, "offset": 0},
        headers={"Accept": "application/json", "User-Agent": "Projeto-Vacina-Dengue/1.0"},
        timeout=TIMEOUT,
    )
    resultado: dict[str, Any] = {
        "consulta": nome,
        "http_status": response.status_code,
        "parametros_enviados": sorted(params),
        "limite_amostra": LIMIT,
    }
    response.raise_for_status()
    resultado.update(resumir_resposta(response.json()))
    resultado["filtro_confirmado_pela_amostra"] = None
    return resultado


def main() -> int:
    consultas = [
        ("ano_sem_filtro_geografico", {"nu_ano": "2024"}),
        ("filtro_id_municip", {"nu_ano": "2024", "id_municip": MUNICIPIO_TESTE}),
        ("filtro_id_mn_resi", {"nu_ano": "2024", "id_mn_resi": MUNICIPIO_TESTE}),
    ]
    resultados = []
    erros = []
    for nome, params in consultas:
        try:
            resultados.append(consultar(nome, params))
        except Exception as exc:
            # Não imprimir corpo da resposta, URL completa ou registros individuais.
            erros.append({"consulta": nome, "tipo_erro": type(exc).__name__})
    print(json.dumps({
        "aviso": (
            "Amostra limitada a 100 registros por consulta. Diferenças sugerem "
            "comportamento dos filtros, mas não validam totais completos. "
            "Nenhum registro individual é impresso."
        ),
        "consultas": resultados,
        "erros": erros,
    }, ensure_ascii=False, indent=2))
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
