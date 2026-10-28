"""Catálogo compartilhado de regras cronológicas do SINAN.

As regras sinalizam relações temporais para auditoria; não corrigem nem excluem
registros. A classificação de severidade/impacto é uma camada separada.
"""

# Tupla: (identificador, campo esquerdo, campo direito, relação violada).
# "greater": o campo esquerdo não deveria ser posterior ao direito.
# "less": o campo esquerdo não deveria ser anterior ao direito.
DATE_ORDER_RULES = (
    ("inicio_sintomas_apos_notificacao", "DT_SIN_PRI", "DT_NOTIFIC", "greater"),
    ("investigacao_antes_notificacao", "DT_INVEST", "DT_NOTIFIC", "less"),
    ("encerramento_antes_investigacao", "DT_ENCERRA", "DT_INVEST", "less"),
    ("encerramento_antes_notificacao", "DT_ENCERRA", "DT_NOTIFIC", "less"),
    ("obito_antes_inicio_sintomas", "DT_OBITO", "DT_SIN_PRI", "less"),
    ("coleta_ns1_antes_inicio_sintomas", "DT_NS1", "DT_SIN_PRI", "less"),
    ("coleta_pcr_antes_inicio_sintomas", "DT_PCR", "DT_SIN_PRI", "less"),
    ("coleta_soro_antes_inicio_sintomas", "DT_SORO", "DT_SIN_PRI", "less"),
    ("coleta_prnt_antes_inicio_sintomas", "DT_PRNT", "DT_SIN_PRI", "less"),
    ("coleta_viral_antes_inicio_sintomas", "DT_VIRAL", "DT_SIN_PRI", "less"),
)

# O relatório de pendências semânticas expõe atualmente estas cinco regras.
# Manter a seleção explícita evita alterar o contrato do CSV existente.
DATE_PENDING_RULES = DATE_ORDER_RULES[:5]
