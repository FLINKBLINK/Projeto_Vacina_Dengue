# ETL das fontes oficiais

## Estado da implementação

O módulo `src/ingestion/etl_oficial.py` consulta a API DEMAS do Ministério da Saúde e grava dados brutos auditáveis no SQLite, em tabelas aditivas (`oficiais_registros` e `oficiais_execucoes`). As tabelas atuais do dashboard permanecem intactas. A carga é idempotente por hash do registro e registra a quantidade de páginas, linhas recebidas e linhas da região.

Fontes documentadas:
- Dengue/SINAN: `/arboviroses/dengue`
- Estimativas populacionais: `/vigilancia-e-meio-ambiente/svsa-populacao-residente`
- Doses aplicadas PNI por ano: `/vacinacao/doses-aplicadas-pni-AAAA`

Swagger oficial: https://apidadosabertos.saude.gov.br/static/swagger.json

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
