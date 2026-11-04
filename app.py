from __future__ import annotations
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
from src.analytics.analises_artigo import construir_analises_artigo
from src.analytics.consultas import ARQUIVOS, MUNICIPIOS_ANALISE, arquivos_ausentes, localizar_arquivo
from src.database.carga import garantir_banco_atualizado
from src.database.conexao import DB_PATH
from src.database.consultas_db import (consultar_casos, consultar_contagens_oficiais, consultar_execucoes_oficiais, consultar_metadados, consultar_populacao, consultar_vacinacao_categoria, consultar_vacinacao_mensal)

st.set_page_config(page_title="Dengue em dados | Ribeirão Preto", page_icon="🦟", layout="wide")
st.markdown('<style>.stApp{background:#f7f9fc;color:#17324d}[data-testid="stSidebar"]{background:#edf3f8}[data-testid="stMetric"]{background:white;border:1px solid #dbe5ee;padding:14px 16px;border-radius:12px}h1,h2,h3{color:#17324d}</style>', unsafe_allow_html=True)

def fmt(x):
    return "—" if pd.isna(x) else f"{x:,.0f}".replace(",", ".")

def fmt_date(x):
    d = pd.to_datetime(x, errors="coerce", utc=True)
    return "—" if pd.isna(d) else d.strftime("%d/%m/%Y %H:%M UTC")

@st.cache_data(show_spinner=False)
def load(db, signature):
    return {"pop": consultar_populacao(db), "sinan": consultar_casos(db), "vac": consultar_vacinacao_mensal(db), "sexo": consultar_vacinacao_categoria("sexo", db), "idade": consultar_vacinacao_categoria("faixaetaria", db), "meta": consultar_metadados(db), "exec": consultar_execucoes_oficiais(db), "official": consultar_contagens_oficiais(db)}

def plot(fig, key):
    fig.update_layout(template="plotly_white", margin={"l": 10, "r": 10, "t": 55, "b": 10})
    st.plotly_chart(fig, use_container_width=True, key=key)

def overview(pop, sinan, vac, meta):
    st.title("Panorama regional")
    st.caption("Vacinação contra dengue e registros de notificação • região de Ribeirão Preto (SP)")
    cols=st.columns(4)
    cols[0].metric("População selecionada",fmt(pop.populacao.sum(min_count=1)))
    cols[1].metric("Registros SINAN",fmt(len(sinan)))
    cols[2].metric("Doses registradas",fmt(vac.doses.sum(min_count=1)))
    cols[3].metric("Municípios",fmt(len(set(pop.municipio)&set(sinan.municipio))))
    ds=sinan.data_notificacao.dropna()
    span=f"{ds.min():%d/%m/%Y} a {ds.max():%d/%m/%Y}" if not ds.empty else "sem datas válidas"
    years=sorted(vac.ano.dropna().astype(int).unique())
    st.caption(f"Período SINAN: {span} • anos de vacinação: {', '.join(map(str,years)) or 'sem dados'} • última carga: {fmt_date(meta.get('carregado_em_utc'))}")
    a,b=st.columns(2)
    if ds.empty: a.info("Sem datas válidas para a série SINAN.")
    else:
        m=sinan.dropna(subset=["data_notificacao"]).assign(mes=lambda d:d.data_notificacao.dt.to_period("M").dt.to_timestamp()).groupby("mes",as_index=False).size().rename(columns={"size":"registros"})
        plot(px.line(m,x="mes",y="registros",markers=True,labels={"mes":"Mês","registros":"Registros"},title="Evolução mensal SINAN"),"ov-sinan")
    if vac.empty: b.info("Sem doses mensais para exibir.")
    else:
        v=vac.groupby(["ano","mes_numero"],as_index=False).doses.sum(min_count=1)
        v["data"]=pd.to_datetime(dict(year=v.ano,month=v.mes_numero,day=1),errors="coerce")
        plot(px.line(v.dropna(subset=["data"]),x="data",y="doses",markers=True,labels={"data":"Mês","doses":"Doses"},title="Evolução mensal vacinação"),"ov-vac")
    sm=sinan.groupby("municipio",as_index=False).size().rename(columns={"size":"registros"})
    vm=vac.groupby("municipio",as_index=False).doses.sum(min_count=1)
    plot(px.bar(sm.merge(vm,on="municipio",how="outer"),x="municipio",y=["registros","doses"],barmode="group",labels={"municipio":"Município","value":"Quantidade","variable":"Indicador"},title="Comparação municipal"),"ov-mun")
    st.info("Doses não equivalem a pessoas únicas nem a cobertura oficial. Registros SINAN são notificações, não necessariamente casos confirmados.")

def vaccination(vac, sex, age):
    st.title("Vacinação")
    st.caption("Fonte: DADOS_EXTRAIDOS.xlsx • contagem de doses registradas.")
    if vac.empty: st.info("Sem dados de vacinação neste recorte."); return
    with st.expander("Filtros das distribuições por categoria", expanded=True):
        left, right = st.columns(2)
        sex_options = sorted(sex.categoria.dropna().unique()) if not sex.empty else []
        age_options = sorted(age.categoria.dropna().unique()) if not age.empty else []
        selected_sex = left.multiselect("Sexo", sex_options, default=sex_options)
        selected_age = right.multiselect("Faixa etária", age_options, default=age_options)
        st.caption("Sexo e faixa etária filtram apenas seus gráficos de distribuição; totais mensais usam a tabela agregada disponível e não são reestimados por essas categorias.")
    sex = sex[sex.categoria.isin(selected_sex)]
    age = age[age.categoria.isin(selected_age)]
    annual=vac.groupby(["ano","municipio"],as_index=False).doses.sum(min_count=1)
    l,r=st.columns(2)
    plot(px.bar(annual,x="municipio",y="doses",color="ano",barmode="group",labels={"municipio":"Município","doses":"Doses","ano":"Ano"},title="Doses por município e ano"),"vac-mun-ano")
    plot(px.bar(vac.groupby("ano",as_index=False).doses.sum(min_count=1),x="ano",y="doses",labels={"ano":"Ano","doses":"Doses"},title="Doses por ano"),"vac-ano")
    rank=annual.groupby("municipio",as_index=False).doses.sum(min_count=1).sort_values("doses")
    plot(px.bar(rank,x="doses",y="municipio",orientation="h",labels={"doses":"Doses","municipio":"Município"},title="Ranking municipal"),"vac-rank")
    if not sex.empty:
        st.subheader("Distribuição por sexo")
        s=sex.groupby(["ano","categoria"],as_index=False).doses.sum(min_count=1); s["percentual"]=s.doses/s.groupby("ano").doses.transform("sum")*100
        plot(px.bar(s,x="categoria",y="percentual",color="ano",barmode="group",labels={"categoria":"Categoria","percentual":"% das doses"},title="Doses por sexo"),"vac-sex")
    if not age.empty:
        st.subheader("Distribuição por faixa etária")
        a=age.groupby(["ano","categoria"],as_index=False).doses.sum(min_count=1)
        plot(px.bar(a,x="categoria",y="doses",color="ano",barmode="group",labels={"categoria":"Faixa etária","doses":"Doses"},title="Doses por faixa etária"),"vac-age")
    st.caption("Categorias permanecem separadas nas agregações. Ausência de linha não é tratada como zero.")
    st.dataframe(annual.sort_values(["ano","doses"],ascending=[False,False]),use_container_width=True,hide_index=True)

def epidemiology(sinan):
    st.title("Epidemiologia • SINAN")
    st.caption("Registros pela data de notificação. Sem classificação final validada, não são apresentados como casos confirmados. Sexo e idade da origem não são exibidos enquanto a validação de domínio não estiver integrada.")
    a,b,c=st.columns(3); a.metric("Registros",fmt(len(sinan))); b.metric("Datas ausentes/inválidas",fmt(sinan.data_notificacao.isna().sum())); c.metric("Municípios",fmt(sinan.municipio.nunique()))
    d=sinan.dropna(subset=["data_notificacao"]).copy()
    if not d.empty:
        d["mês"]=d.data_notificacao.dt.to_period("M").dt.to_timestamp(); m=d.groupby("mês",as_index=False).size().rename(columns={"size":"registros"})
        y=d.assign(ano=d.data_notificacao.dt.year).groupby("ano",as_index=False).size().rename(columns={"size":"registros"})
        l,r=st.columns(2); plot(px.line(m,x="mês",y="registros",markers=True,labels={"mês":"Mês","registros":"Registros"},title="Evolução mensal"),"epi-mes"); plot(px.bar(y,x="ano",y="registros",labels={"ano":"Ano","registros":"Registros"},title="Registros por ano"),"epi-ano")
    m=sinan.groupby("municipio",as_index=False).size().rename(columns={"size":"registros"}).sort_values("registros",ascending=False)
    plot(px.bar(m,x="municipio",y="registros",labels={"municipio":"Município","registros":"Registros"},title="Registros por município"),"epi-mun")
    div=sinan[sinan.diverge_ano_arquivo]
    if not div.empty: st.warning(f"{len(div):,} datas diferem do ano indicado no arquivo; ambas referências foram mantidas.".replace(",","."))
    with st.expander("Registros sem data ou com ano divergente"):
        st.dataframe(sinan[sinan.data_notificacao.isna()|sinan.diverge_ano_arquivo][["municipio_original","data_notificacao","arquivo_ano","ano_data","diverge_ano_arquivo"]],use_container_width=True,hide_index=True)

def statistics(vac,sinan,pop):
    st.title("Análise estatística")
    st.write("Pearson descreve associação linear entre variáveis agregadas. Correlação não demonstra causalidade nem eficácia individual.")
    r=construir_analises_artigo(vac,sinan,pop); corr=r["correlacoes"]
    st.dataframe(corr[["analise","status","n_municipios","r","p_value"]],use_container_width=True,hide_index=True,column_config={"analise":"Análise","status":"Situação","n_municipios":"Municípios (n)","r":st.column_config.NumberColumn("Pearson (r)",format="%.3f"),"p_value":st.column_config.NumberColumn("p-valor",format="%.4f")})
    st.caption("p-valor não mede magnitude nem importância prática da associação.")
    st.subheader("Referência publicada anteriormente")
    st.dataframe(corr[["analise","r_artigo","p_artigo"]].rename(columns={"analise":"Análise","r_artigo":"Pearson publicado","p_artigo":"p-valor publicado"}),use_container_width=True,hide_index=True)
    st.caption("Valores publicados são referências históricas, não resultados calculados com a base atual. Diferenças de período e amostra limitam a comparação.")
    opts={"Doses 2024 × variação 2023–2024":("correlacao_1_dados","taxa_doses_2024_pct","variacao_2023_2024_pct"),"Doses 2024 × variação jan–abr 2023–2025":("correlacao_2_dados","taxa_doses_2024_pct","variacao_2023_2025_jan_abr_pct"),"Doses acumuladas × registros jan–abr 2025":("correlacao_3_dados","taxa_doses_acumulada_pct","registros_2025_jan_abr")}
    label=st.selectbox("Dispersão",list(opts)); key,x,y=opts[label]; points=r[key].dropna(subset=[x,y])
    if len(points)>=3 and points[x].nunique()>1 and points[y].nunique()>1:
        fig=px.scatter(points,x=x,y=y,text="municipio",labels={x:x.replace("_"," "),y:y.replace("_"," ")},title=label)
        xv=points[x].to_numpy(dtype=float); yv=points[y].to_numpy(dtype=float); coef=np.polyfit(xv,yv,1); line=np.linspace(xv.min(),xv.max(),100)
        fig.add_scatter(x=line,y=np.polyval(coef,line),mode="lines",name="Tendência linear")
        plot(fig,"stats-scatter")
    else: st.info("Amostra insuficiente/incompleta ou sem variação para tendência.")
    st.subheader("Diagnóstico da amostra"); st.dataframe(r["diagnosticos_amostra"],use_container_width=True,hide_index=True)
    st.caption("Janelas metodológicas fixas do projeto; filtros gerais não alteram estes cálculos. Valores ausentes não são imputados como zero.")

def quality(sinan,vac):
    st.title("Qualidade dos dados")
    st.caption("Triagem do conjunto completo para os municípios selecionados; o filtro de ano não esconde pendências históricas.")
    miss=int(sinan.data_notificacao.isna().sum()); div=int(sinan.diverge_ano_arquivo.sum()); unk=int(sinan.municipio.isna().sum()+(sinan.municipio=="").sum())
    c=st.columns(3); c[0].metric("Datas ausentes/inválidas",fmt(miss)); c[1].metric("Ano diferente do arquivo",fmt(div)); c[2].metric("Município não identificado",fmt(unk))
    st.dataframe(pd.DataFrame([{"situação":"Pendência","ocorrência":"Data ausente/inválida","quantidade":miss,"impacto":"Exclui de séries temporais; mantém contagem total.","severidade":"Média"},{"situação":"Alerta","ocorrência":"Ano da data difere do arquivo","quantidade":div,"impacto":"Pode alterar agrupamento temporal; ambas referências mantidas.","severidade":"Média"},{"situação":"Inconclusiva","ocorrência":"Município não identificado","quantidade":unk,"impacto":"Pode impedir agrupamento municipal.","severidade":"A avaliar"}]),use_container_width=True,hide_index=True)
    with st.expander("Cobertura temporal observada"):
        st.write("Vacinação",vac.groupby("ano").mes_numero.agg(lambda x:", ".join(map(str,sorted(x.dropna().astype(int).unique())))).rename("meses disponíveis").reset_index())
        st.write("SINAN",sinan.groupby("arquivo_ano").agg(registros=("arquivo_ano","size"),datas_validas=("data_notificacao","count")).reset_index())
    st.info("Estas são triagens observáveis, não certificação integral da qualidade semântica ou geográfica. Nenhum registro é corrigido ou removido; auditorias detalhadas ficam nos scripts próprios.")

def sources(data):
    st.title("Fontes e atualização")
    rows=[]
    for label,name in ARQUIVOS.items():
        p=localizar_arquivo(name); rows.append({"arquivo":name,"uso":label,"situação":"Disponível" if p else "Ausente","alterado localmente":fmt_date(pd.Timestamp(p.stat().st_mtime,unit="s",tz="UTC")) if p else "—","caminho":str(p) if p else "—"})
    st.subheader("Fontes do dashboard"); st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    meta=data["meta"]; st.metric("Última carga das planilhas",fmt_date(meta.get("carregado_em_utc")))
    st.caption(f"SQLite: {DB_PATH} • esquema: {meta.get('versao_esquema','—')} • assinatura ETL: {meta.get('assinatura_fontes','—')}")
    st.subheader("ETL oficial independente")
    st.write("Registros brutos oficiais não alimentam automaticamente os indicadores. O painel não inicia downloads.")
    if data["exec"].empty: st.info("Este banco não tem histórico do ETL oficial. Cargas controladas são executadas por scripts/etl_fontes_oficiais.py.")
    else:
        st.dataframe(data["exec"],use_container_width=True,hide_index=True); st.subheader("Registros brutos por fonte"); st.dataframe(data["official"],use_container_width=True,hide_index=True)
    st.caption("Fontes: IBGE (população), SINAN (notificações) e planilhas locais (vacinação). PNI não é tratado como vacina dengue sem validação do imunobiológico.")

st.title("Dengue em dados")
st.caption("Projeto Vacina Dengue • Região de Ribeirão Preto (SP)")
missing=arquivos_ausentes()
if missing: st.error("Fontes obrigatórias ausentes; não são simulados resultados."); st.write(", ".join(missing)); st.stop()
try:
    carga=garantir_banco_atualizado(); stat=DB_PATH.stat(); data=load(str(DB_PATH),(stat.st_mtime_ns,stat.st_size))
except Exception as exc: st.error(f"Não foi possível preparar ou consultar o SQLite: {exc}"); st.stop()
if carga: st.toast("SQLite atualizado a partir das planilhas locais.",icon="✅")
pop0,sinan0,vac0=data["pop"],data["sinan"],data["vac"]
munis=sorted(pop0.municipio.dropna().unique()); default=[m for m in MUNICIPIOS_ANALISE if m in munis] or munis
years=sorted(set(sinan0.data_notificacao.dropna().dt.year.astype(int))|set(vac0.ano.dropna().astype(int)))
with st.sidebar:
    st.header("Navegação"); page=st.radio("Seção",["Visão geral","Vacinação","Epidemiologia / SINAN","Análise estatística","Qualidade dos dados","Fontes e atualização"],label_visibility="collapsed")
    st.divider(); st.subheader("Filtros"); selected_munis=st.multiselect("Municípios",munis,default=default); selected_years=st.multiselect("Ano",years,default=years); st.caption("SINAN usa ano da data de notificação; registros sem data permanecem visíveis para auditoria."); st.caption(f"SQLite local • {DB_PATH.name}")
pop=pop0[pop0.municipio.isin(selected_munis)].copy()
sinan=sinan0[sinan0.municipio.isin(selected_munis)].copy(); sinan["ano"]=sinan.data_notificacao.dt.year; sinan=sinan[sinan.ano.isin(selected_years)|sinan.data_notificacao.isna()]
vac=vac0[vac0.municipio.isin(selected_munis)&vac0.ano.isin(selected_years)].copy()
sex=data["sexo"][data["sexo"].municipio.isin(selected_munis)&data["sexo"].ano.isin(selected_years)]
age=data["idade"][data["idade"].municipio.isin(selected_munis)&data["idade"].ano.isin(selected_years)]
if page=="Visão geral": overview(pop,sinan,vac,data["meta"])
elif page=="Vacinação": vaccination(vac,sex,age)
elif page=="Epidemiologia / SINAN": epidemiology(sinan)
elif page=="Análise estatística": statistics(vac0,sinan0,pop0)
elif page=="Qualidade dos dados": quality(sinan0[sinan0.municipio.isin(selected_munis)],vac0[vac0.municipio.isin(selected_munis)])
else: sources(data)
