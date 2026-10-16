from scripts.diagnosticar_paginacao_sinan import codigo_residencia, resumir_linhas


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
