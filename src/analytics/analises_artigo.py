"""Reprodução auditável das três correlações descritas no artigo."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.estatisticas import correlacao_pearson
from src.analytics.indicadores import calcular_doses_por_100_habitantes, calcular_variacao_percentual
from src.analytics.consultas import MUNICIPIOS_ANALISE

RESULTADOS_ARTIGO = {
    "Correlação 1": {"r": -0.11, "p_value": 0.784},
    "Correlação 2": {"r": -0.17, "p_value": 0.658},
    "Correlação 3": {"r": 0.32, "p_value": 0.408},
}


def _ano_e_mes(casos: pd.DataFrame) -> pd.DataFrame:
    df = casos.copy()
    if "data_notificacao" in df:
        df["data_notificacao"] = pd.to_datetime(df["data_notificacao"], errors="coerce")
        df["ano_calculado"] = df["data_notificacao"].dt.year
        df["mes_calculado"] = df["data_notificacao"].dt.month
    else:
        df["ano_calculado"] = pd.to_numeric(df.get("ano_data"), errors="coerce")
        df["mes_calculado"] = np.nan
    return df


def _contagens_completas(casos: pd.DataFrame, anos: tuple[int, int],
                         somente_jan_abr: bool = False) -> pd.DataFrame:
    """Conta registros sem imputar zero quando um município/ano não aparece na fonte.

    Uma variação só é calculada quando há registros observados nos dois períodos.
    A ausência de linhas não permite distinguir, sozinha, zero real de cobertura
    incompleta da fonte; por isso, não é convertida automaticamente em zero.
    """
    recorte = casos[casos["ano_calculado"].isin(anos)].copy()
    if somente_jan_abr:
        recorte = recorte[recorte["mes_calculado"].between(1, 4)]
    if recorte.empty:
        return pd.DataFrame(columns=["municipio", *anos])
    contagens = (recorte.groupby(["municipio", "ano_calculado"]).size()
                 .unstack().reindex(columns=list(anos)))
    return contagens.dropna(subset=list(anos)).reset_index()


def _correlacionar(nome: str, dados: pd.DataFrame, x: str, y: str, status: str = "calculada") -> dict:
    resultado = correlacao_pearson(dados[x], dados[y]) if status == "calculada" else {
        "r": np.nan, "p_value": np.nan, "n": int(dados[[x, y]].dropna().shape[0]),
        "interpretacao": status,
    }
    referencia = RESULTADOS_ARTIGO[nome]
    status_final = status
    if status == "calculada" and (pd.isna(resultado["r"]) or pd.isna(resultado["p_value"])):
        status_final = "indefinida: amostra insuficiente ou variável sem variação"
    resultado.update({
        "analise": nome,
        "status": status_final,
        "r_artigo": referencia["r"],
        "p_artigo": referencia["p_value"],
        "diferenca_r": resultado["r"] - referencia["r"] if pd.notna(resultado["r"]) else np.nan,
        "diferenca_p": resultado["p_value"] - referencia["p_value"] if pd.notna(resultado["p_value"]) else np.nan,
        "n_municipios": resultado["n"],
    })
    return resultado


def _diagnostico_amostra(nome: str, municipios_esperados: set[str],
                         municipios_incluidos: set[str], observacao: str) -> dict:
    return {
        "analise": nome,
        "municipios_esperados": len(municipios_esperados),
        "municipios_incluidos": len(municipios_incluidos),
        "municipios_excluidos": len(municipios_esperados - municipios_incluidos),
        "excluidos": ", ".join(sorted(municipios_esperados - municipios_incluidos)),
        "criterio": observacao,
    }


def construir_analises_artigo(vacinacao: pd.DataFrame, casos: pd.DataFrame,
                               populacao: pd.DataFrame) -> dict:
    """Monta datasets e correlações sem converter períodos ausentes em zero.

    Os resultados usam registros SINAN disponíveis, não necessariamente casos
    confirmados. Municípios sem observações nos dois períodos de uma variação são
    excluídos dessa correlação e contabilizados no diagnóstico de amostra.
    """
    municipios = set(MUNICIPIOS_ANALISE)
    pop = (populacao[populacao["municipio"].isin(municipios)]
           [["municipio", "populacao"]].drop_duplicates("municipio"))
    vac = vacinacao[vacinacao["municipio"].isin(municipios)].copy()
    vac["ano"] = pd.to_numeric(vac["ano"], errors="coerce")
    vac["mes_numero"] = pd.to_numeric(vac["mes_numero"], errors="coerce")
    vac["doses"] = pd.to_numeric(vac["doses"], errors="coerce")

    casos_df = _ano_e_mes(casos)
    casos_df = casos_df[casos_df["municipio"].isin(municipios)].copy()
    casos_df["ano_calculado"] = pd.to_numeric(casos_df["ano_calculado"], errors="coerce")
    casos_df["mes_calculado"] = pd.to_numeric(casos_df["mes_calculado"], errors="coerce")

    anual = _contagens_completas(casos_df, (2023, 2024))
    if anual.empty:
        anual = pd.DataFrame(columns=["municipio", 2023, 2024])
    anual["variacao_2023_2024_pct"] = calcular_variacao_percentual(anual[2023], anual[2024])

    jan_abr = _contagens_completas(casos_df, (2023, 2025), somente_jan_abr=True)
    if jan_abr.empty:
        jan_abr = pd.DataFrame(columns=["municipio", 2023, 2025])
    jan_abr["variacao_2023_2025_jan_abr_pct"] = calcular_variacao_percentual(jan_abr[2023], jan_abr[2025])

    doses_2024 = (vac[vac["ano"] == 2024].groupby("municipio", as_index=False)["doses"]
                  .sum(min_count=1).rename(columns={"doses": "doses_2024"}))
    taxa_2024 = doses_2024.merge(pop, on="municipio", how="left")
    taxa_2024["taxa_doses_2024_pct"] = calcular_doses_por_100_habitantes(
        taxa_2024["doses_2024"], taxa_2024["populacao"])

    corr1_df = taxa_2024.merge(
        anual[["municipio", "variacao_2023_2024_pct"]], on="municipio", how="inner")
    corr2_df = taxa_2024.merge(
        jan_abr[["municipio", "variacao_2023_2025_jan_abr_pct"]], on="municipio", how="inner")

    corr1 = _correlacionar("Correlação 1", corr1_df, "taxa_doses_2024_pct", "variacao_2023_2024_pct")
    corr2 = _correlacionar("Correlação 2", corr2_df, "taxa_doses_2024_pct", "variacao_2023_2025_jan_abr_pct")

    # Exige cobertura mensal por município: 12 meses em 2024 e janeiro-abril de 2025.
    meses_2025 = sorted(vac.loc[vac["ano"] == 2025, "mes_numero"].dropna().astype(int).unique().tolist())
    tem_jan_abr_2025 = all(m in meses_2025 for m in range(1, 5))
    meses_por_municipio = (vac[vac["ano"].isin([2024, 2025])]
                           .dropna(subset=["mes_numero"])
                           .groupby(["municipio", "ano"])["mes_numero"].agg(
                               lambda s: set(s.astype(int).tolist())))
    municipios_vac_completa = set()
    for municipio in municipios:
        meses_2024_mun = meses_por_municipio.get((municipio, 2024), set())
        meses_2025_mun = meses_por_municipio.get((municipio, 2025), set())
        if set(range(1, 13)).issubset(meses_2024_mun) and set(range(1, 5)).issubset(meses_2025_mun):
            municipios_vac_completa.add(municipio)

    casos_2025_jan_abr = (casos_df[(casos_df["ano_calculado"] == 2025) &
                                   casos_df["mes_calculado"].between(1, 4)]
                          .groupby("municipio").size().rename("registros_2025_jan_abr").reset_index())
    doses_acumuladas = vac[
        (vac["municipio"].isin(municipios_vac_completa)) &
        (((vac["ano"] == 2024) & vac["mes_numero"].between(1, 12)) |
         ((vac["ano"] == 2025) & vac["mes_numero"].between(1, 4)))
    ]
    doses_acumuladas = (doses_acumuladas.groupby("municipio", as_index=False)["doses"]
                        .sum(min_count=1)
                        .rename(columns={"doses": "doses_acumuladas_2024_2025_jan_abr"}))
    corr3_df = doses_acumuladas.merge(pop, on="municipio", how="left").merge(
        casos_2025_jan_abr, on="municipio", how="inner")
    corr3_df["taxa_doses_acumulada_pct"] = calcular_doses_por_100_habitantes(
        corr3_df["doses_acumuladas_2024_2025_jan_abr"], corr3_df["populacao"])
    if tem_jan_abr_2025 and municipios_vac_completa:
        corr3 = _correlacionar("Correlação 3", corr3_df, "taxa_doses_acumulada_pct", "registros_2025_jan_abr")
    else:
        motivo = ("indisponível: faltam meses de vacinação de janeiro a abril de 2025"
                  if not tem_jan_abr_2025 else
                  "indisponível: nenhum município tem cobertura mensal completa de vacinação em 2024 e jan-abr/2025")
        corr3 = _correlacionar(
            "Correlação 3", corr3_df, "taxa_doses_acumulada_pct", "registros_2025_jan_abr",
            status=motivo,
        )

    diagnosticos = pd.DataFrame([
        _diagnostico_amostra(
            "Correlação 1", municipios,
            set(corr1_df["municipio"].dropna()),
            "Somente municípios com registros SINAN observados em 2023 e 2024 e taxa de doses calculável.",
        ),
        _diagnostico_amostra(
            "Correlação 2", municipios,
            set(corr2_df["municipio"].dropna()),
            "Somente municípios com registros observados em jan-abr/2023 e jan-abr/2025 e taxa de doses calculável.",
        ),
        _diagnostico_amostra(
            "Correlação 3", municipios,
            set(corr3_df["municipio"].dropna()),
            "Somente municípios com todos os meses de vacinação de 2024 e jan-abr/2025, população válida e registros SINAN observados em jan-abr/2025.",
        ),
    ])

    return {
        "correlacoes": pd.DataFrame([corr1, corr2, corr3]),
        "correlacao_1_dados": corr1_df,
        "correlacao_2_dados": corr2_df,
        "correlacao_3_dados": corr3_df,
        "casos_anuais": anual,
        "casos_jan_abr": jan_abr,
        "meses_vacinacao_2025": meses_2025,
        "tem_jan_abr_vacinacao_2025": tem_jan_abr_2025,
        "diagnosticos_amostra": diagnosticos,
    }
