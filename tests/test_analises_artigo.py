import pandas as pd

from src.analytics.analises_artigo import construir_analises_artigo


def test_analises_artigo_calcula_variacoes_com_janeiro_a_abril():
    municipios = ["Barrinha", "Cravinhos", "Guatapará"]
    populacao = pd.DataFrame({"municipio": municipios, "populacao": [1000, 1000, 1000]})
    vacinacao = pd.DataFrame([
        {"municipio": m, "ano": 2024, "mes_numero": mes, "doses": 10 * (i + 1)}
        for i, m in enumerate(municipios) for mes in range(1, 13)
    ] + [
        {"municipio": m, "ano": 2025, "mes_numero": mes, "doses": 2 * (i + 1)}
        for i, m in enumerate(municipios) for mes in range(1, 5)
    ])
    casos = pd.DataFrame([
        {"municipio": m, "data_notificacao": f"2023-{mes:02d}-10"}
        for i, m in enumerate(municipios) for mes in range(1, 13) for _ in range(10 + i)
    ] + [
        {"municipio": m, "data_notificacao": f"2024-{mes:02d}-10"}
        for i, m in enumerate(municipios) for mes in range(1, 13) for _ in range(20 + i)
    ] + [
        {"municipio": m, "data_notificacao": f"2025-{mes:02d}-10"}
        for i, m in enumerate(municipios) for mes in range(1, 5) for _ in range(15 + i)
    ])

    resultado = construir_analises_artigo(vacinacao, casos, populacao)
    assert len(resultado["correlacoes"]) == 3
    assert resultado["correlacoes"].iloc[0]["analise"] == "Correlação 1"
    assert resultado["correlacoes"].iloc[1]["analise"] == "Correlação 2"
    assert resultado["correlacoes"].iloc[2]["status"] == "calculada"
    assert resultado["tem_jan_abr_vacinacao_2025"] is True
    assert resultado["correlacao_1_dados"]["variacao_2023_2024_pct"].notna().all()
    assert resultado["correlacao_2_dados"]["variacao_2023_2025_jan_abr_pct"].notna().all()


def test_analises_artigo_calcula_correlacao_3_com_janeiro_a_abril():
    municipios = ["Barrinha", "Cravinhos", "Guatapará"]
    populacao = pd.DataFrame({"municipio": municipios, "populacao": [1000, 1000, 1000]})
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

    resultado = construir_analises_artigo(vacinacao, casos, populacao)
    corr3 = resultado["correlacoes"].iloc[2]
    assert resultado["tem_jan_abr_vacinacao_2025"] is True
    assert corr3["status"] == "calculada"
    assert pd.notna(corr3["r"])
