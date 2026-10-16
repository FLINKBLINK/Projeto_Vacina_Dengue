"""Leitura e padronização das planilhas de origem."""
from __future__ import annotations
import unicodedata
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIRS = (ROOT / "data" / "raw", ROOT)
ARQUIVOS = {"populacao": "IBGE_TRATADO.xlsx", "vacinacao": "DADOS_EXTRAIDOS.xlsx",
            "sinan_2023": "SINAN_2023.xlsx", "sinan_2024": "SINAN_2024.xlsx", "sinan_2025": "SINAN_2025.xlsx"}
MUNICIPIOS_ANALISE = ["Ribeirão Preto", "Sertãozinho", "Cravinhos", "Jardinópolis", "Pradópolis", "Pontal", "Serrana", "Guatapará", "Barrinha"]
BRODOWSKI = "Brodowski"

def localizar_arquivo(nome: str) -> Path | None:
    for pasta in DATA_DIRS:
        caminho = pasta / nome
        if caminho.exists():
            return caminho
    return None

def arquivos_ausentes() -> list[str]:
    return [nome for nome in ARQUIVOS.values() if localizar_arquivo(nome) is None]

def normalizar_texto(valor) -> str:
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.strip().upper().replace("_", " ").split())

def normalizar_municipio(valor) -> str:
    chave = normalizar_texto(valor).replace("(SP)", "").strip()
    mapa = {"RIBEIRAO": "Ribeirão Preto", "RIBEIRAO PRETO": "Ribeirão Preto",
            "SERTAOZINHO": "Sertãozinho", "CRAVINHOS": "Cravinhos", "CRAVINHHOS": "Cravinhos",
            "JARDINOPOLIS": "Jardinópolis", "PRADOPOLIS": "Pradópolis", "PONTAL": "Pontal",
            "SERRANA": "Serrana", "BRODOWSKI": "Brodowski", "GUATAPARA": "Guatapará", "BARRINHA": "Barrinha"}
    return mapa.get(chave, str(valor).strip())

def carregar_excel(nome: str, sheet_name=0):
    caminho = localizar_arquivo(nome)
    if caminho is None:
        raise FileNotFoundError(f"Arquivo não encontrado: {nome}. Coloque-o em data/raw/ ou na raiz.")
    return pd.read_excel(caminho, sheet_name=sheet_name)

def carregar_populacao() -> pd.DataFrame:
    df = carregar_excel(ARQUIVOS["populacao"], sheet_name="Total")
    col_mun = next((c for c in df.columns if "munic" in str(c).lower()), None)
    col_valor = next((c for c in df.columns if str(c).strip().lower() == "total"), None)
    if col_mun is None or col_valor is None:
        raise ValueError("A aba 'Total' do IBGE precisa ter uma coluna de município e uma coluna 'Total'.")
    out = df[[col_mun, col_valor]].copy()
    out.columns = ["municipio_original", "populacao"]
    out["municipio"] = out["municipio_original"].map(normalizar_municipio)
    out["populacao"] = pd.to_numeric(out["populacao"], errors="coerce")
    return out

def carregar_casos() -> pd.DataFrame:
    partes = []
    for chave, ano_arquivo in [("sinan_2023", 2023), ("sinan_2024", 2024), ("sinan_2025", 2025)]:
        caminho = localizar_arquivo(ARQUIVOS[chave])
        if caminho is None:
            continue
        df = pd.read_excel(caminho)
        mapa = {str(c).strip().upper(): c for c in df.columns}
        col_mun, col_data = mapa.get("NM_MUNICIP"), mapa.get("DT_NOTIFIC")
        col_idade, col_sexo = mapa.get("IDADE_ANOS"), mapa.get("CS_SEXO")
        if col_mun is None or col_data is None:
            raise ValueError(f"{ARQUIVOS[chave]} precisa conter NM_MUNICIP e DT_NOTIFIC.")
        out = pd.DataFrame({"municipio_original": df[col_mun],
                            "data_notificacao": pd.to_datetime(df[col_data], errors="coerce", dayfirst=True),
                            "idade_anos": df[col_idade] if col_idade else pd.NA,
                            "sexo": df[col_sexo] if col_sexo else pd.NA,
                            "arquivo_ano": ano_arquivo})
        out["municipio"] = out["municipio_original"].map(normalizar_municipio)
        out["ano_data"] = out["data_notificacao"].dt.year
        out["diverge_ano_arquivo"] = out["ano_data"].notna() & (out["ano_data"] != ano_arquivo)
        partes.append(out)
    if not partes:
        return pd.DataFrame(columns=["municipio", "data_notificacao", "idade_anos", "sexo", "arquivo_ano", "ano_data", "diverge_ano_arquivo"])
    return pd.concat(partes, ignore_index=True)

def carregar_vacinacao() -> dict[str, pd.DataFrame]:
    caminho = localizar_arquivo(ARQUIVOS["vacinacao"])
    if caminho is None:
        raise FileNotFoundError(f"Arquivo não encontrado: {ARQUIVOS['vacinacao']}")
    xls = pd.ExcelFile(caminho)
    return {aba: pd.read_excel(xls, sheet_name=aba) for aba in xls.sheet_names if aba.strip().lower() != "planilha1"}

def _mes_canonico(nome_coluna) -> str | None:
    """Reconhece nomes de meses em português, completos ou abreviados."""
    nome = normalizar_texto(nome_coluna).rstrip(".")
    aliases = {
        "JAN": "jan", "JANEIRO": "jan",
        "FEV": "fev", "FEVEREIRO": "fev",
        "MAR": "mar", "MARCO": "mar",
        "ABR": "abr", "ABRIL": "abr",
        "MAI": "mai", "MAIO": "mai",
        "JUN": "jun", "JUNHO": "jun",
        "JUL": "jul", "JULHO": "jul",
        "AGO": "ago", "AGOSTO": "ago",
        "SET": "set", "SETEMBRO": "set",
        "OUT": "out", "OUTUBRO": "out",
        "NOV": "nov", "NOVEMBRO": "nov",
        "DEZ": "dez", "DEZEMBRO": "dez",
    }
    # Aceita cabeçalhos como "Jan/2024" ou "Janeiro 2024", se houver ano no título.
    partes = nome.replace("/", " ").replace("-", " ").split()
    if partes and partes[-1].isdigit() and len(partes[-1]) in (2, 4):
        nome = " ".join(partes[:-1])
    return aliases.get(nome)


def preparar_vacinacao_mensal(abas: dict[str, pd.DataFrame], ano: int) -> pd.DataFrame:
    """Converte a aba anual em formato longo, reconhecendo meses completos e abreviados."""
    colunas_saida = ["municipio", "municipio_original", "mes", "doses", "ano"]
    chave = f"{ano}_ano"
    if chave not in abas:
        return pd.DataFrame(columns=colunas_saida)

    df = abas[chave].copy()
    if df.empty or len(df.columns) == 0:
        return pd.DataFrame(columns=colunas_saida)

    df = df.rename(columns={df.columns[0]: "municipio_original"})
    df["municipio"] = df["municipio_original"].map(normalizar_municipio)

    mapa_meses = {
        coluna: _mes_canonico(coluna)
        for coluna in df.columns
        if coluna not in ("municipio_original", "municipio")
        and _mes_canonico(coluna) is not None
    }
    if not mapa_meses:
        return pd.DataFrame(columns=colunas_saida)

    canonicos = list(mapa_meses.values())
    duplicados = sorted({mes for mes in canonicos if canonicos.count(mes) > 1})
    if duplicados:
        raise ValueError(
            "Há mais de uma coluna para o(s) mês(es): "
            + ", ".join(duplicados)
            + ". Verifique os cabeçalhos da aba "
            + chave
            + " para evitar somar doses duplicadas."
        )

    df = df.rename(columns=mapa_meses)
    colunas_mes = list(mapa_meses.values())
    longa = df.melt(
        id_vars=["municipio", "municipio_original"],
        value_vars=colunas_mes,
        var_name="mes",
        value_name="doses",
    )
    longa["doses"] = pd.to_numeric(longa["doses"], errors="coerce")
    longa["ano"] = ano
    return longa

def preparar_vacinacao_categoria(abas: dict[str, pd.DataFrame], ano: int, categoria: str) -> pd.DataFrame:
    """Converte abas por sexo ou faixa etária para formato longo."""
    if categoria not in ("sexo", "faixaetaria"):
        raise ValueError("categoria deve ser 'sexo' ou 'faixaetaria'.")
    chave = f"{ano}_{categoria}"
    if chave not in abas:
        return pd.DataFrame(columns=["municipio", "categoria", "doses", "ano"])
    df = abas[chave].copy()
    df = df.rename(columns={df.columns[0]: "municipio_original"})
    df["municipio"] = df["municipio_original"].map(normalizar_municipio)
    colunas = [
        c for c in df.columns
        if c not in ("municipio_original", "municipio")
        and str(c).strip().lower() not in ("categoria", "total", "municípios", "municipios")
    ]
    if not colunas:
        return pd.DataFrame(columns=["municipio", "categoria", "doses", "ano"])
    longa = df.melt(
        id_vars=["municipio", "municipio_original"],
        value_vars=colunas,
        var_name="categoria",
        value_name="doses",
    )
    longa["doses"] = pd.to_numeric(longa["doses"], errors="coerce")
    longa["ano"] = ano
    return longa
