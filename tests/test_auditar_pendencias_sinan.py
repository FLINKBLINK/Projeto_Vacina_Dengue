import json
import sqlite3

from scripts.auditar_pendencias_sinan import audit_pending


def _create_db(path, rows):
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE oficiais_registros (
            fonte TEXT, chave_registro TEXT, municipio_ibge TEXT, municipio TEXT,
            ano_referencia INTEGER, extraido_em_utc TEXT, registro_json TEXT,
            PRIMARY KEY (fonte, chave_registro)
        )""")
        for key, year, record in rows:
            conn.execute(
                "INSERT INTO oficiais_registros VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("sinan_dengue", key, "3505601", "Barrinha", year,
                 "2026-01-01T00:00:00+00:00", json.dumps(record)),
            )


def _record(**overrides):
    record = {
        "ID_AGRAVO": "A90", "ID_MN_RESI": "350560", "NU_ANO": "2024",
        "DT_NOTIFIC": "2024-03-10", "DT_SIN_PRI": "2024-03-08",
        "DT_INVEST": "2024-03-11", "DT_ENCERRA": "2024-03-12",
        "CLASSI_FIN": "10", "EVOLUCAO": "1", "CRITERIO": "1",
        "CS_SEXO": "F", "NU_IDADE_N": "4050", "SEM_PRI": "202410",
    }
    record.update(overrides)
    return record


def test_details_year_classification_missing_fields_and_duplicate_payload(tmp_path):
    db = tmp_path / "test.db"
    duplicated = _record(CLASSI_FIN="8", EVOLUCAO="")
    mismatch = _record(NU_ANO="2023", DT_NOTIFIC="2023-12-31", DT_SIN_PRI="2023-12-28")
    _create_db(db, [
        ("2024:linha:1", 2024, duplicated),
        ("2024:linha:2", 2024, duplicated),
        ("2024:linha:3", 2024, mismatch),
    ])

    summary, pending = audit_pending(str(db), (2024,))
    types = [row["tipo_pendencia"] for row in pending]

    assert summary["registros_por_ano"]["2024"] == 3
    assert summary["classificacao_por_ano"]["2024"]["8"] == 2
    assert types.count("classificacao_inconclusiva") == 2
    assert types.count("evolucao_vazia") == 2
    assert types.count("conteudo_clinico_repetido") == 2
    assert "NU_ANO_diferente_arquivo" in types
    assert "ano_notificacao_diferente_arquivo" in types
    assert summary["grupos_conteudo_clinico_repetido_por_ano"]["2024"] == 1


def test_empty_year_raises(tmp_path):
    db = tmp_path / "test.db"
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE oficiais_registros (
            fonte TEXT, chave_registro TEXT, municipio_ibge TEXT, municipio TEXT,
            ano_referencia INTEGER, extraido_em_utc TEXT, registro_json TEXT
        )""")
    try:
        audit_pending(str(db), (2024,))
    except ValueError as exc:
        assert "Nenhum registro" in str(exc)
    else:
        raise AssertionError("Esperava erro para ano sem registros")
