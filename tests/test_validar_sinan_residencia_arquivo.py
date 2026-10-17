import io

from scripts.validar_sinan_residencia_arquivo import analisar_csv, normalizar_codigo


def test_normalizar_codigo_municipal():
    assert normalizar_codigo("354340") == "354340"
    assert normalizar_codigo("3543402") == "354340"
    assert normalizar_codigo("") is None


def test_agrega_residencia_notificador_sem_expor_linhas():
    csv_text = (
        "ID_MUNIC;ID_MN_RESI;NU_ANO\n"
        "354340;354340;2024\n"
        "354340;354020;2024\n"
        "354020;354020;2024\n"
    )
    result = analisar_csv(io.StringIO(csv_text))
    assert result["registros_lidos_arquivo"] == 3
    assert result["registros_distintos_por_hash_exato"] == 3
    assert result["linhas_repetidas_por_hash_exato"] == 0
    assert result["por_municipio_residencia"]["Ribeirão Preto"] == 1
    assert result["por_municipio_residencia"]["Pontal"] == 2
    assert result["por_municipio_notificador"]["Ribeirão Preto"] == 2
    assert result["por_municipio_notificador"]["Pontal"] == 1
    assert result["cruzamento_notificador_residencia_alvo"] == [
        {"notificador": "Pontal", "residencia": "Pontal", "registros": 1},
        {"notificador": "Ribeirão Preto", "residencia": "Pontal", "registros": 1},
        {"notificador": "Ribeirão Preto", "residencia": "Ribeirão Preto", "registros": 1},
    ]
