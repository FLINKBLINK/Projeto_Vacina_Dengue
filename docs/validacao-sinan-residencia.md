# Validação SINAN por município de residência

Este diagnóstico compara, para um ano, o arquivo anual nacional de dengue do Portal de Dados Abertos do SUS com as contagens obtidas pela API paginada.

## Execução

No GitHub Actions, execute **Validar SINAN por residência usando arquivo oficial** e selecione o ano (padrão 2024). O workflow baixa o CSV/ZIP oficial, processa-o sem gravar linhas individuais e publica apenas um JSON agregado por município de residência e notificador.

Fonte de 2024: https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue/resource/4cf2f7b8-9920-41b5-817a-1ffc13e0690c

## Códigos municipais\n\nO código de Guatapará no IBGE é `3518859`, cujo prefixo de seis dígitos usado neste arquivo é `351885`. Não usar `351880`, que corresponde ao prefixo de Guarulhos (`3518800`). O teste automatizado cobre essa distinção para evitar que registros de Guarulhos sejam contabilizados como Guatapará.\n\n## O que comparar

- `por_municipio_residencia`: total de registros cujo município de residência é um dos dez municípios estudados, independentemente do município notificador.
- `por_municipio_notificador`: total de registros notificados por cada município estudado.
- `cruzamento_notificador_residencia_alvo`: distribuição cruzada entre notificadores e residentes dos dez municípios.
- `registros_distintos_por_hash_exato` e `linhas_repetidas_por_hash_exato`: repetição integral de linha, não uma deduplicação epidemiológica.
- `sha256_arquivo_zip`: identifica a versão exata do arquivo para reprodutibilidade.

O arquivo é nacional. Os dados brutos são temporários no runner e não são enviados como artefato. Apenas o resumo agregado é publicado por 14 dias. Não substituir tabelas do dashboard com este diagnóstico sem validar campos, critérios epidemiológicos e diferenças entre versões da base.

As contagens representam registros/notificações. Não significam automaticamente casos confirmados. Para incidência, a documentação do portal recomenda usar município de residência.


## Auditoria de consistência geográfica por UF

O JSON também contém o objeto `auditoria_geografica`, calculado sobre todas as linhas do CSV nacional:

- `SG_UF` é comparado com o prefixo estadual do código de residência (`ID_MN_RESI`).
- `SG_UF_NOT` é comparado com o prefixo estadual do código notificador (`ID_MUNICIP`).
- São contabilizados separadamente códigos ausentes, códigos com formato inválido, códigos válidos fora dos dez municípios do estudo, UFs ausentes/não reconhecidas e divergências entre UF e código municipal.
- UFs podem ser reconhecidas tanto pelo código IBGE de dois dígitos quanto pela sigla (por exemplo, `35` e `SP`).
- Os códigos municipais não mapeados são apresentados somente como frequências agregadas (até 30 valores mais frequentes); não são exportadas linhas individuais.

A regra de consistência verifica apenas se os dois primeiros dígitos do código municipal correspondem à UF informada. Ela não confirma a existência do município, a correção do endereço ou a qualidade epidemiológica do registro. Códigos não mapeados são esperados porque o arquivo é nacional e o projeto acompanha somente dez municípios.

Se as colunas `SG_UF` ou `SG_UF_NOT` não existirem no arquivo, o relatório sinaliza isso e não calcula compatibilidade para a dimensão correspondente. Divergências são indicadores para investigação, não autorização para corrigir ou excluir registros.
