# Investigação da API PNI — vacinação contra dengue

## Objetivo

Investigar a estrutura real dos endpoints anuais do Programa Nacional de Imunizações (PNI), identificar os códigos de vacina e dose presentes nas amostras e verificar a disponibilidade de campos demográficos e geográficos.

Esta etapa é diagnóstica. **Não é uma carga de produção**, não grava registros individuais no SQLite e não altera as tabelas do dashboard.

## Execução local

```bash
python scripts/investigar_pni_dengue.py \
  --anos 2023,2024,2025,2026 \
  --page-size 1000 \
  --max-pages 3 \
  --saida reports/pni/inspecao_pni_dengue.json
```

O tamanho máximo de página aceito pela rotina é 1.000. O padrão de três páginas por ano limita a consulta a uma amostra de até 3.000 registros por endpoint.

## Execução pelo GitHub Actions

1. Abra o workflow **Investigar códigos e campos da vacinação PNI**.
2. Clique em **Run workflow** e selecione a branch desta implementação.
3. Mantenha inicialmente os parâmetros padrão.
4. Após a execução, baixe o artefato `investigacao-pni-dengue`.

O workflow executa apenas os testes específicos desta investigação e consulta os endpoints configurados.

## Conteúdo do relatório

O JSON apresenta, por ano:

- nomes dos campos retornados;
- preenchimento observado dos campos semânticos;
- frequência dos códigos de vacina e dose;
- descrições associadas aos códigos de vacina;
- frequências de sexo, idade e códigos municipais;
- menor e maior data de aplicação observadas;
- possíveis candidatos cujo texto da descrição mencione dengue.

O relatório contém agregações, não linhas individuais. Campos que não fazem parte da lista de dimensões investigadas não têm seus valores exportados.

## Limitações e interpretação

- Uma amostra paginada não comprova a completude anual nem a cobertura territorial.
- A presença de uma descrição com a palavra "dengue" gera um candidato, não uma classificação definitiva.
- O código da vacina precisa ser confirmado em dicionário oficial do PNI antes de ser usado no ETL.
- Município do paciente e município do estabelecimento são dimensões distintas e não devem ser intercambiadas.
- Os valores de idade são apresentados como observados. A conversão para anos ou faixas etárias depende da validação da codificação original.
- O parâmetro `offset` segue a paginação já utilizada no cliente da API do projeto; a execução diagnóstica não substitui a validação da paginação completa.
- Nenhum dado é inserido no banco de dados.

## Próxima decisão

Após revisar o artefato, validar os códigos de vacina em documentação oficial e verificar se os endpoints cobrem os períodos e municípios necessários. Somente então decidir a fonte definitiva e desenhar a carga de vacinação normalizada.
