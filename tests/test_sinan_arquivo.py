import io
import sqlite3
import zipfile

from src.ingestion.etl_oficial import carregar_registros, inicializar_tabelas_oficiais

import pytest

from src.ingestion.sinan_arquivo import iterar_csv_residencia, iterar_sinan_arquivo, normalizar_codigo_residencia


def test_normaliza_codigos_ibge_de_seis_e_sete_digitos():
    assert normalizar_codigo_residencia("354340") == "354340"
    assert normalizar_codigo_residencia("3543402") == "354340"
    assert normalizar_codigo_residencia("3518859") == "351885"
    assert normalizar_codigo_residencia("") is None
    assert normalizar_codigo_residencia("320530") == "320530"


def test_filtra_por_residencia_e_nao_por_notificador():
    csv_text = (
        "ID_MUNICIP;ID_MN_RESI;NU_ANO\n"
        "354340;354340;2024\n"
        "320530;354020;2024\n"
        "354020;320530;2024\n"
        "354020;3518859;2024\n"
    )
    batches = list(iterar_csv_residencia(io.StringIO(csv_text), page_size=2))
    rows = [row for batch in batches for row in batch]
    assert len(rows) == 3
    assert [row["id_mn_resi"] for row in rows] == ["354340", "354020", "351885"]
    # Linha notificada em Pontal mas residente fora da região é descartada.
    assert all(row["id_mn_resi"] != "320530" for row in rows)


def test_falha_se_nao_houver_coluna_de_residencia():
    with pytest.raises(ValueError, match="município de residência"):
        list(iterar_csv_residencia(io.StringIO("ID_MUNICIP;NU_ANO\n354340;2024\n")))


def test_preserva_linhas_identicas_com_ordinais_de_fonte_distintos():
    csv_text = (
        "ID_MN_RESI;NU_ANO;CS_SEXO\n"
        "354340;2024;F\n"
        "354340;2024;F\n"
    )
    batches = list(iterar_csv_residencia(io.StringIO(csv_text), page_size=10))
    rows = [row for batch in batches for row in batch]

    assert len(rows) == 2
    assert rows[0]["NU_ANO"] == rows[1]["NU_ANO"]
    assert rows[0]["CS_SEXO"] == rows[1]["CS_SEXO"]
    assert rows[0]["_sinan_linha_fonte"] == "1"
    assert rows[1]["_sinan_linha_fonte"] == "2"

    conn = sqlite3.connect(":memory:")
    inicializar_tabelas_oficiais(conn)
    stats = carregar_registros(conn, "sinan_dengue", rows, ano_referencia=2024)

    assert stats == {"recebidos": 2, "regiao": 2}
    assert conn.execute(
        "SELECT COUNT(*) FROM oficiais_registros WHERE fonte='sinan_dengue'"
    ).fetchone()[0] == 2
    keys = [row[0] for row in conn.execute(
        "SELECT chave_registro FROM oficiais_registros ORDER BY chave_registro"
    )]
    assert keys == ["2024:linha:1", "2024:linha:2"]



def test_iterar_sinan_arquivo_reutiliza_zip_local_sem_rede(tmp_path):
    archive_path = tmp_path / "sinan.zip"
    csv_text = "ID_MN_RESI;NU_ANO;CS_SEXO\\n354340;2024;F\\n320530;2024;M\\n"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("DENGBR24.csv", csv_text.encode("latin-1"))

    batches = list(iterar_sinan_arquivo(2024, page_size=10, archive_path=archive_path))
    rows = [row for batch in batches for row in batch]

    assert len(rows) == 1
    assert rows[0]["id_mn_resi"] == "354340"
    assert rows[0]["_sinan_linha_fonte"] == "1"
