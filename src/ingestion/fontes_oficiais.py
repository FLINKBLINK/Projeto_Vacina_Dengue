"""Descoberta de fontes oficiais de dengue, vacinação e população.

O Portal de Dados Abertos do SUS não expõe a Action API CKAN no host antigo.
O inventário usa o Swagger oficial da API DEMAS e mantém os links de catálogo
para conferência humana. Esta etapa não baixa microdados nem altera o banco.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

API_BASE = "https://apidadosabertos.saude.gov.br"
OPENAPI_URL = f"{API_BASE}/static/swagger.json"
PORTAL_BASE = "https://dadosabertos.saude.gov.br"
TIMEOUT_SECONDS = 30
USER_AGENT = "Projeto-Vacina-Dengue/1.0 (catalogo-dados-publicos)"


class ErroCatalogoOficial(RuntimeError):
    """Erro de consulta ou resposta inválida das fontes oficiais."""


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Consulta JSON HTTP e converte falhas em erro de domínio."""
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
        raise ErroCatalogoOficial(f"Falha ao consultar fonte oficial: {exc}") from exc

    if not isinstance(payload, dict):
        raise ErroCatalogoOficial("A fonte oficial retornou JSON em formato inesperado.")
    return payload


def buscar_conjuntos(termo: str, limite: int = 100) -> list[dict[str, Any]]:
    """Busca operações relevantes no Swagger da API oficial do Ministério da Saúde."""
    if not termo.strip():
        raise ValueError("O termo de busca não pode ser vazio.")
    if limite < 1 or limite > 500:
        raise ValueError("limite deve estar entre 1 e 500.")

    swagger = _get_json(OPENAPI_URL)
    paths = swagger.get("paths", {})
    if not isinstance(paths, dict):
        raise ErroCatalogoOficial("O Swagger oficial não contém uma lista de operações.")

    termos = [parte.lower() for parte in termo.split() if parte.strip()]
    resultados = []
    for path, metodos in paths.items():
        if not isinstance(metodos, dict):
            continue
        for metodo, operacao in metodos.items():
            if metodo.lower() not in {"get", "post"} or not isinstance(operacao, dict):
                continue
            texto = " ".join([
                str(path),
                str(operacao.get("summary", "")),
                str(operacao.get("description", "")),
                str(operacao.get("operationId", "")),
                " ".join(str(tag) for tag in operacao.get("tags", [])),
            ]).lower()
            if all(termo in texto for termo in termos):
                resultados.append({
                    "id": operacao.get("operationId") or path,
                    "name": path,
                    "title": operacao.get("summary") or path,
                    "description": operacao.get("description", ""),
                    "method": metodo.upper(),
                    "url": f"{API_BASE}{path}",
                    "tags": operacao.get("tags", []),
                })
            if len(resultados) >= limite:
                return resultados
    return resultados


def consultar_conjunto(identificador: str) -> dict[str, Any]:
    """Obtém a operação do Swagger por caminho ou operationId."""
    if not identificador.strip():
        raise ValueError("O identificador não pode ser vazio.")
    swagger = _get_json(OPENAPI_URL)
    paths = swagger.get("paths", {})
    for path, metodos in paths.items():
        if not isinstance(metodos, dict):
            continue
        for metodo, operacao in metodos.items():
            if not isinstance(operacao, dict):
                continue
            if identificador in {path, operacao.get("operationId")}:
                return {
                    "path": path,
                    "method": metodo.upper(),
                    **operacao,
                }
    raise ErroCatalogoOficial(f"Operação não encontrada no Swagger: {identificador}")


def resumir_recurso(recurso: dict[str, Any]) -> dict[str, Any]:
    """Seleciona metadados úteis de uma operação da API."""
    return {
        "id": recurso.get("id"),
        "nome": recurso.get("name"),
        "formato": str(recurso.get("format") or "JSON API").upper(),
        "url": recurso.get("url"),
        "ultima_modificacao": recurso.get("last_modified"),
        "criado_em": recurso.get("created"),
        "estado": recurso.get("state", "documentado_no_swagger"),
    }


def gerar_inventario() -> dict[str, Any]:
    """Gera inventário das operações oficiais relacionadas a dengue e vacinação."""
    consultas = {
        "sinan_dengue": "arboviroses dengue",
        "pni_vacinacao": "vacinacao doses aplicadas pni",
        "populacao": "residente",
    }
    inventario: dict[str, Any] = {
        "extraido_em_utc": datetime.now(timezone.utc).isoformat(),
        "catalogo": PORTAL_BASE,
        "documentacao_api": OPENAPI_URL,
        "consultas": {},
    }
    for chave, termo in consultas.items():
        operacoes = buscar_conjuntos(termo)
        inventario["consultas"][chave] = [
            {
                "id": item.get("id"),
                "nome": item.get("title"),
                "slug": item.get("name"),
                "metodo": item.get("method"),
                "url": item.get("url"),
                "descricao": item.get("description"),
                "tags": item.get("tags", []),
            }
            for item in operacoes
        ]
    return inventario
