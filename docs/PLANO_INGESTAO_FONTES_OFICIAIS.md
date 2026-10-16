# Plano de ingestão de fontes oficiais

## Escopo inicial

A primeira entrega automatiza a descoberta e a auditoria de metadados do catálogo oficial do Ministério da Saúde. Ela **não substitui a base analítica existente nem atualiza tabelas de produção**. Isso é intencional: os campos, formatos e regras de deduplicação precisam ser confirmados nos arquivos reais antes de liberar cargas automáticas.

## Fontes prioritárias

- **SINAN/Dengue:** https://dadosabertos.saude.gov.br/dataset/arboviroses-dengue
- **API de Dados Abertos do SUS:** https://apidadosabertos.saude.gov.br/
- **PNI — doses aplicadas:** https://dadosabertos.saude.gov.br/dataset/doses-aplicadas-pelo-programa-de-nacional-de-imunizacoes-pni-2026
- **Estimativas populacionais do IBGE:** https://www.ibge.gov.br/estatisticas/sociais/populacao/9103-estimativas-de-population.html

## Automação nesta etapa

O workflow `.github/workflows/inventario-fontes.yml` executa semanalmente ou manualmente. Ele consulta a API CKAN do Portal de Dados Abertos do SUS e publica um artefato JSON com os conjuntos, recursos, formatos, URLs e metadados de atualização encontrados.

## Próxima etapa: validação dos contratos de dados

Antes de baixar e transformar os arquivos, revisar o inventário e confirmar:

1. quais recursos representam registros individuais de dengue e quais são agregados;
2. quais campos de data, município de residência, classificação final e critério de confirmação estão disponíveis;
3. quais códigos/descrições identificam especificamente o imunizante contra dengue no PNI em cada ano;
4. quais arquivos históricos do PNI existem e se a estrutura muda entre anos;
5. regras de deduplicação, atualização retroativa e tratamento de dados incompletos;
6. denominadores populacionais por ano e faixa etária, sem usar uma única população atual para toda a série.

## Regras de segurança analítica

- Falha de fonte não pode apagar a última carga válida.
- Guardar a data da extração e os metadados do recurso de origem.
- Não tratar notificações como casos confirmados sem filtros epidemiológicos documentados.
- Não chamar doses/população total de cobertura vacinal oficial.
- Não publicar microdados pessoais ou identificadores diretos.
- Manter separadas as camadas bruta, tratada e analítica.
- Só promover cargas após passar validações de esquema, datas, totais, duplicidades e abrangência temporal.

## Estado

- [x] Criar módulo de descoberta do catálogo oficial.
- [x] Criar testes unitários com respostas simuladas.
- [x] Criar workflow semanal para inventário e execução manual.
- [ ] Executar workflow no GitHub e revisar inventário real.
- [ ] Validar dicionários/cabeçalhos dos recursos oficiais.
- [ ] Implementar download incremental e normalização SINAN.
- [ ] Implementar filtro específico de vacinação contra dengue e histórico PNI.
- [ ] Integrar dados validados ao banco e às visualizações do Streamlit.
