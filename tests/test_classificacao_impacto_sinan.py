from scripts.classificacao_impacto_sinan import (
    classify_issue,
    classify_pending,
    summarize_classifications,
)


def test_temporal_alert_does_not_directly_block_vaccination_indicators():
    result = classify_issue("ano_notificacao_diferente_arquivo")

    assert result["severidade"] == "alerta"
    assert result["impacto"] == "series_temporais_sinan"
    assert result["impacto_vacinacao"] == "nao_direto"
    assert result["regra_catalogo"] is True


def test_inconclusive_classification_is_not_counted_as_confirmed_dengue():
    result = classify_issue("classificacao_inconclusiva")

    assert result["severidade"] == "inconclusiva"
    assert result["impacto"] == "casos_dengue_confirmados"
    assert "Não contar como dengue confirmada" in result["tratamento"]


def test_invalid_date_only_blocks_indicator_that_uses_that_date():
    result = classify_issue("data_invalida_DT_NOTIFIC")

    assert result["severidade"] == "bloqueante_no_indicador"
    assert result["impacto"] == "indicadores_que_usam_a_data"
    assert result["impacto_vacinacao"] == "depende_do_indicador"


def test_unknown_issue_is_preserved_and_flagged_for_review():
    result = classify_issue("tipo_novo_nao_catalogado")

    assert result["severidade"] == "inconclusiva"
    assert result["impacto"] == "nao_avaliado"
    assert result["regra_catalogo"] is False
    assert result["revisao_manual"] is True


def test_classify_pending_does_not_mutate_source_row():
    row = {"tipo_pendencia": "conteudo_clinico_repetido", "chave_registro": "2024:linha:7"}
    original = row.copy()

    result = classify_pending(row)

    assert row == original
    assert result["chave_registro"] == "2024:linha:7"
    assert result["severidade"] == "alerta"


def test_summary_counts_occurrences_and_unknown_types():
    rows = [
        {"tipo_pendencia": "ano_notificacao_diferente_arquivo"},
        {"tipo_pendencia": "classificacao_inconclusiva"},
        {"tipo_pendencia": "tipo_novo"},
        {"tipo_pendencia": "tipo_novo"},
    ]

    summary = summarize_classifications(rows)

    assert summary["total_ocorrencias"] == 4
    assert summary["por_severidade"] == {"alerta": 1, "inconclusiva": 3}
    assert summary["por_impacto_vacinacao"] == {"nao_avaliado": 2, "nao_direto": 2}
    assert summary["tipos_fora_do_catalogo"] == {"tipo_novo": 2}
