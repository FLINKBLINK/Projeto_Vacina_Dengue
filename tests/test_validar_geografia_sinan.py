from scripts.validar_geografia_sinan import contar_codigos, extrair_registros, resumir_resposta


def test_extrair_registros_envelope_dengue():
    assert extrair_registros({"dengue": [{"id_mn_resi": "354340"}]}) == [
        {"id_mn_resi": "354340"}
    ]


def test_resumo_geografico_agrega_sem_expor_linhas():
    resultado = resumir_resposta([
        {"id_municip": "354340", "id_mn_resi": "354340", "dt_notific": "2024-01-01"},
        {"id_municip": "354340", "id_mn_resi": "355150", "dt_notific": "2024-01-02"},
    ])
    assert resultado["registros_na_amostra"] == 2
    assert resultado["frequencias_id_municip"] == {"354340": 2}
    assert resultado["frequencias_id_mn_resi"] == {"354340": 1, "355150": 1}
    assert "dt_notific" not in resultado
    assert "registros" not in resultado


def test_contar_codigos_ignora_valores_vazios():
    assert contar_codigos([{"id_mn_resi": None}, {"id_mn_resi": ""}, {"id_mn_resi": 354340}], "id_mn_resi") == {
        "354340": 1
    }
