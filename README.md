# Projeto Vacina Dengue

Projeto de Ciência de Dados para analisar registros de vacinação contra a dengue, população e notificações de dengue nos municípios da região de Ribeirão Preto (SP). O repositório reúne dashboard em Streamlit, armazenamento relacional em SQLite, rotinas de ETL, auditorias de qualidade e testes automatizados.

> **Objetivo:** explorar como os registros de vacinação e as notificações de dengue evoluem nos municípios selecionados, documentando qualidade, cobertura temporal e limitações das fontes. As análises municipais são descritivas e exploratórias; não estimam eficácia individual nem demonstram causalidade.

## O que o projeto faz

- Explora doses registradas por município e recortes temporais e demográficos disponíveis.
- Compara vacinação, população e registros do SINAN.
- Calcula estatísticas descritivas e correlações de Pearson, com tamanho amostral e p-valor quando aplicável.
- Mantém uma camada SQLite separada da interface.
- Audita consistência, datas, classificação final, evolução clínica, domínios e divergências entre ano do arquivo e campos/datas registrados.
- Classifica pendências por severidade e impacto no indicador, sem alterar os dados de origem.
- Usa GitHub Actions para testes, validações e publicação de artefatos.

## Municípios

O conjunto regional inclui Barrinha, Brodowski, Cravinhos, Guatapará, Jardinópolis, Pontal, Pradópolis, Ribeirão Preto, Serrana e Sertãozinho.

Brodowski fica fora de algumas análises principais que reproduzem o recorte do artigo, mas permanece disponível nas rotinas de auditoria quando há dados.

## Tecnologias

- **Python**, pandas e bibliotecas de análise de dados
- **Streamlit** para o dashboard
- **SQLite** para persistência e consultas
- **pytest** para testes automatizados
- **GitHub Actions** para integração contínua e workflows de validação

## Executar localmente

Recomendado: Python 3.10 ou superior.

```bash
git clone https://github.com/FLINKBLINK/Projeto_Vacina_Dengue.git
cd Projeto_Vacina_Dengue

python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Se os arquivos necessários não estiverem nos locais esperados, o aplicativo informa quais fontes estão faltando.

## Dados de entrada e SQLite

### Planilhas do dashboard

Coloque os arquivos de origem em `data/raw/` (ou na raiz, conforme a resolução de caminhos implementada):

- `IBGE_TRATADO.xlsx` — população tratada;
- `DADOS_EXTRAIDOS.xlsx` — registros de vacinação;
- `SINAN_2023.xlsx`, `SINAN_2024.xlsx` e `SINAN_2025.xlsx` — extrações do SINAN usadas na análise.

Obtenha e publique os arquivos de acordo com as condições de uso das fontes originais. Não inclua dados pessoais identificáveis em logs, relatórios públicos ou commits.

### Banco do dashboard

O dashboard usa SQLite. Por padrão, o banco é criado em `data/processed/dengue.db`; a variável de ambiente `DENGUE_DB_PATH` permite indicar outro caminho. O banco é reconstruível e não precisa ser versionado.

Para gerar ou atualizar o banco a partir das planilhas:

```bash
python -m scripts.gerar_banco
```

A carga pode ser repetida após a atualização das fontes. O dashboard verifica a assinatura das fontes e refaz a carga quando identifica mudanças.

| Tabela | Conteúdo |
| --- | --- |
| `populacao_municipio` | População por município |
| `registros_sinan` | Registros SINAN importados, com referência à fonte |
| `vacinacao_mensal` | Doses por município, ano e mês |
| `vacinacao_sexo` | Doses por município, ano e categoria de sexo |
| `vacinacao_faixa_etaria` | Doses por município, ano e faixa etária |
| `metadados_carga` | Assinatura das fontes, data da carga e versão do esquema |

A camada de persistência fica em `src/database/`: `conexao.py` trata do caminho e esquema; `carga.py` executa o ETL; `consultas_db.py` centraliza consultas do dashboard.

## ETL e auditoria das fontes oficiais

Além das planilhas que alimentam o dashboard, há um pipeline separado para ingestão e auditoria de fontes oficiais. Ele grava registros brutos em tabelas próprias do SQLite, como `oficiais_registros` e `oficiais_execucoes`, sem substituir automaticamente as tabelas do dashboard.

Fontes documentadas:

- SINAN/Dengue na API de Dados Abertos do Ministério da Saúde;
- dados de população residente;
- API de doses aplicadas do PNI, opcional e sujeita à validação do imunobiológico.

Consulte [a documentação do ETL oficial](docs/ETL_FONTES_OFICIAIS.md).

### Teste curto do ETL SINAN

```bash
python -m scripts.etl_fontes_oficiais \
  --db data/processed/etl_teste.db \
  --anos-sinan 2024 \
  --somente-sinan \
  --max-pages 1
```

**Atenção:** `--max-pages 1` limita os lotes processados/gravados, mas não necessariamente o download nacional. Para SINAN, o comando pode baixar o ZIP anual completo e percorrer o CSV até obter o lote regional. Use um banco de teste para não misturar a validação com o banco do dashboard.

A extração oficial é independente da carga das planilhas. A opção PNI é desabilitada por padrão: não some todas as doses do PNI como se fossem doses contra dengue sem identificar e validar o imunobiológico correto.

### Auditorias SINAN

As rotinas auditam qualidade e pendências sem corrigir, excluir ou fundir registros automaticamente. O catálogo de regras temporais fica em `scripts/regras_temporais_sinan.py`; a política de severidade e impacto fica em `scripts/classificacao_impacto_sinan.py`.

Exemplo de exportação de pendências semânticas para um banco oficial já carregado:

```bash
python -m scripts.auditar_pendencias_sinan \
  --db data/processed/etl_teste.db \
  --years 2023,2024,2025 \
  --output-dir reports/auditoria-sinan
```

O comando gera `pendencias_semanticas_sinan.json` e `pendencias_semanticas_sinan.csv`. Ajuste os anos aos que existem no banco; a rotina exige registros para cada ano solicitado.

As classificações são uma política de triagem, não uma declaração automática de erro clínico. Pendências exclusivas do SINAN não bloqueiam diretamente os indicadores de vacinação quando não há relação direta demonstrada.

## Validações automatizadas

Execute os testes localmente:

```bash
python -m pytest -q
python -m compileall -q app.py src tests
```

Após a integração da auditoria de impacto, os workflows da branch principal registraram **79 testes aprovados**. Esse número descreve aquela execução, não garante o resultado de commits futuros.

Consulte a aba [GitHub Actions](https://github.com/FLINKBLINK/Projeto_Vacina_Dengue/actions) para os logs e artefatos de cada execução.

## Resultado de uma auditoria histórica

Uma execução consolidada avaliou **119.290 registros SINAN** dos anos de arquivo de 2023 a 2025:

| Ano de arquivo | Registros avaliados |
| --- | ---: |
| 2023 | 19.076 |
| 2024 | 60.846 |
| 2025 | 39.368 |
| **Total** | **119.290** |

Naquela execução, a integridade estrutural foi aprovada nos três anos, enquanto o status semântico foi `revisar_pendencias`. O relatório consolidado classificou 7.516 ocorrências de pendência, sem tipos fora do catálogo. Todas foram marcadas como sem impacto direto nos indicadores de vacinação pela política vigente. Esses números descrevem aquela extração e versão das regras; podem mudar com atualizações das fontes ou do código.

**Importante:** `revisar_pendencias` não significa que a execução falhou nem que todos os registros estão errados. Indica alertas ou situações inconclusivas que precisam permanecer documentados e ser interpretados conforme o indicador. Os artefatos ficam associados ao workflow correspondente no GitHub Actions; não trate um relatório histórico como contagem atual permanente.

## Convenções e limitações metodológicas

- **Doses não são pessoas únicas.** O indicador `doses registradas por 100 habitantes` não é cobertura vacinal oficial: uma pessoa pode receber mais de uma dose, e a população total pode não corresponder à população elegível.
- **Notificação não é confirmação.** A quantidade de linhas do SINAN é descrita como registros da base. Só se deve contar dengue confirmada após aplicar uma classificação final compatível e documentada; registros inconclusivos não são casos confirmados.
- **Datas e anos divergentes são sinalizados.** O ano no nome do arquivo, `NU_ANO` e os anos derivados de datas podem representar dimensões diferentes ou atualizações retrospectivas. Não são reclassificados silenciosamente.
- **Pendência não implica automaticamente erro ou duplicidade.** Conteúdo clínico semelhante merece comparação, mas não prova que se trata da mesma pessoa. Não há deduplicação nem correção automática.
- **Ausência não equivale a zero.** Valores ausentes não são convertidos automaticamente em zero.
- **Cobertura temporal importa.** A base de vacinação de 2025 identificada na auditoria inicial contém janeiro a abril. Não se inventam valores para maio nem se presume que arquivos futuros mantenham a mesma cobertura temporal.
- **Correlação não demonstra causalidade.** Associação entre vacinação e notificações agregadas por município não mede eficácia individual e pode ser afetada por sazonalidade, subnotificação, diferenças populacionais, temporalidade e outros fatores.
- **Geografia e denominadores devem ser validados.** Antes de comparar bases, confirme se cada fonte representa município de residência, município de notificação ou município do estabelecimento, além da granularidade e compatibilidade do denominador populacional.

## Fontes

- [IBGE — Censo Demográfico 2022](https://www.ibge.gov.br/estatisticas/sociais/rendimento-despesa-e-consumo/22827-censo-demografico-2022.html)
- [DATASUS — Transferência de arquivos](https://datasus.saude.gov.br/transferencia-de-arquivos/)
- [RNDS / InfoMS — Vacinação](https://infoms.saude.gov.br/extensions/SEIDIGI_DEMAS_VACINACAO_CALENDARIO_NACIONAL_OCORRENCIA/)
- [API de Dados Abertos do Ministério da Saúde — Swagger](https://apidadosabertos.saude.gov.br/static/swagger.json)
- [Auditoria inicial das bases](docs/AUDITORIA_DADOS.md)

## Estado do projeto

A base técnica inclui dashboard, SQLite, ETL separado para fontes oficiais, testes automatizados e auditorias de qualidade/impacto. O foco das próximas etapas é validar resultados estatísticos, explicitar as perguntas de pesquisa e transformar as visualizações em conclusões proporcionais ao que os dados permitem afirmar — sem confundir volume de registros, casos confirmados, cobertura vacinal e eficácia.
