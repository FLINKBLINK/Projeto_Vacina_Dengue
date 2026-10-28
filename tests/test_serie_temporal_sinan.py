from scripts.serie_temporal_sinan import aggregate_records, parse_date


def test_parse_date_distinguishes_missing_invalid_and_valid():
    assert parse_date("2024-01-02")[0].isoformat() == "2024-01-02"
    assert parse_date("")[1] == "ausente"
    assert parse_date("31/02/2024")[1] == "invalida"


def test_series_uses_symptom_year_and_keeps_missing_and_future_dates_separate():
    records = [
        {"municipio": "Ribeirão Preto", "ano_arquivo": 2024,
         "registro": {"DT_SIN_PRI": "2023-12-31", "DT_NOTIFIC": "2024-01-03", "CLASSI_FIN": "10"}},
        {"municipio": "Ribeirão Preto", "ano_arquivo": 2025,
         "registro": {"DT_SIN_PRI": "2026-01-02", "DT_NOTIFIC": "2025-12-30", "CLASSI_FIN": "8"}},
        {"municipio": "Serrana", "ano_arquivo": 2025,
         "registro": {"DT_SIN_PRI": "", "DT_NOTIFIC": "2025-04-01", "CLASSI_FIN": ""}},
        {"municipio": "Serrana", "ano_arquivo": 2025,
         "registro": {"DT_SIN_PRI": "data-errada", "DT_NOTIFIC": "", "CLASSI_FIN": "5"}},
    ]

    report = aggregate_records(records)

    assert report["total_registros_origem"] == 4
    assert report["registros_por_ano_inicio_sintomas"] == {2023: 1, 2026: 1}
    assert report["registros_por_ano_notificacao"] == {2024: 1, 2025: 2}
    assert report["qualidade_data_inicio_sintomas"] == {"ausente": 1, "invalida": 1, "valida": 2}
    assert report["datas_sintomas_posteriores_ao_snapshot"] == [
        {"ano_arquivo": 2025, "ano_inicio_sintomas": 2026, "registros": 1}
    ]
    assert {"ano_inicio_sintomas": "data_ausente", "classificacao": "classificacao_ausente", "registros": 1} in report["registros_por_ano_sintomas_e_classificacao"]
    assert {"ano_inicio_sintomas": "data_invalida", "classificacao": "descartado", "registros": 1} in report["registros_por_ano_sintomas_e_classificacao"]
