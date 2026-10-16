from unittest.mock import patch

import pytest

from src.ingestion.fontes_oficiais import (
    ErroCatalogoOficial,
    buscar_conjuntos,
    resumir_recurso,
)


def test_buscar_conjuntos_valida_termo_vazio():
    with pytest.raises(ValueError):
        buscar_conjuntos("  ")


def test_buscar_conjuntos_valida_limite():
    with pytest.raises(ValueError):
        buscar_conjuntos("dengue", limite=501)


@patch("src.ingestion.fontes_oficiais._get_json")
def test_buscar_conjuntos_filtra_operacoes_do_swagger(mock_get_json):
    mock_get_json.return_value = {
        "basePath": "/v1",
        "paths": {
            "/arboviroses/dengue": {
                "get": {
                    "operationId": "get_arboviroses_dengue",
                    "summary": "Lista de notificações de dengue",
                    "description": "Dados por ano e município",
                    "tags": ["Agravo Arboviroses"],
                }
            },
            "/cnes/estabelecimentos": {
                "get": {
                    "operationId": "get_cnes_estabelecimentos",
                    "summary": "Lista de estabelecimentos",
                    "description": "Cadastro de estabelecimentos",
                    "tags": ["CNES"],
                }
            },
        },
    }
    resultado = buscar_conjuntos("arboviroses dengue")
    assert len(resultado) == 1
    assert resultado[0]["id"] == "get_arboviroses_dengue"
    assert resultado[0]["url"].endswith("/v1/arboviroses/dengue")


def test_resumir_recurso_padroniza_metadados():
    result = resumir_recurso({
        "id": "123", "name": "/arboviroses/dengue",
        "format": "json api", "url": "https://example.org/data",
        "state": "active",
    })
    assert result["id"] == "123"
    assert result["formato"] == "JSON API"
    assert result["url"].endswith("/data")


@patch("src.ingestion.fontes_oficiais.requests.get")
def test_erro_http_e_convertido_em_erro_de_catalogo(mock_get):
    import requests
    mock_get.side_effect = requests.Timeout("timeout")
    from src.ingestion.fontes_oficiais import _get_json
    with pytest.raises(ErroCatalogoOficial):
        _get_json("https://example.org")
