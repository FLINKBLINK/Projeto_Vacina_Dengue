"""Inspeciona o esquema real das APIs oficiais sem imprimir dados pessoais.

O relatório mostra campos/tipos e apenas valores de identificadores geográficos
ou classificações públicas da vacina, para validar filtros e códigos de imunizante.
"""
from __future__ import annotations

import json
from typing import Any

import requests

BASE = "https://apidadosabertos.saude.gov.br"
HEADERS = {
    "User-Agent": "Projeto-Vacina-Dengue/1.0 (inspecao-de-esquema)",
    "Accept": "application/json",
}
TIMEOUT = 30
SAMPLE_LIMIT = 100
CAMPOS_PUBLICOS = {
    "id_municip", "municipio", "nu_ano", "ano", "cod_mun",
    "nome_municipio_estabelecimento", "nome_municipio_paciente",
    "codigo_municipio_estabelecimento", "codigo_municipio_paciente",
    "codigo_vacina", "descricao_vacina", "codigo_dose_vacina",
}


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
        f"{BASE}{rota}", params={**params, "limit": SAMPLE_LIMIT, "offset": 0},
        headers=HEADERS, timeout=TIMEOUT,
    )
    resultado: dict[str, Any] = {
        "fonte": nome, "rota": rota, "http_status": response.status_code,
        "parametros_enviados": sorted(params.keys()),
    }
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError(f"{nome}: resposta não é JSON válido.") from exc
    rows = extrair_lista(payload)
    tipos: dict[str, set[str]] = {}
    identificadores: dict[str, dict[str, int]] = {}
    for row in rows:
        for key, value in row.items():
            tipos.setdefault(str(key), set()).add(tipo_json(value))
            if str(key).lower() in CAMPOS_PUBLICOS and value not in (None, ""):
                bucket = identificadores.setdefault(str(key), {})
                label = str(value)
                bucket[label] = bucket.get(label, 0) + 1
    resultado["registros_amostra"] = len(rows)
    resultado["campos"] = [
        {"nome": key, "tipos_observados": sorted(values)}
        for key, values in sorted(tipos.items())
    ]
    resultado["identificadores_publicos_observados"] = {
        key: [
            {"valor": value, "ocorrencias_na_amostra": count}
            for value, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:20]
        ]
        for key, values in sorted(identificadores.items())
    }
    resultado["limite_amostra"] = SAMPLE_LIMIT
    resultado["amostra_vazia"] = len(rows) == 0
    return resultado


def main() -> int:
    consultas = [
        ("sinan_2024_sem_filtro_municipal", "/arboviroses/dengue", {"nu_ano": "2024"}),
        ("sinan_2024_municipio_6_digitos", "/arboviroses/dengue",
         {"nu_ano": "2024", "id_municip": "354340"}),
        ("sinan_2024_municipio_5_digitos", "/arboviroses/dengue",
         {"nu_ano": "2024", "id_municip": "35434"}),
        ("sinan_2024_municipio_7_digitos", "/arboviroses/dengue",
         {"nu_ano": "2024", "id_municip": "3543402"}),
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
