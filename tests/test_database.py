import pandas as pd

from src.database.carga import recriar_banco
from src.database.conexao import listar_tabelas
from src.database.consultas_db import (
    consultar_contagens_oficiais,
    consultar_casos,
    consultar_execucoes_oficiais,
    consultar_populacao,
    consultar_vacinacao_categoria,
    consultar_vacinacao_mensal,
)


def test_sqlite_importa_as_fontes_e_permite_consultas(tmp_path):
    caminho = tmp_path / "dengue_test.db"
    contagens = recriar_banco(caminho)

    assert set(listar_tabelas(caminho)) == {
        "metadados_carga",
        "populacao_municipio",
        "registros_sinan",
        "vacinacao_mensal",
        "vacinacao_sexo",
        "vacinacao_faixa_etaria",
    }
    assert contagens["populacao_municipio"] == 10
    assert contagens["registros_sinan"] > 100_000
    assert contagens["vacinacao_mensal"] > 100
    assert not consultar_populacao(caminho).empty
    assert not consultar_casos(caminho).empty
    assert not consultar_vacinacao_mensal(caminho).empty
    assert not consultar_vacinacao_categoria("sexo", caminho).empty
    assert not consultar_vacinacao_categoria("faixaetaria", caminho).empty


def test_categoria_invalida_e_rejeitada():
    try:
        consultar_vacinacao_categoria("idade")
    except ValueError as exc:
        assert "categoria" in str(exc)
    else:
        raise AssertionError("A consulta deveria rejeitar uma categoria inválida")


def test_consultas_oficiais_sao_opcionais(tmp_path):
    caminho = tmp_path / "sem_etl_oficial.db"
    assert consultar_execucoes_oficiais(caminho).empty
    assert consultar_contagens_oficiais(caminho).empty


def test_consultas_expoem_historico_oficial_quando_disponivel(tmp_path):
    import sqlite3

    caminho = tmp_path / "etl_oficial.db"
    with sqlite3.connect(caminho) as conn:
        conn.executescript("""
            CREATE TABLE oficiais_execucoes (
                id INTEGER PRIMARY KEY, fonte TEXT, iniciado_em_utc TEXT,
                finalizado_em_utc TEXT, paginas INTEGER, registros_recebidos INTEGER,
                registros_regiao INTEGER, status TEXT, detalhe TEXT
            );
            INSERT INTO oficiais_execucoes VALUES
                (1, 'sinan_dengue', '2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z', 2, 20, 10, 'sucesso', NULL);
            CREATE TABLE oficiais_registros (fonte TEXT, ano_referencia INTEGER);
            INSERT INTO oficiais_registros VALUES ('sinan_dengue', 2025);
            INSERT INTO oficiais_registros VALUES ('sinan_dengue', 2025);
        """)

    execucoes = consultar_execucoes_oficiais(caminho)
    contagens = consultar_contagens_oficiais(caminho)
    assert execucoes.iloc[0]["fonte"] == "sinan_dengue"
    assert pd.isna(execucoes.iloc[0]["ano_referencia"])
    assert contagens.iloc[0]["registros"] == 2
