import io

from scripts.validar_sinan_residencia_arquivo import analisar_csv, normalizar_codigo


def test_normalizar_codigo_municipal():
    assert normalizar_codigo("354340") == "354340"
    assert normalizar_codigo("3543402") == "354340"
    # Guatapará é 3518859 (prefixo SINAN 351885), não 3518800 (Guarulhos).
    assert normalizar_codigo("3518859") == "351885"
    assert normalizar_codigo("3518800") == "351880"
    assert normalizar_codigo("") is None


def test_agrega_residencia_notificador_sem_expor_linhas():
    csv_text = (
        "ID_MUNICIP;ID_MN_RESI;NU_ANO\n"
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


def test_guatapara_nao_confunde_codigo_de_guarulhos():
    csv_text = (
        "ID_MUNICIP;ID_MN_RESI;NU_ANO\n"
        "3518859;3518859;2024\n"
        "3518800;3518800;2024\n"
    )
    result = analisar_csv(io.StringIO(csv_text))
    assert result["por_municipio_residencia"]["Guatapará"] == 1
    assert result["por_municipio_notificador"]["Guatapará"] == 1


def test_audita_uf_residencia_e_notificacao():
    csv_text = (
        "ID_MUNICIP;ID_MN_RESI;SG_UF_NOT;SG_UF;NU_ANO\\n"
        "354340;354020;35;35;2024\\n"
        "354340;354020;35;SP;2024\\n"
        "330455;354020;33;33;2024\\n"
        "999999;354020;35;35;2024\\n"
        ";354020;35;35;2024\\n"
        "abc;354020;35;35;2024\\n"
    )
    result = analisar_csv(io.StringIO(csv_text))
    auditoria = result["auditoria_geografica"]
    assert auditoria["colunas_uf_encontradas"] == {"SG_UF": True, "SG_UF_NOT": True}
    residencia = auditoria["por_dimensao"]["residencia"]
    notificacao = auditoria["por_dimensao"]["notificacao"]
    assert residencia["uf_compativel"] == 5
    assert residencia["uf_divergente"] == 1
    assert notificacao["uf_compativel"] == 2
    assert notificacao["uf_divergente"] == 1
    assert notificacao["codigo_invalido"] == 1
    assert {"codigo": "999999", "registros": 1} in notificacao["codigos_validos_nao_mapeados_top_30"]


def test_normaliza_uf_por_codigo_ou_sigla():
    from scripts.validar_sinan_residencia_arquivo import normalizar_uf

    assert normalizar_uf("35") == "35"
    assert normalizar_uf("SP") == "35"
    assert normalizar_uf(" 35 ") == "35"
    assert normalizar_uf("XX") is None
