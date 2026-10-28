from scripts.regras_temporais_sinan import DATE_ORDER_RULES, DATE_PENDING_RULES


def test_chronology_catalog_has_unique_rule_names_and_complete_fields():
    names = [rule[0] for rule in DATE_ORDER_RULES]

    assert len(names) == len(set(names))
    assert all(len(rule) == 4 for rule in DATE_ORDER_RULES)
    assert all(relation in {"less", "greater"} for _, _, _, relation in DATE_ORDER_RULES)


def test_pending_audit_uses_explicit_subset_of_shared_chronology_catalog():
    assert DATE_PENDING_RULES == DATE_ORDER_RULES[:5]
    assert [rule[0] for rule in DATE_PENDING_RULES] == [
        "inicio_sintomas_apos_notificacao",
        "investigacao_antes_notificacao",
        "encerramento_antes_investigacao",
        "encerramento_antes_notificacao",
        "obito_antes_inicio_sintomas",
    ]


def test_catalog_keeps_sample_collection_rules_available_to_quality_audit():
    names = {rule[0] for rule in DATE_ORDER_RULES}

    assert {
        "coleta_ns1_antes_inicio_sintomas",
        "coleta_pcr_antes_inicio_sintomas",
        "coleta_soro_antes_inicio_sintomas",
        "coleta_prnt_antes_inicio_sintomas",
        "coleta_viral_antes_inicio_sintomas",
    }.issubset(names)
