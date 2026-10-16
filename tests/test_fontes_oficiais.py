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
def test_buscar_conjuntos_retorna_resultados(mock_get_json):
    mock_get_json.return_value = {
        "success": True,
        "result": {"results": [{"id": "abc"}, None, {"id": "def"}]},
    }
    assert buscar_conjuntos("dengue") == [{"id": "abc"}, {"id": "def"}]


def test_resumir_recurso_padroniza_metadados():
    result = resumir_recurso({
        "id": "123", "name": "SINAN 2026", "format": "csv",
        "url": "https://example.org/data.zip", "state": "active",
    })
    assert result["id"] == "123"
    assert result["formato"] == "CSV"
    assert result["url"].endswith("data.zip")


@patch("src.ingestion.fontes_oficiais.requests.get")
def test_erro_http_e_convertido_em_erro_de_catalogo(mock_get):
    import requests
    mock_get.side_effect = requests.Timeout("timeout")
    from src.ingestion.fontes_oficiais import _get_json
    with pytest.raises(ErroCatalogoOficial):
        _get_json("https://example.org")
