## Auditoria da modelagem SQLite

Antes de alterar tabelas existentes, gere um diagnóstico somente leitura:

```bash
python -m scripts.auditar_modelagem
```

O comando usa por padrão `data/processed/dengue.db` e `DADOS_EXTRAIDOS.xlsx`
na raiz do projeto. Para indicar outros caminhos:

```bash
python -m scripts.auditar_modelagem --db data/processed/dengue.db --workbook data/raw/DADOS_EXTRAIDOS.xlsx --saida reports/auditoria_modelagem.md
```

Se quiser auditar somente o esquema do banco:

```bash
python -m scripts.auditar_modelagem --sem-planilha
```

O relatório apresenta colunas, tipos, nulabilidade, chaves primárias,
índices, chaves estrangeiras, contagem de linhas e cabeçalhos das abas.
Rótulos com hífen ou outros separadores são destacados para investigação,
mas não são classificados automaticamente como violações da primeira forma
normal.

**Segurança:** o banco é aberto em modo somente leitura. O script não cria,
altera nem exclui tabelas ou registros. A migração será uma etapa separada,
depois da validação das fontes, da granularidade e das dependências funcionais.
