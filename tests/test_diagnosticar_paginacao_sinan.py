import scripts.diagnosticar_paginacao_sinan as diagnostico_sinan
from scripts.diagnosticar_paginacao_sinan import (
    codigo_residencia,
    diagnosticar,
    lista_registros,
    resumir_linhas,
)
import pytest


def test_codigo_residencia_normaliza_codigo_ibge_de_seis_ou_sete_digitos():
    assert codigo_residencia({"id_mn_resi": "354340"}) == "354340"
    assert codigo_residencia({"id_mn_resi": 3543402}) == "354340"


def test_codigo_residencia_nao_confunde_municipio_notificador():
    assert codigo_residencia({"id_municip": "354340"}) is None


def test_resumir_linhas_conta_apenas_residencia_dos_municipios_alvo():
    resumo = resumir_linhas([
        {"id_mn_resi": "354340"},
        {"id_mn_resi": "354340"},
        {"id_mn_resi": "320130"},
        {"id_municip": "354340"},
    ])
    assert resumo["linhas_lidas"] == 4
    assert resumo["linhas_por_municipio_residencia_alvo"]["Ribeirão Preto"] == 2
    assert resumo["linhas_sem_codigo_residencia"] == 1


def test_lista_registros_aceita_lista_na_raiz():
    assert lista_registros([{"id_mn_resi": "354340"}]) == [
        {"id_mn_resi": "354340"}
    ]


def test_lista_registros_aceita_envelope_aninhado():
    payload = {"data": {"results": [{"id_mn_resi": "354340"}]}}
    assert lista_registros(payload) == [{"id_mn_resi": "354340"}]


def test_lista_registros_aceita_lista_vazia():
    assert lista_registros({"data": []}) == []


def test_lista_registros_informa_chaves_sem_expor_registros():
    with pytest.raises(ValueError, match="Chaves recebidas.*message"):
        lista_registros({"message": "Parâmetro inválido", "code": 400})


def test_lista_registros_aceita_envelope_especifico_da_api_sinan():
    payload = {"dengue": [{"id_mn_resi": "354340"}]}
    assert lista_registros(payload) == [{"id_mn_resi": "354340"}]


def test_lista_registros_aceita_envelope_dengue_vazio():
    assert lista_registros({"dengue": []}) == []



def test_diagnosticar_offset_avanca_pelo_tamanho_da_pagina(monkeypatch):
    offsets = []

    class Response:
        def __init__(self, rows):
            self.rows = rows

        def raise_for_status(self):
            pass

        def json(self):
            return {"dengue": self.rows}

    class Session:
        def __init__(self):
            self.headers = {}

        def get(self, url, params, timeout):
            offsets.append(params["offset"])
            paginas = {
                0: [{"id_mn_resi": "320530"}, {"id_mn_resi": "320500"}],
                2: [{"id_mn_resi": "354340"}, {"id_mn_resi": "354340"}],
                4: [],
            }
            return Response(paginas[params["offset"]])

    monkeypatch.setattr(diagnostico_sinan.requests, "Session", Session)
    resultado = diagnosticar(2024, max_pages=5, page_size=2, pausa=0)

    assert offsets == [0, 2, 4]
    assert resultado["registros_lidos"] == 4
    assert resultado["varredura_completa"] is True
    assert resultado["registros_por_municipio_residencia_alvo"]["Ribeirão Preto"] == 2
