import json
import sqlite3

from scripts.validar_qualidade_sinan import audit


def _db(path, record, municipality="Barrinha", key="2024:linha:1"):
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE oficiais_registros (
            fonte TEXT, chave_registro TEXT, municipio_ibge TEXT, municipio TEXT,
            ano_referencia INTEGER, extraido_em_utc TEXT, registro_json TEXT,
            PRIMARY KEY (fonte, chave_registro)
        )""")
        conn.execute(
            "INSERT INTO oficiais_registros VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("sinan_dengue", key, "3505601", municipality, 2024,
             "2026-01-01T00:00:00+00:00", json.dumps(record)),
        )


def _record(**overrides):
    record = {
        "ID_AGRAVO": "A90", "ID_MN_RESI": "350560", "NU_ANO": "2024",
        "DT_NOTIFIC": "2024-03-10", "DT_SIN_PRI": "2024-03-08",
        "DT_INVEST": "2024-03-11", "DT_ENCERRA": "2024-03-12",
        "DT_OBITO": "", "CS_SEXO": "F", "NU_IDADE_N": "4050",
        "CLASSI_FIN": "10", "EVOLUCAO": "1", "SEM_PRI": "202410",
    }
    record.update(overrides)
    return record


def test_valid_record_has_approved_integrity(tmp_path):
    db = tmp_path / "test.db"
    _db(db, _record())
    report = audit(str(db), 2024)
    assert report["status_integridade"] == "aprovado"
    assert report["registros_analisados"] == 1
    assert report["contagens"]["datas_invalidas_por_campo"] == {}
    assert report["contagens"]["inconsistencias_cronologicas"] == {}


def test_reports_invalid_dates_and_chronology_without_deleting_rows(tmp_path):
    db = tmp_path / "test.db"
    _db(db, _record(DT_NOTIFIC="31-31-2024", DT_SIN_PRI="2024-04-01"))
    report = audit(str(db), 2024)
    assert report["status_integridade"] == "aprovado"
    assert report["contagens"]["datas_invalidas_por_campo"]["DT_NOTIFIC"] == 1
    assert report["registros_analisados"] == 1


def test_detects_wrong_municipality_mapping_as_integrity_failure(tmp_path):
    db = tmp_path / "test.db"
    _db(db, _record(), municipality="Serrana")
    report = audit(str(db), 2024)
    assert report["status_integridade"] == "falha"
    assert report["contagens"]["municipio_codigo_divergente"] == 1


def test_classification_code_8_is_counted_as_inconclusive_not_invalid(tmp_path):
    db = tmp_path / "test.db"
    _db(db, _record(CLASSI_FIN="8"))
    report = audit(str(db), 2024)
    assert report["status_integridade"] == "aprovado"
    assert report["contagens"]["classi_fin_inconclusivo_codigo_8"] == 1
    assert "valor_fora_dominio_CLASSI_FIN" not in report["contagens"]["alertas_ano_e_dominio"]
    assert report["contagens"]["campos_categoricos"]["CLASSI_FIN"]["8"] == 1
    assert report["registros_analisados"] == 1
