from __future__ import annotations
import pandas as pd
import plotly.express as px
import streamlit as st
from src.analytics.consultas import ARQUIVOS, MUNICIPIOS_ANALISE, arquivos_ausentes
from src.database.carga import garantir_banco_atualizado
from src.database.consultas_db import consultar_casos, consultar_populacao, consultar_vacinacao_mensal, consultar_vacinacao_categoria
from src.database.conexao import DB_PATH
from src.analytics.indicadores import calcular_doses_por_100_habitantes
from src.analytics.estatisticas import correlacao_pearson

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
        for categoria, titulo in [("sexo", "Doses registradas por sexo"), ("faixaetaria", "Doses registradas por faixa etária")]:
            dados_categoria = consultar_vacinacao_categoria(categoria)
            dados_categoria = dados_categoria[dados_categoria["municipio"].isin(municipios_filtro)]
            if not dados_categoria.empty:
                resumo_categoria = dados_categoria.groupby(["ano", "categoria"], as_index=False)["doses"].sum(min_count=1)
                st.plotly_chart(px.bar(resumo_categoria, x="categoria", y="doses", color="ano", barmode="group",
                                       labels={"categoria": "Grupo", "doses": "Doses registradas", "ano": "Ano"},
                                       title=titulo), use_container_width=True)
    else:
        st.warning("A tabela mensal de vacinação ficou vazia. Confira se as abas 2024_ano/2025_ano existem e se os cabeçalhos dos meses estão em português; o carregador foi ajustado para aceitar nomes completos e abreviações. Se o aviso persistir, os cabeçalhos reais da planilha precisam ser inspecionados.")
except Exception as exc:
    st.warning(f"A parte de vacinação não pôde ser calculada: {exc}")

st.subheader("Correlação exploratória entre vacinação e registros")
st.write("Selecione separadamente o ano das doses e o ano dos registros. Esta visualização é uma exploração transversal entre municípios; não reproduz, por si só, as três correlações de variação temporal do artigo.")
if not vac.empty and not casos_brutos.empty:
    anos_vac = sorted(int(a) for a in vac["ano"].dropna().unique())
    anos_casos_corr = sorted(int(a) for a in casos_brutos["ano_data"].dropna().unique())
    csel1, csel2 = st.columns(2)
    ano_doses_corr = csel1.selectbox("Ano das doses", anos_vac, index=0 if 2024 in anos_vac else len(anos_vac)-1)
    ano_casos_corr = csel2.selectbox("Ano da data de notificação", anos_casos_corr, index=0 if 2024 in anos_casos_corr else len(anos_casos_corr)-1)
    doses_corr = vac[vac["ano"] == ano_doses_corr].groupby("municipio", as_index=False)["doses"].sum(min_count=1)
    casos_corr = casos_brutos[(casos_brutos["ano_data"] == ano_casos_corr) & casos_brutos["municipio"].isin(municipios_filtro)].groupby("municipio", as_index=False).size().rename(columns={"size": "registros"})
    corr_df = doses_corr.merge(casos_corr, on="municipio", how="inner").dropna(subset=["doses", "registros"])
    if len(corr_df) >= 3 and corr_df["doses"].nunique() > 1 and corr_df["registros"].nunique() > 1:
        resultado = correlacao_pearson(corr_df["doses"], corr_df["registros"])
        a, b, c = st.columns(3)
        a.metric("Pearson r", f"{resultado['r']:.3f}")
        b.metric("p-valor", f"{resultado['p_value']:.3f}")
        c.metric("n de municípios", str(resultado["n"]))
        st.caption(resultado["interpretacao"])
        st.plotly_chart(px.scatter(corr_df, x="doses", y="registros", text="municipio", labels={"doses": f"Doses registradas em {ano_doses_corr}", "registros": f"Registros SINAN em {ano_casos_corr}"}, title="Doses registradas versus registros SINAN por município"), use_container_width=True)
    else:
        st.info("A correlação exige pelo menos três municípios com valores válidos e variação nas duas variáveis.")
elif vac.empty:
    st.warning("Correlação não calculada: nenhuma dose mensal foi carregada do arquivo de vacinação. Confira a seção Vacinação e os cabeçalhos da planilha.")
elif casos_brutos.empty:
    st.warning("Correlação não calculada: não há registros SINAN carregados.")
else:
    st.info("Não foi possível calcular a correlação com os dados disponíveis. Confira os anos selecionados e se há pelo menos três municípios em comum com valores válidos e variação nas duas variáveis.")

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
