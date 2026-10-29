import json
import zipfile

from scripts.auditar_estrutura_snapshots_sinan import comparar


def _zip(path, csv_text, member):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, csv_text.encode("latin-1"))


def test_compara_cabecalhos_e_distribuicoes_sem_expor_linhas(tmp_path):
    y2023 = tmp_path / "2023.zip"
    y2024 = tmp_path / "2024.zip"
    _zip(
        y2023,
        "ID_MN_RESI;ID_MUNICIP;NU_ANO;DT_NOTIFIC;CLASSI_FIN\n"
        "354340;354340;2023;2023-02-01;10\n"
        "354020;354340;2023;2023-03-01;8\n",
        "DENGBR23.csv",
    )
    _zip(
        y2024,
        "ID_MN_RESI;ID_MUNICIP;NU_ANO;DT_NOTIFIC;CLASSI_FIN;CAMPO_NOVO\n"
        "354340;354020;2024;2024-01-01;11;x\n",
        "DENGBR24.csv",
    )

    report = comparar({2023: y2023, 2024: y2024})

    assert report["anos_analisados"] == [2023, 2024]
    assert report["quantidade_colunas_comuns"] == 5
    assert report["snapshots"]["2023"]["linhas_csv"] == 2
    assert report["snapshots"]["2024"]["linhas_csv"] == 1
    assert report["snapshots"]["2023"]["registros_por_municipio_residencia_alvo"] == {
        "Ribeirão Preto": 1,
        "Pontal": 1,
    }
    assert report["snapshots"]["2023"]["distribuicao_CLASSI_FIN"] == {"10": 1, "8": 1}
    assert "CAMPO_NOVO" in report["comparacao_cabecalhos"][0]["colunas_ausentes_em_relacao_a_uniao"]
    serialized = json.dumps(report, ensure_ascii=False)
    assert "2023-02-01" not in serialized
    assert "2024-01-01" not in serialized


def test_falha_se_zip_nao_tiver_exatamente_um_csv(tmp_path):
    import pytest
    from scripts.auditar_estrutura_snapshots_sinan import analisar_arquivo

    archive_path = tmp_path / "sem_csv.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("readme.txt", "arquivo sem CSV")

    with pytest.raises(ValueError, match="exatamente um CSV"):
        analisar_arquivo(2024, archive_path)
