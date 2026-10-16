from scripts.validar_respostas_api import _find_records, validar_endpoint


def test_find_records_reconhece_lista_na_resposta():
    records, path, metadata = _find_records({"data": [{"a": 1}, {"b": 2}], "total": 2})
    assert len(records) == 2
    assert path == "$.data"
    assert "total" in metadata


def test_find_records_reconhece_lista_na_raiz():
    records, path, metadata = _find_records([{"id": 1}])
    assert records == [{"id": 1}]
    assert path == "$"
    assert metadata == []


def test_validar_endpoint_registra_campos_sem_gravar_registros(monkeypatch):
    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"ano": 2025, "cod_mun": 1234567}], "total": 1}

    monkeypatch.setattr("scripts.validar_respostas_api.requests.get", lambda *args, **kwargs: FakeResponse())
    resultado = validar_endpoint("populacao", "/exemplo", {"limit": 5})
    assert resultado["sucesso"] is True
    assert resultado["quantidade_registros_amostra"] == 1
    assert resultado["campos_amostra"] == ["ano", "cod_mun"]
    assert "ano" not in resultado
