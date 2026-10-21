# Validação de qualidade do SINAN/Dengue

## Escopo

Auditoria da carga anual SINAN/Dengue 2024, executada em SQLite isolado. A reconciliação do arquivo oficial foi aprovada em 21/10/2026:

- CSV oficial: `DENGBR24.csv`, dentro do ZIP [oficial](https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINAN/Dengue/csv/DENGBR24.csv.zip).
- SHA-256 do ZIP lido pela auditoria: `1b6b7bf7f6b1fdab4ed2314edc2f57919c33b8103988383f22b7d4776c4a931a`.
- Total de linhas no CSV nacional, sem cabeçalho: 6.564.924.
- Linhas dos dez municípios no CSV: 60.846.
- Linhas no SQLite: 60.846.
- Chaves ausentes e inesperadas: zero.
- Contagens de cada um dos dez municípios coincidiram exatamente.

O artifact original da execução está no [GitHub Actions run 39648119475](https://github.com/FLINKBLINK/Projeto_Vacina_Dengue/actions/runs/39648119475).

## Achados de qualidade observados na carga 2024

| Verificação | Resultado | Tratamento |
|---|---:|---|
| Agravo `ID_AGRAVO` diferente de A90 | 0 | Esperado para este arquivo de dengue |
| Código de residência sem município mapeado | 0 | Nenhuma divergência observada |
| Datas em formato inválido | 0 | Nenhuma divergência observada |
| `NU_ANO` diferente de 2024 | 3 | Revisar regra de inclusão no arquivo anual |
| Data de notificação em 2023 | 3 | Preservar e revisar; não excluir automaticamente |
| Início de sintomas em 2023 | 87 | Pode refletir início anterior à notificação; manter e documentar |
| `CLASSI_FIN` vazio | 34 | Dado ausente; revisar dicionário e regra de análise |
| `EVOLUCAO` vazio | 2.744 | Dado ausente; não inferir desfecho |
| `CLASSI_FIN=8` | 1.326 | Fora dos valores listados no dicionário SINAN Online de 2015; confirmar compatibilidade com o layout/versão dos microdados 2024 |
| Investigação anterior à notificação | 1 | Verificar regra temporal do dicionário |
| Encerramento anterior à investigação | 1 | Verificar cronologia do registro |
| Óbito anterior à notificação | 7 no diagnóstico preliminar | Não é, por si só, prova de erro; comparar com início dos sintomas e regras oficiais |
| Grupos de linhas com conteúdo clínico igual após remover metadados de extração | 37 grupos (74 linhas nesses grupos) | Preservar linhas; investigar se são duplicatas de origem ou notificações distintas |

Os resultados de campos ausentes e códigos devem ser interpretados segundo o dicionário vigente para o arquivo específico. O [dicionário SINAN Online de Dengue/Chikungunya](https://portalsinan.saude.gov.br/images/documentos/Agravos/Dengue/DIC_DADOS_ONLINE.pdf), revisado em 21/10/2015, lista `CLASSI_FIN` como 5 (descartado), 10 (dengue), 11 (dengue com sinais de alarme), 12 (dengue grave) e 13 (chikungunya), e `EVOLUCAO` como 1, 2, 3, 4 ou 9. Por ser uma referência de 2015, a ausência do código 8 nela é um **alerta para investigação**, não autorização para alterar o dado nem concluir automaticamente que a fonte está errada.

## Critérios de uso

1. Integridade da ingestão e qualidade semântica são indicadores separados.
2. Nenhuma linha é apagada apenas por data fora do ano do arquivo, campo vazio, código fora do dicionário de referência ou conteúdo repetido.
3. Para análises de casos confirmados, utilizar apenas as categorias definidas pela versão validada do dicionário, deixando explícitos os critérios e os registros excluídos do numerador.
4. Não chamar todos os registros de “casos confirmados”: o arquivo contém registros com classificações diferentes e valores ausentes.
5. Antes de incorporar ao banco produtivo, executar a auditoria semântica atualizada e revisar os alertas em relação ao dicionário específico da extração 2024.

## Próximas etapas

- Executar `scripts/validar_qualidade_sinan.py` no workflow de carga completa e arquivar `qualidade_sinan_2024.json`.
- Conferir a documentação oficial mais recente do layout nacional CSV 2024 e resolver o significado de `CLASSI_FIN=8`.
- Repetir a carga e as auditorias para 2023 e 2025; não generalizar a aprovação de 2024 para outros anos.
- Avaliar se a reconciliação de origem pode compartilhar a mesma cópia imutável do ZIP com a carga, evitando comparação de snapshots diferentes.
