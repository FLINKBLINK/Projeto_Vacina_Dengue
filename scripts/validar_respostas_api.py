"""Valida respostas pequenas da API DEMAS sem persistir microdados pessoais."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

API_BASE = "https://apidadosabertos.saude.gov.br/v1"
SWAGGER_URL = "https://apidadosabertos.saude.gov.br/static/swagger.json"
TIMEOUT_SECONDS = 60
USER_AGENT = "Projeto-Vacina-Dengue/1.0 (validacao-de-fontes-publicas)"


def _find_records(payload: Any) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Localiza uma lista de registros em respostas JSON comuns."""
    if isinstance(payload, list):
        records = [item for item in payload if isinstance(item, dict)]
        return records, "$", []
    if not isinstance(payload, dict):
        return [], "$", []

    metadata_keys = [str(key) for key in payload if not isinstance(payload[key], (list, dict))]
    preferred = ("data", "dados", "results", "resultados", "items", "registros")
    for key in preferred:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)], f"$.{key}", metadata_keys
    for key, value in payload.items():
        if isinstance(value, list) and (not value or all(isinstance(item, dict) for item in value)):
            return value, f"$.{key}", metadata_keys
    return [], "$", metadata_keys


def validar_endpoint(nome: str, path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    resultado: dict[str, Any] = {
        "fonte": nome,
        "url": url,
        "parametros_teste": params,
        "status_http": None,
        "content_type": None,
        "sucesso": False,
        "quantidade_registros_amostra": 0,
        "caminho_registros_json": None,
        "campos_amostra": [],
        "chaves_metadados_resposta": [],
        "erro": None,
        "observacao": "Amostra limitada; nenhum registro individual é gravado no relatório.",
    }
    try:
        response = requests.get(
            url,
            params=params,
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        resultado["status_http"] = response.status_code
        resultado["content_type"] = response.headers.get("Content-Type")
        response.raise_for_status()
        payload = response.json()
        records, record_path, metadata_keys = _find_records(payload)
        resultado.update({
            "sucesso": True,
            "quantidade_registros_amostra": len(records),
            "caminho_registros_json": record_path,
            "campos_amostra": sorted({str(key) for row in records[:5] for key in row}),
            "chaves_metadados_resposta": metadata_keys,
        })
        if not records:
            resultado["observacao"] = (
                "HTTP/JSON válido, mas não foi identificada lista de registros na resposta. "
                "Inspecionar formato antes de implementar ETL."
            )
    except (requests.RequestException, ValueError) as exc:
        resultado["erro"] = f"{type(exc).__name__}: {exc}"
    return resultado


def gerar_relatorio() -> dict[str, Any]:
    """Testa um pequeno lote em cada fonte e registra apenas status e esquema."""
    amostras = [
        ("sinan_dengue", "/arboviroses/dengue", {"nu_ano": "2025", "limit": 5, "offset": 0}),
        ("pni_vacinacao_2026", "/vacinacao/doses-aplicadas-pni-2026", {"limit": 5, "offset": 0}),
        ("populacao_2025", "/vigilancia-e-meio-ambiente/svsa-populacao-residente", {"ano": 2025, "limit": 5, "offset": 0}),
    ]
    resultados = [validar_endpoint(nome, path, params) for nome, path, params in amostras]
    return {
        "validado_em_utc": datetime.now(timezone.utc).isoformat(),
        "swagger_oficial": SWAGGER_URL,
        "tipo_teste": "amostras pequenas; sem persistência de microdados",
        "fontes": resultados,
        "resumo": {
            "total_fontes": len(resultados),
            "fontes_http_json_ok": sum(item["sucesso"] for item in resultados),
            "fontes_com_registros_na_amostra": sum(item["quantidade_registros_amostra"] > 0 for item in resultados),
            "fontes_com_erro": sum(not item["sucesso"] for item in resultados),
        },
    }


def main() -> int:
    output = Path("artifacts/validacao-respostas-api.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = gerar_relatorio()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["resumo"], ensure_ascii=False))
    for item in report["fontes"]:
        print(
            f'{item["fonte"]}: HTTP={item["status_http"]}, '
            f'registros_amostra={item["quantidade_registros_amostra"]}, erro={item["erro"]}'
        )
    return 1 if report["resumo"]["fontes_com_erro"] else 0


if __name__ == "__main__":
    sys.exit(main())
