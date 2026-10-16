from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from src.analytics.consultas import ARQUIVOS, MUNICIPIOS_ANALISE, arquivos_ausentes
from src.database.carga import garantir_banco_atualizado
from src.database.consultas_db import consultar_casos, consultar_populacao, consultar_vacinacao_mensal, consultar_vacinacao_categoria
from src.database.conexao import DB_PATH
from src.analytics.indicadores import calcular_doses_por_100_habitantes
from src.analytics.estatisticas import correlacao_pearson
from src.analytics.indicadores import calcular_variacao_percentual
from src.analytics.analises_artigo import construir_analises_artigo

st.set_page_config(page_title="Vacina Dengue | Região de Ribeirão Preto", page_icon="🦟", layout="wide")
st.title("Vacinação contra a dengue e registros da doença")
st.caption("Região de Ribeirão Preto (SP) • análise exploratória • dados de origem sujeitos a validação")
with st.sidebar:
    st.header("Filtros")
    incluir_brodowski = st.checkbox("Incluir Brodowski na auditoria", value=False)
    st.caption("A análise principal exclui Brodowski, conforme justificativa descrita no artigo.")

ausentes = arquivos_ausentes()
if ausentes:
    st.warning("Faltam arquivos de dados. Envie as planilhas para a pasta data/raw/ ou para a raiz do repositório.")
    for arquivo in ausentes:
        st.write(f"- {arquivo}")
    st.info("O aplicativo não inventa valores nem cria resultados quando as planilhas não estão disponíveis.")
    st.stop()
try:
    with st.spinner("Verificando o banco SQLite e preparando as bases..."):
        carga_realizada = garantir_banco_atualizado()
    populacao = consultar_populacao()
    casos_brutos = consultar_casos()
    vac_banco = consultar_vacinacao_mensal()
except Exception as exc:
    st.error(f"Não foi possível preparar ou consultar o banco SQLite: {exc}")
    st.exception(exc)
    st.stop()

with st.sidebar:
    st.caption(f"Banco SQLite: {DB_PATH.name}")
    st.caption("As consultas do dashboard são realizadas no banco local do ambiente.")
if carga_realizada:
    st.success("Banco SQLite criado/atualizado a partir das planilhas de origem.")

municipios = sorted(populacao["municipio"].dropna().unique().tolist())
municipios_selecionados = municipios if incluir_brodowski else [m for m in MUNICIPIOS_ANALISE if m in municipios and m != "Brodowski"]
pop = populacao[populacao["municipio"].isin(municipios_selecionados)].copy()
casos = casos_brutos[casos_brutos["municipio"].isin(municipios_selecionados)].copy()
if casos.empty:
    st.warning("Não há registros SINAN para os municípios selecionados.")
    st.stop()
casos["ano"] = casos["data_notificacao"].dt.year
anos_disponiveis = sorted(int(a) for a in casos["ano"].dropna().unique())
with st.sidebar:
    anos_escolhidos = st.multiselect("Ano da data de notificação", anos_disponiveis, default=anos_disponiveis)
    municipios_filtro = st.multiselect("Municípios", municipios_selecionados, default=municipios_selecionados)
casos_f = casos[casos["ano"].isin(anos_escolhidos) & casos["municipio"].isin(municipios_filtro)].copy()
pop_f = pop[pop["municipio"].isin(municipios_filtro)].copy()
total_pop = pop_f["populacao"].sum(min_count=1)
c1, c2, c3 = st.columns(3)
c1.metric("População (IBGE)", f"{total_pop:,.0f}".replace(",", ".") if pd.notna(total_pop) else "—")
c2.metric("Registros SINAN no filtro", f"{len(casos_f):,}".replace(",", "."))
c3.metric("Municípios no filtro", str(casos_f["municipio"].nunique()))

st.subheader("Evolução dos registros por data de notificação")
if casos_f["data_notificacao"].notna().any():
    mensal = (casos_f.dropna(subset=["data_notificacao"])
              .assign(mes=lambda d: d["data_notificacao"].dt.to_period("M").dt.to_timestamp())
              .groupby("mes", as_index=False).size().rename(columns={"size": "registros"}))
    st.plotly_chart(px.line(mensal, x="mes", y="registros", markers=True, labels={"mes": "Mês", "registros": "Registros"}, title="Registros por mês de notificação"), use_container_width=True)
    por_mun = casos_f.groupby("municipio", as_index=False).size().rename(columns={"size": "registros"})
    st.plotly_chart(px.bar(por_mun.sort_values("registros", ascending=False), x="municipio", y="registros", labels={"municipio": "Município", "registros": "Registros"}, title="Registros por município"), use_container_width=True)
    # Resumos anuais e trimestrais para comparar com as visualizações descritas no artigo.
    casos_com_data = casos_f.dropna(subset=["data_notificacao"]).copy()
    casos_com_data["ano"] = casos_com_data["data_notificacao"].dt.year
    resumo_anual = casos_com_data.groupby("ano").size().rename("registros").reset_index()
    if not resumo_anual.empty:
        st.markdown("**Resumo anual e variação percentual**")
        resumo_anual = resumo_anual.sort_values("ano")
        resumo_anual["variacao_percentual"] = resumo_anual["registros"].pct_change() * 100
        st.dataframe(resumo_anual, use_container_width=True, hide_index=True)
    casos_com_data["trimestre"] = casos_com_data["data_notificacao"].dt.to_period("Q").astype(str)
    resumo_trimestral = casos_com_data.groupby("trimestre").size().rename("registros").reset_index()
    if not resumo_trimestral.empty:
        st.plotly_chart(px.bar(resumo_trimestral, x="trimestre", y="registros",
                               labels={"trimestre": "Trimestre", "registros": "Registros SINAN"},
                               title="Registros SINAN por trimestre"), use_container_width=True)
else:
    st.info("Não há datas de notificação válidas para os filtros atuais.")

st.subheader("Vacinação")
st.caption("A aba anual de 2025 disponível contém janeiro a abril; maio não consta na planilha auditada.")
vac = pd.DataFrame()
try:
    vac = vac_banco[vac_banco["municipio"].isin(municipios_filtro)].copy()
    if not vac.empty:
        resumo_vac = vac.groupby(["ano", "municipio"], as_index=False)["doses"].sum(min_count=1)
        st.plotly_chart(px.bar(resumo_vac, x="municipio", y="doses", color="ano", barmode="group", labels={"municipio": "Município", "doses": "Doses registradas", "ano": "Ano"}, title="Doses registradas por município e ano"), use_container_width=True)
        indicador = resumo_vac.merge(pop_f[["municipio", "populacao"]].drop_duplicates("municipio"), on="municipio", how="left")
        indicador["doses_por_100_hab"] = calcular_doses_por_100_habitantes(indicador["doses"], indicador["populacao"])
        st.caption("Doses por 100 habitantes é um indicador descritivo, não cobertura vacinal oficial nem percentual de pessoas únicas vacinadas.")
        st.dataframe(indicador, use_container_width=True, hide_index=True)
        resumo_taxa = indicador.groupby("ano", as_index=False)["doses_por_100_hab"].mean()
        resumo_taxa = resumo_taxa.rename(columns={"doses_por_100_hab": "média municipal de doses por 100 habitantes"})
        st.markdown("**Média municipal descritiva de doses por 100 habitantes**")
        st.dataframe(resumo_taxa, use_container_width=True, hide_index=True)

        dados_sexo = consultar_vacinacao_categoria("sexo")
        dados_sexo = dados_sexo[dados_sexo["municipio"].isin(municipios_filtro)].copy()
        if not dados_sexo.empty:
            resumo_sexo = dados_sexo.groupby(["ano", "categoria"], as_index=False)["doses"].sum(min_count=1)
            resumo_sexo["percentual_das_doses_no_ano"] = (
                resumo_sexo["doses"] / resumo_sexo.groupby("ano")["doses"].transform("sum") * 100
            )
            st.markdown("**Distribuição das doses por sexo**")
            st.dataframe(resumo_sexo, use_container_width=True, hide_index=True)
            st.plotly_chart(px.bar(resumo_sexo, x="categoria", y="percentual_das_doses_no_ano", color="ano",
                                   barmode="group", labels={"categoria": "Sexo", "percentual_das_doses_no_ano": "% das doses", "ano": "Ano"},
                                   title="Proporção das doses registradas por sexo"), use_container_width=True)

        dados_idade = consultar_vacinacao_categoria("faixaetaria")
        dados_idade = dados_idade[dados_idade["municipio"].isin(municipios_filtro)].copy()
        if not dados_idade.empty:
            resumo_idade_mun = dados_idade.groupby(["ano", "municipio", "categoria"], as_index=False)["doses"].sum(min_count=1)
            st.markdown("**Distribuição por faixa etária e município**")
            st.plotly_chart(px.box(resumo_idade_mun, x="categoria", y="doses", color="ano", points="all",
                                   labels={"categoria": "Faixa etária", "doses": "Doses por município", "ano": "Ano"},
                                   title="Distribuição municipal das doses por faixa etária"), use_container_width=True)
            st.dataframe(resumo_idade_mun, use_container_width=True, hide_index=True)
    else:
        st.warning("A tabela mensal de vacinação ficou vazia. Confira se as abas 2024_ano/2025_ano existem e se os cabeçalhos dos meses estão em português; o carregador foi ajustado para aceitar nomes completos e abreviações. Se o aviso persistir, os cabeçalhos reais da planilha precisam ser inspecionados.")
except Exception as exc:
    st.warning(f"A parte de vacinação não pôde ser calculada: {exc}")

st.subheader("Reprodução das três correlações do artigo")
st.write("As análises de 2025 usam somente janeiro a abril, conforme a disponibilidade atual das bases. Os valores publicados no artigo são mantidos como referência histórica, mas não são diretamente comparáveis quando o período foi ajustado. Os cálculos usam registros SINAN, não necessariamente casos confirmados.")
try:
    analises_artigo = construir_analises_artigo(vac_banco, casos_brutos, populacao)
    tabela_corr = analises_artigo["correlacoes"].copy()
    tabela_corr = tabela_corr[["analise", "status", "n_municipios", "r", "p_value", "r_artigo", "p_artigo", "diferenca_r", "diferenca_p"]]
    st.dataframe(tabela_corr, use_container_width=True, hide_index=True)
    if not analises_artigo["tem_jan_abr_vacinacao_2025"]:
        st.warning("A Correlação 3 não pode ser calculada porque faltam um ou mais meses entre janeiro e abril de 2025 na vacinação.")
    else:
        st.caption("A Correlação 3 usa vacinação acumulada de janeiro a dezembro de 2024 mais janeiro a abril de 2025, comparada aos registros SINAN de janeiro a abril de 2025.")

    opcoes_corr = {
        "Correlação 1 — doses 2024 × variação anual 2023–2024":
            ("correlacao_1_dados", "taxa_doses_2024_pct", "variacao_2023_2024_pct"),
        "Correlação 2 — doses 2024 × variação Jan–Abr 2023–2025":
            ("correlacao_2_dados", "taxa_doses_2024_pct", "variacao_2023_2025_jan_abr_pct"),
        "Correlação 3 — doses acumuladas × registros Jan–Abr 2025":
            ("correlacao_3_dados", "taxa_doses_acumulada_pct", "registros_2025_jan_abr"),
    }
    escolha_corr = st.selectbox("Visualizar dispersão por análise", list(opcoes_corr))
    chave_df, eixo_x, eixo_y = opcoes_corr[escolha_corr]
    df_corr = analises_artigo[chave_df].dropna(subset=[eixo_x, eixo_y]).copy()
    if escolha_corr.startswith("Correlação 3") and not analises_artigo["tem_jan_abr_vacinacao_2025"]:
        st.info("Gráfico da Correlação 3 omitido porque a base não contém todos os meses de janeiro a abril de 2025.")
    elif len(df_corr) >= 3 and df_corr[eixo_x].nunique() > 1 and df_corr[eixo_y].nunique() > 1:
        fig = px.scatter(df_corr, x=eixo_x, y=eixo_y, text="municipio",
                         labels={eixo_x: eixo_x.replace("_", " "), eixo_y: eixo_y.replace("_", " ")},
                         title=escolha_corr)
        import numpy as np
        x_obs = df_corr[eixo_x].to_numpy(dtype=float)
        y_obs = df_corr[eixo_y].to_numpy(dtype=float)
        coef = np.polyfit(x_obs, y_obs, 1)
        x_linha = np.linspace(float(x_obs.min()), float(x_obs.max()), 100)
        fig.add_scatter(x=x_linha, y=np.polyval(coef, x_linha), mode="lines",
                        name="Tendência linear", line={"width": 3})
        fig.update_traces(selector={"mode": "markers+text"}, textposition="top center")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Não há municípios suficientes com variação nos dois eixos para desenhar esta correlação.")

    p_plot = tabela_corr[["analise", "p_value", "p_artigo"]].melt(
        id_vars="analise", var_name="origem", value_name="p_value").dropna(subset=["p_value"])
    if not p_plot.empty:
        p_plot["origem"] = p_plot["origem"].map({"p_value": "Calculado com as bases atuais", "p_artigo": "Publicado no artigo"})
        fig_p = px.bar(p_plot, x="analise", y="p_value", color="origem", barmode="group",
                       labels={"analise": "Análise", "p_value": "p-valor", "origem": "Referência"},
                       title="Comparação dos p-valores calculados e publicados")
        fig_p.add_hline(y=0.05, line_dash="dash", line_color="red",
                        annotation_text="Limiar de significância (0,05)")
        st.plotly_chart(fig_p, use_container_width=True)
except Exception as exc:
    st.error(f"Não foi possível reproduzir as análises do artigo: {exc}")
    st.exception(exc)

st.subheader("Qualidade e limitações dos dados")
divergencias = casos_brutos[casos_brutos["diverge_ano_arquivo"]].copy()
q1, q2, q3 = st.columns(3)
q1.metric("Datas ausentes/inválidas", int(casos_brutos["data_notificacao"].isna().sum()))
q2.metric("Ano da data difere do arquivo", int(casos_brutos["diverge_ano_arquivo"].sum()))
q3.metric("Municípios nos arquivos SINAN", int(casos_brutos["municipio"].nunique()))
if not divergencias.empty:
    st.warning("Há registros cuja data não corresponde ao ano indicado no nome do arquivo. O painel usa o ano real da data e expõe esses registros para auditoria.")
    st.dataframe(divergencias[["municipio_original", "data_notificacao", "arquivo_ano", "ano_data"]].head(100), use_container_width=True, hide_index=True)
with st.expander("Ver resumo e limitações das fontes"):
    st.json(ARQUIVOS)
    st.write("Sem campo de classificação final no arquivo SINAN, as linhas são descritas como registros, não como casos confirmados.")
    st.write("Na auditoria inicial, a aba anual de vacinação de 2025 continha janeiro a abril, sem maio.")
    st.write("Doses/população não é cobertura vacinal oficial; doses não equivalem necessariamente a pessoas únicas vacinadas.")
