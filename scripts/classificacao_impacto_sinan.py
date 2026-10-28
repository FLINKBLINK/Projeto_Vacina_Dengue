"""Classifica severidade e impacto de pendências SINAN sem alterar os dados.

A classificação é uma política de triagem para orientar indicadores e revisão.
Não confirma erro clínico, não corrige registros e não deduplica notificações.
"""
from __future__ import annotations

from collections import Counter

from scripts.regras_temporais_sinan import DATE_ORDER_RULES

# A severidade se aplica ao uso do registro/indicador, não significa que o
# registro original deva ser removido nem que toda a execução deva falhar.
ISSUE_POLICY = {
    "json_invalido": {
        "severidade": "bloqueante_no_registro",
        "impacto": "processamento_semantico_sinan",
        "impacto_vacinacao": "nao_direto",
        "tratamento": "Preservar a linha de origem; não usar os campos clínicos até que o JSON possa ser interpretado.",
        "revisao_manual": True,
    },
    "classificacao_final_vazia": {
        "severidade": "bloqueante_no_indicador",
        "impacto": "casos_dengue_classificados",
        "impacto_vacinacao": "nao_direto",
        "tratamento": "Não inferir a classificação final; excluir apenas do indicador que exige classificação conhecida e reportar a quantidade.",
        "revisao_manual": True,
    },
    "classificacao_inconclusiva": {
        "severidade": "inconclusiva",
        "impacto": "registros_inconclusivos_sinan",
        "impacto_vacinacao": "nao_direto",
        "tratamento": "Não contar como dengue confirmada; manter na contagem de registros inconclusivos.",
        "revisao_manual": False,
    },
    "evolucao_vazia": {
        "severidade": "alerta",
        "impacto": "desfechos_clinicos_sinan",
        "impacto_vacinacao": "nao_direto",
        "tratamento": "Manter o desfecho como desconhecido; não inferir evolução clínica.",
        "revisao_manual": False,
    },
    "conteudo_clinico_repetido": {
        "severidade": "alerta",
        "impacto": "contagens_sinan",
        "impacto_vacinacao": "nao_direto",
        "tratamento": "Sinalizar para comparação; não remover, unir ou considerar duplicidade de pessoa automaticamente.",
        "revisao_manual": True,
    },
    "NU_ANO_diferente_arquivo": {
        "severidade": "alerta",
        "impacto": "series_temporais_sinan",
        "impacto_vacinacao": "nao_direto",
        "tratamento": "Preservar o valor original e conferir o período coberto e a versão do snapshot.",
        "revisao_manual": True,
    },
    "ano_notificacao_diferente_arquivo": {
        "severidade": "alerta",
        "impacto": "series_temporais_sinan",
        "impacto_vacinacao": "nao_direto",
        "tratamento": "Preservar a data; verificar cobertura temporal e eventual atualização retrospectiva da fonte.",
        "revisao_manual": True,
    },
    "ano_sintomas_diferente_arquivo": {
        "severidade": "alerta",
        "impacto": "series_temporais_sinan",
        "impacto_vacinacao": "nao_direto",
        "tratamento": "Preservar a data; avaliar o efeito na série por início de sintomas sem presumir erro.",
        "revisao_manual": True,
    },
}

_CHRONOLOGY_TYPES = {rule[0] for rule in DATE_ORDER_RULES}


def classify_issue(issue_type: str) -> dict:
    """Retorna metadados de triagem para um tipo de pendência conhecido ou não."""
    policy = ISSUE_POLICY.get(issue_type)
    if policy is not None:
        return {"tipo_pendencia": issue_type, **policy, "regra_catalogo": True}

    if issue_type in _CHRONOLOGY_TYPES:
        return {
            "tipo_pendencia": issue_type,
            "severidade": "alerta",
            "impacto": "qualidade_temporal_sinan",
            "impacto_vacinacao": "nao_direto",
            "tratamento": "Sinalizar a relação cronológica; não alterar datas nem descartar o registro.",
            "revisao_manual": True,
            "regra_catalogo": True,
        }

    if issue_type.startswith("data_invalida_"):
        return {
            "tipo_pendencia": issue_type,
            "severidade": "bloqueante_no_indicador",
            "impacto": "indicadores_que_usam_a_data",
            "impacto_vacinacao": "depende_do_indicador",
            "tratamento": "Não usar a data inválida no cálculo que depende dela; manter o valor original e contabilizar a pendência.",
            "revisao_manual": True,
            "regra_catalogo": True,
        }

    if issue_type.startswith("valor_fora_dominio_"):
        return {
            "tipo_pendencia": issue_type,
            "severidade": "alerta",
            "impacto": "indicadores_que_usam_o_campo",
            "impacto_vacinacao": "depende_do_indicador",
            "tratamento": "Não recodificar automaticamente; verificar o domínio e a versão do dicionário aplicável.",
            "revisao_manual": True,
            "regra_catalogo": True,
        }

    return {
        "tipo_pendencia": issue_type,
        "severidade": "inconclusiva",
        "impacto": "nao_avaliado",
        "impacto_vacinacao": "nao_avaliado",
        "tratamento": "Tipo não catalogado; preservar os dados e encaminhar a regra para avaliação antes de decidir o impacto.",
        "revisao_manual": True,
        "regra_catalogo": False,
    }


def classify_pending(row: dict) -> dict:
    """Acrescenta metadados de triagem a uma ocorrência, sem modificar a entrada."""
    issue_type = str(row.get("tipo_pendencia", "")).strip()
    return {**row, **classify_issue(issue_type)}


def summarize_classifications(rows: list[dict]) -> dict:
    """Resume ocorrências classificadas; contagens não representam pessoas únicas."""
    severity_counts = Counter()
    impact_counts = Counter()
    vaccine_impact_counts = Counter()
    unknown_types = Counter()

    for row in rows:
        issue_type = str(row.get("tipo_pendencia", "")).strip()
        classified = classify_issue(issue_type)
        severity_counts[classified["severidade"]] += 1
        impact_counts[classified["impacto"]] += 1
        vaccine_impact_counts[classified["impacto_vacinacao"]] += 1
        if not classified["regra_catalogo"]:
            unknown_types[issue_type or "(vazio)"] += 1

    return {
        "total_ocorrencias": len(rows),
        "observacao": (
            "Conta ocorrências de pendência, não registros ou pessoas únicas. "
            "A severidade se refere ao indicador afetado; não autoriza corrigir ou excluir dados. "
            "Impacto vacinal 'nao_direto' significa que a regra, por si só, não bloqueia "
            "indicadores de vacinação."
        ),
        "por_severidade": dict(sorted(severity_counts.items())),
        "por_impacto": dict(sorted(impact_counts.items())),
        "por_impacto_vacinacao": dict(sorted(vaccine_impact_counts.items())),
        "tipos_fora_do_catalogo": dict(sorted(unknown_types.items())),
    }
