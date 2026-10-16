"""Consultas de leitura usadas pelo dashboard para acessar o SQLite."""
from __future__ import annotations

import pandas as pd

from src.database.conexao import DB_PATH, conectar


def _ler(sql: str, params: tuple = (), db_path=None) -> pd.DataFrame:
    with conectar(db_path or DB_PATH) as conexao:
        return pd.read_sql_query(sql, conexao, params=params)


def consultar_populacao(db_path=None) -> pd.DataFrame:
    """População por município, com nomes compatíveis com a camada analítica."""
    return _ler(
        "SELECT municipio_original, municipio, populacao FROM populacao_municipio ORDER BY municipio",
        db_path=db_path,
    )


def consultar_casos(db_path=None) -> pd.DataFrame:
    """Registros SINAN combinados, mantendo ano real e ano do arquivo de origem."""
    df = _ler(
        "SELECT municipio_original, municipio, data_notificacao, idade_anos, sexo, "
        "arquivo_ano, ano_data, diverge_ano_arquivo FROM registros_sinan",
        db_path=db_path,
    )
    if not df.empty:
        df["data_notificacao"] = pd.to_datetime(df["data_notificacao"], errors="coerce")
        df["diverge_ano_arquivo"] = df["diverge_ano_arquivo"].astype(bool)
    return df


def consultar_vacinacao_mensal(db_path=None) -> pd.DataFrame:
    """Doses por município, ano e mês em formato longo."""
    return _ler(
        "SELECT municipio, municipio_original, ano, mes, mes_numero, doses "
        "FROM vacinacao_mensal ORDER BY ano, mes_numero, municipio",
        db_path=db_path,
    )


def consultar_vacinacao_categoria(categoria: str, db_path=None) -> pd.DataFrame:
    """Lê doses por sexo ou faixa etária a partir da tabela correspondente."""
    configuracao = {
        "sexo": ("vacinacao_sexo", "sexo_categoria"),
        "faixaetaria": ("vacinacao_faixa_etaria", "faixa_etaria"),
    }
    if categoria not in configuracao:
        raise ValueError("categoria deve ser 'sexo' ou 'faixaetaria'.")
    tabela, coluna = configuracao[categoria]
    return _ler(
        f"SELECT municipio, municipio_original, ano, {coluna} AS categoria, doses "
        f"FROM {tabela} ORDER BY ano, municipio, categoria",
        db_path=db_path,
    )


def consultar_metadados(db_path=None) -> dict[str, str]:
    """Retorna metadados da última carga realizada."""
    df = _ler("SELECT chave, valor FROM metadados_carga", db_path=db_path)
    return dict(zip(df["chave"], df["valor"])) if not df.empty else {}
