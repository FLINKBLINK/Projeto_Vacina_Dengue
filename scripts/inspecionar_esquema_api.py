"""Inspeciona o esquema real das APIs oficiais sem imprimir valores de registros.

O relatório mostra apenas nomes de campos, tipos JSON e contagem de amostras.
Não grava dados pessoais nem substitui o ETL principal.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

import requests

BASE = "https://apidadosabertos.saude.gov.br"
HEADERS = {
    "User-Agent": "Projeto-Vacina-Dengue/1.0 (inspecao-de-esquema)",
    "Accept": "application/json",
}
TIMEOUT = 30


def extrair_lista(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "dados", "results", "resultados", "items", "registros"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        lists = [value for value in payload.values() if isinstance(value, list)]
        if len(lists) == 1:
            return [row for row in lists[0] if isinstance(row, dict)]
    raise ValueError("Formato JSON não reconhecido; sem imprimir conteúdo bruto.")


def tipo_json(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def inspecionar(nome: str, rota: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        f"{BASE}{rota}", params={**params, "limit": 5, "offset": 0},
        headers=HEADERS, timeout=TIMEOUT,
    )
    resultado: dict[str, Any] = {
        "fonte": nome,
        "rota": rota,
        "http_status": response.status_code,
        "parametros_enviados": sorted(params.keys()),
    }
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError(f"{nome}: resposta não é JSON válido.") from exc
    rows = extrair_lista(payload)
    tipos: dict[str, set[str]] = {}
    for row in rows:
        for key, value in row.items():
            tipos.setdefault(str(key), set()).add(tipo_json(value))
    resultado["registros_amostra"] = len(rows)
    resultado["campos"] = [
        {"nome": key, "tipos_observados": sorted(values)}
        for key, values in sorted(tipos.items())
    ]
    resultado["amostra_vazia"] = len(rows) == 0
    return resultado


def main() -> int:
    consultas = [
        ("sinan_dengue_2024_ribeirao", "/arboviroses/dengue",
         {"nu_ano": "2024", "id_municip": "35434"}),
        ("populacao_2023_ribeirao", "/vigilancia-e-meio-ambiente/svsa-populacao-residente",
         {"ano": 2023, "cod_mun": 3543402}),
        ("pni_2025_amostra_nacional", "/vacinacao/doses-aplicadas-pni-2025", {}),
    ]
    relatorio = []
    erros = []
    for nome, rota, params in consultas:
        try:
            relatorio.append(inspecionar(nome, rota, params))
        except Exception as exc:
            erros.append({"fonte": nome, "erro": f"{type(exc).__name__}: {exc}"})
    print(json.dumps({"inspecoes": relatorio, "erros": erros}, ensure_ascii=False, indent=2))
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
