# Arquitetura do banco SQLite

## Fluxo de dados

```text
Planilhas em data/raw/
        |
        v
src/analytics/consultas.py  (leitura e padronização)
        |
        v
src/database/carga.py       (ETL e assinatura das fontes)
        |
        v
SQLite: data/processed/dengue.db
        |
        v
src/database/consultas_db.py
        |
        v
app.py (Streamlit)
```

## Decisões de implementação

- As planilhas de origem são mantidas como fontes de referência e não são alteradas durante a carga.
- O arquivo SQLite é derivado e fica em `data/processed/`, pasta ignorada pelo Git. Isso evita versionar um artefato binário que pode ser reconstruído de forma determinística a partir das fontes.
- Na primeira execução, o dashboard gera o banco automaticamente. Nas execuções seguintes, compara uma assinatura dos nomes, tamanhos e datas de modificação das fontes e recarrega se detectar alteração.
- A carga substitui os registros das tabelas de dados em vez de acrescentar cópias, para evitar duplicação ao executar novamente.
- A camada de consultas isola o dashboard dos detalhes físicos do banco.

## Tabelas de dados

- `populacao_municipio`: uma linha por município na planilha IBGE.
- `registros_sinan`: linhas combinadas dos arquivos SINAN 2023, 2024 e 2025. `arquivo_ano` preserva o ano indicado pela origem; `ano_data` deriva da data real de notificação.
- `vacinacao_mensal`: doses registradas por município, ano e mês, em formato longo.
- `vacinacao_sexo`: doses por município, ano e categoria de sexo.
- `vacinacao_faixa_etaria`: doses por município, ano e faixa etária.
- `metadados_carga`: assinatura das fontes, horário UTC da carga e versão do esquema.

## Execução manual

Na raiz do repositório, com as dependências instaladas:

```bash
python -m scripts.gerar_banco
```

É possível definir um caminho alternativo para o arquivo antes de iniciar o processo:

```bash
# macOS/Linux
export DENGUE_DB_PATH="/caminho/para/dengue.db"
python -m scripts.gerar_banco

# Windows PowerShell
$env:DENGUE_DB_PATH = "C:\\caminho\\para\\dengue.db"
python -m scripts.gerar_banco
```

## Publicação no Streamlit Community Cloud

O ambiente publicado tem seu próprio sistema de arquivos. Por isso, o app não depende de um arquivo `.db` criado no computador local: ao iniciar, gera o SQLite a partir das planilhas incluídas em `data/raw/` e consulta esse banco durante a sessão. Como o armazenamento local de uma implantação pode ser efêmero, o banco deve ser considerado um artefato reconstruível; os arquivos de origem versionados são a referência persistente.
