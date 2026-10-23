from scripts.resumir_pendencias_temporais_sinan import classify


def _row(kind, year, notification, symptoms, nu_ano):
    return {
        "tipo_pendencia": kind,
        "ano_arquivo": str(year),
        "chave_registro": f"{year}:linha:1",
        "municipio": "Barrinha",
        "municipio_ibge": "3505601",
        "NU_ANO": str(nu_ano),
        "DT_NOTIFIC": notification,
        "DT_SIN_PRI": symptoms,
        "DT_INVEST": "",
        "DT_ENCERRA": "",
        "SEM_PRI": "",
    }


def test_previous_year_at_year_end_is_transition_review():
    row = _row("ano_notificacao_diferente_arquivo", 2025, "2024-12-31", "2024-12-29", 2024)
    result = classify(row)
    assert result["categoria_temporal"] == "transicao_fim_ano_anterior"
    assert "Janela" in result["criterio_classificacao"] or "Data entre" in result["criterio_classificacao"]


def test_following_year_outside_january_window_is_flagged():
    row = _row("ano_notificacao_diferente_arquivo", 2025, "2026-05-13", "2025-05-12", 2026)
    result = classify(row)
    assert result["categoria_temporal"] == "ano_posterior_ao_snapshot"


def test_symptom_date_at_year_boundary_is_classified():
    row = _row("ano_sintomas_diferente_arquivo", 2024, "2024-01-04", "2023-12-31", 2024)
    result = classify(row)
    assert result["categoria_temporal"] == "transicao_fim_ano_anterior"


def test_non_temporal_alert_is_ignored():
    row = _row("evolucao_vazia", 2024, "2024-01-04", "2023-12-31", 2024)
    assert classify(row) is None
