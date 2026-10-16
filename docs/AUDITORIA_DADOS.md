# Auditoria inicial das bases

Esta nota registra conferências feitas nos arquivos disponíveis em 16/10/2026. Os números abaixo são contagens das planilhas fornecidas; não substituem validação com as bases oficiais originais.

## Escopo

A análise principal considera nove municípios, excluindo Brodowski conforme a justificativa descrita no artigo: Barrinha, Cravinhos, Guatapará, Jardinópolis, Pontal, Pradópolis, Ribeirão Preto, Serrana e Sertãozinho.

## População (IBGE)

- A aba `Total` de `IBGE_TRATADO.xlsx` contém 10 municípios.
- A soma da coluna `Total` para os nove municípios (sem Brodowski) é **1.042.098 habitantes**, igual ao valor informado no artigo.
- Os nomes no arquivo IBGE têm o sufixo `(SP)`; a normalização do projeto remove esse sufixo antes de relacionar as bases.

## SINAN

| Arquivo | Linhas nos nove municípios | Intervalo de datas encontrado | Observação |
|---|---:|---|---|
| `SINAN_2023.xlsx` | 16.377 | 02/01/2023–30/12/2023 | Coincide com o total descrito no artigo |
| `SINAN_2024.xlsx` | 60.363 | 31/12/2023–28/12/2024 | Três registros têm data de notificação em 2023 |
| `SINAN_2025.xlsx` | 34.475 | 29/12/2024–03/05/2025 | 54 registros têm data em 2024; 34.421 têm data em 2025 |

O artigo informa **37.466** registros/casos entre janeiro e maio de 2025. A planilha `SINAN_2025.xlsx` contém **34.421** registros com data de notificação em 2025 para os nove municípios, diferença de **3.045**. A data máxima da planilha é 03/05/2025, portanto ela não representa todo o mês de maio.

Os arquivos SINAN fornecidos têm os campos de município, data de notificação, idade e sexo. Eles não contêm campo de classificação final que permita confirmar, isoladamente, que cada linha corresponde a um caso confirmado. Por isso, o dashboard utiliza o termo **registros SINAN** quando apresenta contagem direta de linhas.

Há divergência entre ano do nome do arquivo e ano da data de notificação: três linhas no arquivo 2024 e 54 linhas no arquivo 2025. A aplicação usa a data real para agrupar os registros e expõe essas divergências. Isso difere do procedimento descrito no artigo, que adotou o ano do arquivo como referência em algumas discrepâncias; a decisão precisa ser documentada antes de comparar resultados finais.

## Vacinação (RNDS / InfoMS)

- A aba `2024_ano` tem colunas de janeiro a dezembro. A soma das doses nos nove municípios é **37.533**.
- A aba `2025_ano` contém apenas janeiro, fevereiro, março e abril — **não existe coluna de maio**.
- A soma das doses da aba `2025_ano` nos nove municípios é **9.932**.
- O nome do município Cravinhos aparece como `CRAVINHHOS` na planilha de 2025; a rotina de padronização trata essa grafia.

O indicador doses/população é apresentado como **doses registradas por 100 habitantes**, e não como cobertura vacinal oficial. Doses podem incluir mais de uma dose por pessoa e a população total não equivale necessariamente à população elegível.

## Consequências para as análises estatísticas

1. Não é possível reproduzir de forma estrita a correlação publicada para vacinação acumulada de 2024 até maio de 2025 enquanto a planilha de vacinação de 2025 não tiver maio validado.
2. A comparação com o valor publicado de 37.466 para 2025 não pode ser reproduzida a partir das linhas com data em 2025 na planilha disponível.
3. Correlações em nível municipal têm amostra pequena (nove municípios), não demonstram causalidade e não permitem inferência de eficácia individual.
4. As correlações do artigo devem ser recalculadas a partir das bases e períodos explicitamente definidos antes de assumir os valores publicados como reproduzidos.

## Próximas validações

- Obter a extração SINAN que sustenta o total de 37.466 e verificar o filtro de classificação de caso.
- Confirmar a origem da ausência de maio na aba de vacinação de 2025.
- Definir explicitamente se os agrupamentos SINAN serão feitos pelo ano da data de notificação ou pelo arquivo de origem, e aplicar uma regra única.
- Recalcular as três hipóteses de Pearson do artigo usando períodos e denominadores documentados.
