"""ETL das planilhas auditadas para o banco SQLite."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.analytics.consultas import (
    ARQUIVOS,
    carregar_casos,
    carregar_populacao,
    carregar_vacinacao,
    localizar_arquivo,
    preparar_vacinacao_categoria,
    preparar_vacinacao_mensal,
)
from src.database.conexao import DB_PATH, conectar, inicializar_esquema

MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
         "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
TABELAS_DADOS = (
    "populacao_municipio", "registros_sinan", "vacinacao_mensal",
    "vacinacao_sexo", "vacinacao_faixa_etaria",
)


def assinatura_fontes() -> str:
    """Cria assinatura a partir de nomes, tamanho e data de alteração das fontes."""
    itens = []
    for nome in ARQUIVOS.values():
        caminho = localizar_arquivo(nome)
        if caminho is None:
            raise FileNotFoundError(f"Fonte obrigatória ausente: {nome}")
        stat = caminho.stat()
        itens.append(f"{nome}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("|".join(itens).encode("utf-8")).hexdigest()


def banco_precisa_atualizar(db_path: str | Path | None = None) -> bool:
    """Retorna True quando o banco não existe ou alguma fonte mudou."""
    caminho = Path(db_path) if db_path is not None else DB_PATH
    if not caminho.exists():
        return True
    try:
        with conectar(caminho) as conexao:
            linha = conexao.execute(
                "SELECT valor FROM metadados_carga WHERE chave = 'assinatura_fontes'"
            ).fetchone()
        return linha is None or linha[0] != assinatura_fontes()
    except Exception:
        return True


def _formatar_datas_sinan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "data_notificacao" in df.columns:
        df["data_notificacao"] = pd.to_datetime(df["data_notificacao"], errors="coerce").dt.strftime("%Y-%m-%d")
    return df


def recriar_banco(db_path: str | Path | None = None) -> dict[str, int]:
    """Carrega todas as fontes em tabelas SQLite e retorna contagens importadas."""
    caminho = Path(db_path) if db_path is not None else DB_PATH
    inicializar_esquema(caminho)
    populacao = carregar_populacao()
    casos = _formatar_datas_sinan(carregar_casos())
    abas = carregar_vacinacao()

    mensal = pd.concat(
        [preparar_vacinacao_mensal(abas, ano) for ano in (2024, 2025)],
        ignore_index=True,
    )
    if not mensal.empty:
        mensal["mes_numero"] = mensal["mes"].astype(str).str.strip().str.lower().map(MESES)

    sexo = pd.concat(
        [preparar_vacinacao_categoria(abas, ano, "sexo") for ano in (2024, 2025)],
        ignore_index=True,
    )
    faixa = pd.concat(
        [preparar_vacinacao_categoria(abas, ano, "faixaetaria") for ano in (2024, 2025)],
        ignore_index=True,
    )
    if not sexo.empty:
        sexo = sexo.rename(columns={"categoria": "sexo_categoria"})
    if not faixa.empty:
        faixa = faixa.rename(columns={"categoria": "faixa_etaria"})

    conjuntos = {
        "populacao_municipio": populacao[["municipio", "municipio_original", "populacao"]],
        "registros_sinan": casos[["municipio", "municipio_original", "data_notificacao", "idade_anos", "sexo", "arquivo_ano", "ano_data", "diverge_ano_arquivo"]].copy(),
        "vacinacao_mensal": mensal[["municipio", "municipio_original", "ano", "mes", "mes_numero", "doses"]].copy() if not mensal.empty else pd.DataFrame(columns=["municipio", "municipio_original", "ano", "mes", "mes_numero", "doses"]),
        "vacinacao_sexo": sexo[["municipio", "municipio_original", "ano", "sexo_categoria", "doses"]].copy() if not sexo.empty else pd.DataFrame(columns=["municipio", "municipio_original", "ano", "sexo_categoria", "doses"]),
        "vacinacao_faixa_etaria": faixa[["municipio", "municipio_original", "ano", "faixa_etaria", "doses"]].copy() if not faixa.empty else pd.DataFrame(columns=["municipio", "municipio_original", "ano", "faixa_etaria", "doses"]),
    }

    with conectar(caminho) as conexao:
        try:
            for tabela in TABELAS_DADOS:
                conexao.execute(f"DELETE FROM {tabela}")
            for tabela, df in conjuntos.items():
                df.to_sql(tabela, conexao, if_exists="append", index=False)
            metadados = {
                "assinatura_fontes": assinatura_fontes(),
                "carregado_em_utc": datetime.now(timezone.utc).isoformat(),
                "versao_esquema": "1",
            }
            conexao.executemany(
                "INSERT INTO metadados_carga(chave, valor) VALUES (?, ?) "
                "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                list(metadados.items()),
            )
        except Exception:
            conexao.rollback()
            raise

    return {tabela: len(df) for tabela, df in conjuntos.items()}


def garantir_banco_atualizado(db_path: str | Path | None = None) -> dict[str, int] | None:
    """Cria/atualiza o banco quando necessário; retorna contagens se houve carga."""
    if banco_precisa_atualizar(db_path):
        return recriar_banco(db_path)
    return None
