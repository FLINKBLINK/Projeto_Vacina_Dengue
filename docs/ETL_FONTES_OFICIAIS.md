# ETL das fontes oficiais

## Estado da implementação

O módulo `src/ingestion/etl_oficial.py` consulta a API DEMAS do Ministério da Saúde e grava dados brutos auditáveis no SQLite, em tabelas aditivas (`oficiais_registros` e `oficiais_execucoes`). As tabelas atuais do dashboard permanecem intactas. A carga é idempotente por hash do registro e registra a quantidade de páginas, linhas recebidas e linhas da região.

Fontes documentadas:
- Dengue/SINAN: `/arboviroses/dengue`
- Estimativas populacionais: `/vigilancia-e-meio-ambiente/svsa-populacao-residente`
- Doses aplicadas PNI por ano: `/vacinacao/doses-aplicadas-pni-AAAA`

Swagger oficial: https://apidadosabertos.saude.gov.br/static/swagger.json

## Inspeção real de esquema

O script `scripts/inspecionar_esquema_api.py` consulta amostras limitadas a 100 registros por chamada e imprime nomes de campos, tipos JSON e frequências de identificadores geográficos/classificações públicas permitidas. Não imprime dados pessoais nem o conteúdo bruto dos registros.

Validação executada em 16/10/2026:
- SINAN dengue, ano 2024 sem filtro municipal: HTTP 200 e 5 registros de amostra.
- SINAN dengue, ano 2024 com `id_municip=354340` (código municipal de seis dígitos usado na consulta): HTTP 200 e 5 registros de amostra.
- A mesma consulta com `id_municip=35434` e `id_municip=3543402` retornou zero registros. Embora o código de seis dígitos tenha retornado cinco linhas, a amostra também tinha cinco linhas sem filtro; isso não prova que o filtro foi aplicado corretamente. A inspeção ampliada agora compara frequências dos identificadores públicos observados, mas continua sendo amostra limitada e não substitui a validação completa da geografia antes da carga histórica.
- Campos SINAN relevantes observados: `id_municip`, `municipio`, `nu_ano`, `dt_notific`, `id_mn_resi` e `classi_fin`. A API expõe muitos outros campos clínicos/epidemiológicos, preservados em JSON bruto.
- População residente: HTTP 200, com campos `ano`, `cod_mun`, `idade`, `pop` e `sexo`. Os registros vêm desagregados por sexo e idade; não se deve tratar cada linha como população total municipal.
- PNI 2025: HTTP 200; a amostra contém campos `codigo_vacina`, `codigo_dose_vacina`, `data_vacina`, `codigo_municipio_estabelecimento`, `codigo_municipio_paciente` e descrições de vacina/fabricante, entre outros. A amostra inicial não valida por si só qual código identifica a vacina contra dengue.

O workflow [Inspecionar esquema das APIs oficiais](https://github.com/FLINKBLINK/Projeto_Vacina_Dengue/actions/workflows/inspecionar-esquema-api.yml) executa essa inspeção sem salvar dados de pacientes no log.

## Executar

Teste curto da carga SINAN, usando somente um ano e um lote de até 1.000 registros regionais:

```bash
python -m scripts.etl_fontes_oficiais --db data/processed/etl_teste.db --anos-sinan 2024 --somente-sinan --max-pages 1
```

**Atenção:** mesmo com `--max-pages 1`, o SINAN baixa o ZIP nacional completo do ano escolhido e lê o CSV até encontrar o primeiro lote de registros dos municípios-alvo. A opção limita os lotes gravados, não o tamanho do download. O ETL agora processa cada arquivo anual uma única vez, em vez de baixar o mesmo ZIP uma vez por município.

Também é possível executar esse teste no GitHub sem configurar nada localmente: abra **Actions → Teste ETL SINAN para SQLite → Run workflow**, escolha o ano e inicie. O workflow usa um SQLite isolado, valida se as tabelas e registros foram criados e publica o arquivo `etl_github_test.db` como artefato por sete dias. O teste não altera o banco do dashboard nem os arquivos versionados.

Carga paginada padrão de dengue e população para 2023–2025:

```bash
python -m scripts.etl_fontes_oficiais
```

Banco alternativo para testar sem tocar no banco usado pelo dashboard:

```bash
DENGUE_DB_PATH=data/processed/etl_teste.db python -m scripts.etl_fontes_oficiais --max-pages 1
```

Para PNI nacional, use `--incluir-pni` somente após planejar o volume e validar o campo do imunobiológico. A API PNI é geral e não documenta filtros por município ou vacina no Swagger atual; portanto, a opção é desabilitada por padrão. **Não se deve somar todas as doses do PNI como doses contra dengue.**

## Decisões e limites

- A extração é filtrada para os dez municípios usados no projeto por código IBGE. No SINAN, o filtro oficial `id_municip` representa município da unidade notificadora segundo o Swagger, não necessariamente município de residência. A definição de geografia precisa ser conferida antes de comparar com população.
- A fonte populacional retorna agrupamentos por sexo/idade. O ETL conserva a linha bruta, não soma grupos automaticamente: só se pode obter população total após confirmar que os agrupamentos não se sobrepõem e que a categoria de sexo/idade foi tratada corretamente.
- Os dados oficiais são armazenados em tabelas próprias e não substituem automaticamente as planilhas auditadas nem alimentam os gráficos legados. Essa separação evita alterar silenciosamente as métricas publicadas.
- Os campos JSON brutos são preservados para permitir auditoria de esquema e futuras transformações. As tabelas analíticas normalizadas e a conexão aos gráficos devem ocorrer após validar nomes, semântica e filtros do endpoint com dados reais.
- `--max-pages` serve apenas para testes. Uma carga limitada não deve ser descrita como histórica completa.


## Validação geográfica e agregação (em andamento)

O relatório de inspeção ampliado mostra contagens de valores para campos públicos como `id_municip`, `municipio`, `cod_mun`, `codigo_municipio_paciente`, `codigo_municipio_estabelecimento` e códigos/descrições de vacina. A contagem ajuda a detectar filtros ignorados ou códigos inesperados, sem expor dados pessoais. Como a amostra é limitada a 100 linhas por chamada, ela não comprova completude nem permite inferir totais municipais.

A população residente deve ser agregada somente após carregar todas as páginas do município e verificar os grupos de `sexo` e `idade`. A soma deve evitar duplicar totais ou categorias agregadas. Até que os grupos e a semântica do endpoint estejam validados, os números de população desta fonte não devem substituir os valores já usados no dashboard.

## Diagnóstico de paginação SINAN por residência

A inspeção de 16/10/2026 mostrou que a consulta com `id_mn_resi=354340` retornou 100 linhas, mas os valores observados de `id_mn_resi` eram de outros municípios. Portanto, a API respondeu HTTP 200, porém a amostra indica que o parâmetro de residência pode estar sendo ignorado. Não usar esse parâmetro como filtro confiável sem nova validação.

O script `scripts/diagnosticar_paginacao_sinan.py` foi criado para estimar o volume por paginação sem salvar registros nem imprimir dados pessoais. Ele consulta o ano inteiro sem filtro municipal, lê páginas de até 1.000 linhas e filtra localmente pelos seis primeiros dígitos de `id_mn_resi`, comparando com os dez municípios do projeto. O padrão limita a leitura a 10 páginas para evitar uma varredura nacional ilimitada. O Swagger do endpoint define `offset` como número da página (0, 1, 2...), não como quantidade de linhas a pular. O cliente ETL foi alinhado a essa semântica e os testes verificam que páginas sucessivas não saltam blocos.

Diagnóstico inicial (até 10 páginas):

```bash
python -m scripts.diagnosticar_paginacao_sinan --ano 2024
```

Para testar uma página menor:

```bash
python -m scripts.diagnosticar_paginacao_sinan --ano 2024 --max-pages 1 --page-size 100
```

Se `varredura_completa` for `false`, os resultados são parciais: o limite de páginas foi atingido antes de uma página curta. Só considerar contagens históricas completas quando a paginação terminar normalmente; depois disso, ainda será necessário validar duplicatas, classificação final dos casos e semântica dos campos antes de gerar tabelas analíticas. O script é diagnóstico, não altera o ETL de produção nem as tabelas do dashboard.

