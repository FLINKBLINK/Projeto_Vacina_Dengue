"""Descoberta de recursos oficiais no catálogo CKAN do Ministério da Saúde.

Esta etapa consulta metadados públicos; não baixa nem altera o banco de produção.
Os recursos devem ser validados antes de serem incorporados ao ETL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

CKAN_ACTION_API = "https://dadosabertos.saude.gov.br/api/3/action"
TIMEOUT_SECONDS = 30
USER_AGENT = "Projeto-Vacina-Dengue/1.0 (catalogo-dados-publicos)"


class ErroCatalogoOficial(RuntimeError):
    """Erro de consulta ou resposta inválida do catálogo oficial."""


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        response = requests.get(
            url,
            params=params,
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ErroCatalogoOficial(f"Falha ao consultar catálogo oficial: {exc}") from exc

    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ErroCatalogoOficial("O catálogo oficial retornou resposta sem sucesso.")
    return payload


def buscar_conjuntos(termo: str, limite: int = 100) -> list[dict[str, Any]]:
    """Busca conjuntos por termo no catálogo CKAN oficial."""
    if not termo.strip():
        raise ValueError("O termo de busca não pode ser vazio.")
    if limite < 1 or limite > 500:
        raise ValueError("limite deve estar entre 1 e 500.")

    payload = _get_json(
        f"{CKAN_ACTION_API}/package_search",
        {"q": termo.strip(), "rows": limite, "sort": "metadata_modified desc"},
    )
    resultado = payload.get("result", {})
    if not isinstance(resultado, dict):
        raise ErroCatalogoOficial("Formato inesperado na resposta package_search.")
    conjuntos = resultado.get("results", [])
    if not isinstance(conjuntos, list):
        raise ErroCatalogoOficial("Lista de conjuntos ausente na resposta do catálogo.")
    return [item for item in conjuntos if isinstance(item, dict)]


def consultar_conjunto(identificador: str) -> dict[str, Any]:
    """Obtém os metadados completos de um conjunto pelo ID ou slug."""
    if not identificador.strip():
        raise ValueError("O identificador do conjunto não pode ser vazio.")
    payload = _get_json(
        f"{CKAN_ACTION_API}/package_show",
        {"id": identificador.strip()},
    )
    resultado = payload.get("result")
    if not isinstance(resultado, dict):
        raise ErroCatalogoOficial("Metadados do conjunto ausentes.")
    return resultado


def resumir_recurso(recurso: dict[str, Any]) -> dict[str, Any]:
    """Seleciona metadados úteis para o inventário, sem baixar o arquivo."""
    return {
        "id": recurso.get("id"),
        "nome": recurso.get("name"),
        "formato": str(recurso.get("format") or "").upper(),
        "url": recurso.get("url"),
        "ultima_modificacao": recurso.get("last_modified"),
        "criado_em": recurso.get("created"),
        "estado": recurso.get("state"),
    }


def gerar_inventario() -> dict[str, Any]:
    """Gera um inventário dos catálogos prioritários de dengue e vacinação."""
    consultas = {
        "sinan_dengue": "arboviroses dengue",
        "pni_vacinacao": "doses aplicadas programa nacional imunizações PNI",
    }
    inventario: dict[str, Any] = {
        "extraido_em_utc": datetime.now(timezone.utc).isoformat(),
        "catalogo": "https://dadosabertos.saude.gov.br/",
        "consultas": {},
    }
    for chave, termo in consultas.items():
        conjuntos = buscar_conjuntos(termo)
        inventario["consultas"][chave] = [
            {
                "id": item.get("id"),
                "nome": item.get("title"),
                "slug": item.get("name"),
                "ultima_modificacao": item.get("metadata_modified"),
                "frequencia_atualizacao": item.get("frequency"),
                "url": item.get("url"),
                "recursos": [
                    resumir_recurso(recurso)
                    for recurso in item.get("resources", [])
                    if isinstance(recurso, dict)
                ],
            }
            for item in conjuntos
        ]
    return inventario
