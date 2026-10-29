import json
import zipfile

from scripts.auditar_comparabilidade_temporal_sinan import analyze_archive


def test_agrega_anos_classificacao_municipio_e_hashes_sem_expor_linhas(tmp_path):
    path = tmp_path / "mini.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "DENGBR24.csv",
            "ID_MN_RESI;NU_ANO;DT_NOTIFIC;DT_SIN_PRI;CLASSI_FIN;NDUPLIC_N\n"
            "354340;2024;2024-02-01;2024-01-30;10;1\n"
            "354340;2024;2024-02-01;2024-01-30;10;1\n"
            "354020;2023;2023-12-31;2024-01-01;8;2\n",
        )
    report = analyze_archive(2024, path)
    assert report["linhas"] == 3
    assert report["hashes_de_linhas_exatas_distintas"] == 2
    assert report["linhas_repetidas_por_hash_exato"] == 1
    assert report["distribuicao_NU_ANO"] == {"2023": 1, "2024": 2}
    assert report["distribuicao_ano_DT_SIN_PRI"] == {"2023": 1, "2024": 2}
    assert report["distribuicao_CLASSI_FIN"] == {"10": 2, "8": 1}
    assert report["distribuicao_NDUPLIC_N"] == {"1": 2, "2": 1}
    assert report["municipios_alvo_por_ano_inicio_sintomas"] == [
        {"municipio": "Pontal", "ano_inicio_sintomas": "2024", "registros": 1},
        {"municipio": "Ribeirão Preto", "ano_inicio_sintomas": "2024", "registros": 2},
    ]
    serialized = json.dumps(report, ensure_ascii=False)
    assert "2024-02-01" not in serialized
