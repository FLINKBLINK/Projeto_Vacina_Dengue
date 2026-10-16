from scripts.diagnosticar_paginacao_sinan import (
    codigo_residencia,
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
