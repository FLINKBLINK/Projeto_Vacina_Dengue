import sqlite3

from scripts.auditar_modelagem import auditar_banco


def test_auditoria_banco_e_somente_leitura(tmp_path):
    caminho = tmp_path / "teste.db"
    with sqlite3.connect(caminho) as conn:
        conn.executescript("""
            CREATE TABLE municipio (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL
            );
            CREATE TABLE doses (
                id INTEGER PRIMARY KEY,
                municipio_id INTEGER NOT NULL REFERENCES municipio(id),
                ano INTEGER,
                doses REAL
            );
            INSERT INTO municipio VALUES (1, 'Ribeirão Preto');
            INSERT INTO doses VALUES (1, 1, 2024, 120);
        """)

    resultado = auditar_banco(caminho)
    tabelas = {t["nome"]: t for t in resultado["tabelas"]}

    assert tabelas["municipio"]["linhas"] == 1
    assert tabelas["doses"]["chaves_estrangeiras"][0] == {
        "coluna": "municipio_id",
        "tabela_referenciada": "municipio",
        "coluna_referenciada": "id",
    }
    with sqlite3.connect(caminho) as conn:
        assert conn.execute("SELECT COUNT(*) FROM doses").fetchone()[0] == 1
