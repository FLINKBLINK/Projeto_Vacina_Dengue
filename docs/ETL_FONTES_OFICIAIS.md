# ETL das fontes oficiais

## Estado da implementação

O módulo `src/ingestion/etl_oficial.py` consulta a API DEMAS do Ministério da Saúde e grava dados brutos auditáveis no SQLite, em tabelas aditivas (`oficiais_registros` e `oficiais_execucoes`). As tabelas atuais do dashboard permanecem intactas. A carga é idempotente por hash do registro e registra a quantidade de páginas, linhas recebidas e linhas da região.

Fontes documentadas:
- Dengue/SINAN: `/arboviroses/dengue`
- Estimativas populacionais: `/vigilancia-e-meio-ambiente/svsa-populacao-residente`
- Doses aplicadas PNI por ano: `/vacinacao/doses-aplicadas-pni-AAAA`

Swagger oficial: https://apidadosabertos.saude.gov.br/static/swagger.json

## Inspeção real de esquema

O script `scripts/inspecionar_esquema_api.py` consulta pequenas amostras e imprime somente nomes de campos, tipos JSON e contagens, nunca valores de registros.

Validação executada em 16/10/2026:
- SINAN dengue, ano 2024 sem filtro municipal: HTTP 200 e 5 registros de amostra.
- SINAN dengue, ano 2024 com `id_municip=354340` (código municipal de seis dígitos usado na consulta): HTTP 200 e 5 registros de amostra.
- A mesma consulta com `id_municip=35434` e `id_municip=3543402` retornou zero registros. O formato de seis dígitos deve ser mantido e a contagem real por município ainda deve ser auditada na extração completa.
- Campos SINAN relevantes observados: `id_municip`, `municipio`, `nu_ano`, `dt_notific`, `id_mn_resi` e `classi_fin`. A API expõe muitos outros campos clínicos/epidemiológicos, preservados em JSON bruto.
- População residente: HTTP 200, com campos `ano`, `cod_mun`, `idade`, `pop` e `sexo`. Os registros vêm desagregados por sexo e idade; não se deve tratar cada linha como população total municipal.
- PNI 2025: HTTP 200; a amostra contém campos `codigo_vacina`, `codigo_dose_vacina`, `data_vacina`, `codigo_municipio_estabelecimento`, `codigo_municipio_paciente` e descrições de vacina/fabricante, entre outros. A amostra inicial não valida por si só qual código identifica a vacina contra dengue.

O workflow [Inspecionar esquema das APIs oficiais](https://github.com/FLINKBLINK/Projeto_Vacina_Dengue/actions/workflows/inspecionar-esquema-api.yml) executa essa inspeção sem salvar dados de pacientes no log.

## Executar

Teste curto, limitado a uma página por consulta:

```bash
python -m scripts.etl_fontes_oficiais --max-pages 1
```

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
