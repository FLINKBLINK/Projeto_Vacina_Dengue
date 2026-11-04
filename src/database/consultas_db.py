"""Consultas de leitura usadas pelo dashboard para acessar o SQLite."""
from __future__ import annotations

import json

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


def consultar_execucoes_oficiais(db_path=None) -> pd.DataFrame:
    """Retorna o histórico do ETL oficial quando suas tabelas existem.

    O pipeline oficial é opcional e independente da carga que alimenta o painel;
    um banco sem essas tabelas retorna um quadro vazio.
    """
    with conectar(db_path or DB_PATH) as conexao:
        existe = conexao.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='oficiais_execucoes'"
        ).fetchone()
        if existe is None:
            return pd.DataFrame(columns=[
                "fonte", "ano_referencia", "iniciado_em_utc", "finalizado_em_utc",
                "paginas", "registros_recebidos", "registros_regiao", "status", "detalhe",
            ])
        colunas = {row[1] for row in conexao.execute("PRAGMA table_info(oficiais_execucoes)")}
        tem_ano = "ano_referencia" in colunas
        campos = "fonte, " + ("ano_referencia, " if tem_ano else "NULL AS ano_referencia, ") + (
            "iniciado_em_utc, finalizado_em_utc, paginas, registros_recebidos, "
            "registros_regiao, status, detalhe"
        )
        return pd.read_sql_query(
            f"SELECT {campos} FROM oficiais_execucoes ORDER BY id DESC", conexao
        )


def consultar_contagens_oficiais(db_path=None) -> pd.DataFrame:
    """Conta registros oficiais brutos por fonte e ano, se a tabela existir."""
    with conectar(db_path or DB_PATH) as conexao:
        existe = conexao.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='oficiais_registros'"
        ).fetchone()
        if existe is None:
            return pd.DataFrame(columns=["fonte", "ano_referencia", "registros"])
        return pd.read_sql_query(
            "SELECT fonte, ano_referencia, COUNT(*) AS registros "
            "FROM oficiais_registros GROUP BY fonte, ano_referencia ORDER BY fonte, ano_referencia",
            conexao,
        )


def consultar_casos_oficiais(db_path=None) -> pd.DataFrame:
    """Converte o SINAN oficial bruto em colunas analíticas usadas pelo dashboard.

    A extração oficial é filtrada por município de residência. Os campos clínicos
    não são inferidos: idade só é preenchida quando existe uma coluna explícita
    em anos completos (IDADE_ANOS). NU_IDADE_N não é convertido sem validar seu
    domínio/codificação.
    """
    colunas_saida = [
        "municipio_original", "municipio", "data_notificacao", "idade_anos",
        "sexo", "arquivo_ano", "ano_data", "diverge_ano_arquivo",
    ]
    with conectar(db_path or DB_PATH) as conexao:
        existe = conexao.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='oficiais_registros'"
        ).fetchone()
        if existe is None:
            return pd.DataFrame(columns=colunas_saida)
        colunas = {
            row[1] for row in conexao.execute("PRAGMA table_info(oficiais_registros)")
        }
        if not {"fonte", "municipio", "ano_referencia", "registro_json"}.issubset(colunas):
            return pd.DataFrame(columns=colunas_saida)
        registros = pd.read_sql_query(
            """SELECT municipio, ano_referencia, registro_json
               FROM oficiais_registros
               WHERE fonte='sinan_dengue'
               ORDER BY ano_referencia, chave_registro""",
            conexao,
        )

    if registros.empty:
        return pd.DataFrame(columns=colunas_saida)

    def obter(row: dict, *nomes):
        por_nome = {str(k).strip().upper(): v for k, v in row.items()}
        for nome in nomes:
            valor = por_nome.get(nome.upper())
            if valor not in (None, ""):
                return valor
        return None

    saida = []
    for registro in registros.itertuples(index=False):
        try:
            bruto = json.loads(registro.registro_json)
        except (TypeError, ValueError):
            continue
        data_raw = obter(bruto, "DT_NOTIFIC", "DATA_NOTIFICACAO")
        data = pd.to_datetime(data_raw, errors="coerce", dayfirst=True)
        ano_arquivo = pd.to_numeric(registro.ano_referencia, errors="coerce")
        ano_data = data.year if pd.notna(data) else pd.NA
        municipio = str(registro.municipio or "").strip()
        municipio_original = obter(bruto, "NM_MN_RESI", "NM_MUNICIP", "MUNICIPIO") or municipio
        idade = obter(bruto, "IDADE_ANOS")
        saida.append({
            "municipio_original": str(municipio_original),
            "municipio": municipio,
            "data_notificacao": data,
            "idade_anos": pd.to_numeric(idade, errors="coerce"),
            "sexo": obter(bruto, "CS_SEXO", "SEXO"),
            "arquivo_ano": int(ano_arquivo) if pd.notna(ano_arquivo) else pd.NA,
            "ano_data": ano_data,
            "diverge_ano_arquivo": bool(
                pd.notna(ano_data) and pd.notna(ano_arquivo) and int(ano_data) != int(ano_arquivo)
            ),
        })

    resultado = pd.DataFrame(saida, columns=colunas_saida)
    if not resultado.empty:
        resultado["data_notificacao"] = pd.to_datetime(
            resultado["data_notificacao"], errors="coerce"
        )
        resultado["diverge_ano_arquivo"] = resultado["diverge_ano_arquivo"].astype(bool)
    return resultado
