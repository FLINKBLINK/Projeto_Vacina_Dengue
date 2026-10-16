"""Conexões e esquema do banco SQLite.

O arquivo do banco é gerado no ambiente de execução a partir das fontes versionadas.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("DENGUE_DB_PATH", str(ROOT / "data" / "processed" / "dengue.db")))

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS metadados_carga (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS populacao_municipio (
    municipio TEXT PRIMARY KEY,
    municipio_original TEXT,
    populacao REAL CHECK (populacao IS NULL OR populacao >= 0),
    fonte TEXT NOT NULL DEFAULT 'IBGE_TRATADO.xlsx'
);
CREATE TABLE IF NOT EXISTS registros_sinan (
    id INTEGER PRIMARY KEY,
    municipio TEXT NOT NULL,
    municipio_original TEXT,
    data_notificacao TEXT,
    idade_anos,
    sexo TEXT,
    ano_arquivo INTEGER,
    ano_data INTEGER,
    diverge_ano_arquivo INTEGER NOT NULL DEFAULT 0,
    fonte TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vacinacao_mensal (
    id INTEGER PRIMARY KEY,
    municipio TEXT NOT NULL,
    municipio_original TEXT,
    ano INTEGER NOT NULL,
    mes TEXT NOT NULL,
    mes_numero INTEGER,
    doses REAL CHECK (doses IS NULL OR doses >= 0),
    fonte TEXT NOT NULL DEFAULT 'DADOS_EXTRAIDOS.xlsx'
);
CREATE TABLE IF NOT EXISTS vacinacao_sexo (
    id INTEGER PRIMARY KEY,
    municipio TEXT NOT NULL,
    municipio_original TEXT,
    ano INTEGER NOT NULL,
    sexo_categoria TEXT NOT NULL,
    doses REAL CHECK (doses IS NULL OR doses >= 0),
    fonte TEXT NOT NULL DEFAULT 'DADOS_EXTRAIDOS.xlsx'
);
CREATE TABLE IF NOT EXISTS vacinacao_faixa_etaria (
    id INTEGER PRIMARY KEY,
    municipio TEXT NOT NULL,
    municipio_original TEXT,
    ano INTEGER NOT NULL,
    faixa_etaria TEXT NOT NULL,
    doses REAL CHECK (doses IS NULL OR doses >= 0),
    fonte TEXT NOT NULL DEFAULT 'DADOS_EXTRAIDOS.xlsx'
);
CREATE INDEX IF NOT EXISTS idx_sinan_municipio_data ON registros_sinan(municipio, data_notificacao);
CREATE INDEX IF NOT EXISTS idx_sinan_ano_data ON registros_sinan(ano_data);
CREATE INDEX IF NOT EXISTS idx_vac_mensal_municipio_ano ON vacinacao_mensal(municipio, ano);
CREATE INDEX IF NOT EXISTS idx_vac_sexo_ano ON vacinacao_sexo(ano, sexo_categoria);
CREATE INDEX IF NOT EXISTS idx_vac_faixa_ano ON vacinacao_faixa_etaria(ano, faixa_etaria);
"""


def conectar(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Abre conexão SQLite com Row access e chaves estrangeiras habilitadas."""
    caminho = Path(db_path) if db_path is not None else DB_PATH
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def inicializar_esquema(db_path: str | Path | None = None) -> Path:
    """Cria o arquivo e as tabelas caso ainda não existam."""
    caminho = Path(db_path) if db_path is not None else DB_PATH
    with conectar(caminho) as conexao:
        conexao.executescript(SCHEMA)
    return caminho


def listar_tabelas(db_path: str | Path | None = None) -> list[str]:
    """Retorna as tabelas de negócio presentes no banco."""
    with conectar(db_path) as conexao:
        linhas = conexao.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [linha['name'] for linha in linhas]
