import pandas as pd

from src.database.carga import recriar_banco
from src.database.conexao import listar_tabelas
from src.database.consultas_db import (
    consultar_contagens_oficiais,
    consultar_casos,
    consultar_casos_oficiais,
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


def test_consulta_sinan_oficial_normaliza_registros_por_residencia(tmp_path):
    import json
    import sqlite3

    caminho = tmp_path / "sinan_oficial.db"
    with sqlite3.connect(caminho) as conn:
        conn.execute("""
            CREATE TABLE oficiais_registros (
                fonte TEXT NOT NULL,
                chave_registro TEXT NOT NULL,
                municipio_ibge TEXT,
                municipio TEXT,
                ano_referencia INTEGER,
                extraido_em_utc TEXT NOT NULL,
                registro_json TEXT NOT NULL,
                PRIMARY KEY (fonte, chave_registro)
            )
        """)
        registros = [
            (
                "sinan_dengue", "2024:linha:1", "3543402", "Ribeirão Preto", 2024,
                "2026-11-04T00:00:00Z",
                json.dumps({
                    "DT_NOTIFIC": "15/03/2024",
                    "NM_MN_RESI": "RIBEIRAO PRETO",
                    "CS_SEXO": "F",
                    "NU_IDADE_N": "4025",
                }),
            ),
            (
                "sinan_dengue", "2024:linha:2", "3543402", "Ribeirão Preto", 2024,
                "2026-11-04T00:00:00Z",
                json.dumps({
                    "DT_NOTIFIC": "02/01/2025",
                    "NM_MN_RESI": "RIBEIRAO PRETO",
                    "CS_SEXO": "M",
                    "IDADE_ANOS": "31",
                }),
            ),
        ]
        conn.executemany(
            """INSERT INTO oficiais_registros
               (fonte, chave_registro, municipio_ibge, municipio, ano_referencia,
                extraido_em_utc, registro_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            registros,
        )

    resultado = consultar_casos_oficiais(caminho)
    assert len(resultado) == 2
    assert set(resultado["municipio"]) == {"Ribeirão Preto"}
    assert resultado.loc[0, "data_notificacao"] == pd.Timestamp("2024-03-15")
    assert bool(resultado.loc[1, "diverge_ano_arquivo"]) is True
    # NU_IDADE_N é codificado no SINAN e não pode ser tratado como idade em anos.
    assert pd.isna(resultado.loc[0, "idade_anos"])
    assert resultado.loc[1, "idade_anos"] == 31


def test_carregar_casos_retorna_esquema_vazio_quando_planilhas_sinan_ausentes(monkeypatch):
    from src.analytics import consultas

    monkeypatch.setattr(consultas, "localizar_arquivo", lambda _nome: None)
    resultado = consultas.carregar_casos()

    assert resultado.empty
    assert "municipio_original" in resultado.columns
    assert "data_notificacao" in resultado.columns
    assert "arquivo_ano" in resultado.columns


def test_assinatura_fontes_aceita_sinan_local_ausente(monkeypatch, tmp_path):
    from src.database import carga

    arquivos_locais = {}
    for nome in ("IBGE_TRATADO.xlsx", "DADOS_EXTRAIDOS.xlsx"):
        caminho = tmp_path / nome
        caminho.write_bytes(b"fonte-de-teste")
        arquivos_locais[nome] = caminho

    monkeypatch.setattr(
        carga,
        "localizar_arquivo",
        lambda nome: arquivos_locais.get(nome),
    )
    assert carga.assinatura_fontes()


def test_assinatura_fontes_exige_populacao_e_vacinacao(monkeypatch):
    from src.database import carga

    monkeypatch.setattr(carga, "localizar_arquivo", lambda _nome: None)
    try:
        carga.assinatura_fontes()
    except FileNotFoundError as exc:
        assert "obrigatória" in str(exc)
    else:
        raise AssertionError("População e vacinação devem continuar obrigatórias")
