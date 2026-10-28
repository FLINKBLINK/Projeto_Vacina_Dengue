import pandas as pd

from src.analytics.analises_artigo import construir_analises_artigo


def _bases_sinteticas(municipios):
    populacao = pd.DataFrame({"municipio": municipios, "populacao": [1000] * len(municipios)})
    vacinacao = pd.DataFrame([
        {"municipio": m, "ano": ano, "mes_numero": mes, "doses": (i + 1) * mes}
        for i, m in enumerate(municipios)
        for ano, meses in [(2024, range(1, 13)), (2025, range(1, 5))]
        for mes in meses
    ])
    casos = pd.DataFrame([
        {"municipio": m, "data_notificacao": f"{ano}-{mes:02d}-10"}
        for i, m in enumerate(municipios)
        for ano, meses in [(2023, range(1, 13)), (2024, range(1, 13)), (2025, range(1, 5))]
        for mes in meses for _ in range((i + 1) * (mes + 1))
    ])
    return vacinacao, casos, populacao


def test_analises_artigo_calcula_variacoes_com_periodos_observados():
    municipios = ["Barrinha", "Cravinhos", "Guatapará"]
    vacinacao, casos, populacao = _bases_sinteticas(municipios)

    resultado = construir_analises_artigo(vacinacao, casos, populacao)

    assert len(resultado["correlacoes"]) == 3
    assert resultado["correlacoes"].iloc[0]["analise"] == "Correlação 1"
    assert resultado["correlacoes"].iloc[1]["analise"] == "Correlação 2"
    assert resultado["correlacoes"].iloc[2]["status"] == "calculada"
    assert resultado["tem_jan_abr_vacinacao_2025"] is True
    assert resultado["correlacao_1_dados"]["variacao_2023_2024_pct"].notna().all()
    assert resultado["correlacao_2_dados"]["variacao_2023_2025_jan_abr_pct"].notna().all()
    assert resultado["diagnosticos_amostra"]["municipios_incluidos"].tolist() == [3, 3, 3]


def test_analises_nao_imputa_zero_quando_ano_esta_ausente():
    municipios = ["Barrinha", "Cravinhos", "Guatapará"]
    vacinacao, casos, populacao = _bases_sinteticas(municipios)
    # Remover todas as observações de 2024 para Cravinhos não significa zero em 2024.
    casos = casos[~((casos["municipio"] == "Cravinhos") &
                    (casos["data_notificacao"].str.startswith("2024-")))]

    resultado = construir_analises_artigo(vacinacao, casos, populacao)

    corr1_municipios = set(resultado["correlacao_1_dados"]["municipio"])
    corr2_municipios = set(resultado["correlacao_2_dados"]["municipio"])
    assert "Cravinhos" not in corr1_municipios
    # A Correlação 2 compara jan-abr/2023 com jan-abr/2025, não o ano inteiro de 2024.
    assert "Cravinhos" in corr2_municipios
    diag = resultado["diagnosticos_amostra"].set_index("analise")
    assert diag.loc["Correlação 1", "municipios_excluidos"] >= 1


def test_correlacao_3_exige_cobertura_mensal_por_municipio():
    municipios = ["Barrinha", "Cravinhos", "Guatapará"]
    vacinacao, casos, populacao = _bases_sinteticas(municipios)
    # A presença global de janeiro-abril não garante cobertura mensal de cada município.
    vacinacao = vacinacao[~((vacinacao["municipio"] == "Cravinhos") &
                            (vacinacao["ano"] == 2025) &
                            (vacinacao["mes_numero"] == 3))]

    resultado = construir_analises_artigo(vacinacao, casos, populacao)

    assert resultado["tem_jan_abr_vacinacao_2025"] is True
    assert "Cravinhos" not in set(resultado["correlacao_3_dados"]["municipio"])
    diag = resultado["diagnosticos_amostra"].set_index("analise")
    assert "Cravinhos" in diag.loc["Correlação 3", "excluidos"]


def test_correlacao_3_fica_indisponivel_sem_meses_completos_por_municipio():
    municipios = ["Barrinha", "Cravinhos", "Guatapará"]
    vacinacao, casos, populacao = _bases_sinteticas(municipios)
    vacinacao = vacinacao[~((vacinacao["ano"] == 2024) & (vacinacao["mes_numero"] == 12))]

    resultado = construir_analises_artigo(vacinacao, casos, populacao)

    assert resultado["correlacoes"].iloc[2]["status"].startswith("indisponível")
    assert resultado["correlacao_3_dados"].empty


def test_correlacoes_1_e_2_exigem_ano_completo_de_vacinacao_2024():
    municipios = ["Barrinha", "Cravinhos", "Guatapará"]
    vacinacao, casos, populacao = _bases_sinteticas(municipios)
    # A ausência de um mês não pode ser escondida pela soma parcial anual.
    vacinacao = vacinacao[~((vacinacao["municipio"] == "Cravinhos") &
                            (vacinacao["ano"] == 2024) &
                            (vacinacao["mes_numero"] == 7))]

    resultado = construir_analises_artigo(vacinacao, casos, populacao)

    assert "Cravinhos" not in set(resultado["correlacao_1_dados"]["municipio"])
    assert "Cravinhos" not in set(resultado["correlacao_2_dados"]["municipio"])
    diag = resultado["diagnosticos_amostra"].set_index("analise")
    assert "Cravinhos" in diag.loc["Correlação 1", "excluidos"]
    assert "Cravinhos" in diag.loc["Correlação 2", "excluidos"]


def test_correlacao_2_exclui_municipio_sem_jan_abr_de_2025():
    municipios = ["Barrinha", "Cravinhos", "Guatapará"]
    vacinacao, casos, populacao = _bases_sinteticas(municipios)
    casos = casos[~((casos["municipio"] == "Cravinhos") &
                    (casos["data_notificacao"].str.startswith("2025-")))]

    resultado = construir_analises_artigo(vacinacao, casos, populacao)

    assert "Cravinhos" not in set(resultado["correlacao_2_dados"]["municipio"])
    diag = resultado["diagnosticos_amostra"].set_index("analise")
    assert "Cravinhos" in diag.loc["Correlação 2", "excluidos"]
