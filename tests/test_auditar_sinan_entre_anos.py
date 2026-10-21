import json
import sqlite3

from scripts.auditar_sinan_entre_anos import auditar


def test_audita_ano_nominal_e_assinatura_repetida_sem_excluir_registros(tmp_path):
    db = tmp_path / "cross_year.db"
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE oficiais_registros (
            fonte TEXT, chave_registro TEXT, ano_referencia INTEGER, registro_json TEXT
        )""")
        base = {
            "ID_MN_RESI": "354340", "DT_NOTIFIC": "2024-03-10",
            "DT_SIN_PRI": "2024-03-08", "CS_SEXO": "F",
            "NU_IDADE_N": "4050", "CLASSI_FIN": "10", "CRITERIO": "1",
            "NU_ANO": "2024",
        }
        conn.executemany(
            "INSERT INTO oficiais_registros VALUES (?, ?, ?, ?)",
            [
                ("sinan_dengue", "2023:linha:1", 2023, json.dumps(base)),
                ("sinan_dengue", "2024:linha:1", 2024, json.dumps(base)),
            ],
        )
    report = auditar(str(db), (2023, 2024))
    assert report["registros_por_ano"] == {"2023": 1, "2024": 1}
    assert report["registros_com_NU_ANO_divergente"] == 1
    assert report["grupos_assinatura_clinica_presentes_em_multiplos_anos"] == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM oficiais_registros").fetchone()[0] == 2
