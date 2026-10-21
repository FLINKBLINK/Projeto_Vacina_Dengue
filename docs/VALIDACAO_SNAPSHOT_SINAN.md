# Snapshot imutável e auditoria temporal do SINAN

## Objetivo

A carga completa do workflow baixa o ZIP anual oficial uma única vez e reutiliza os mesmos bytes para o ETL e para a auditoria de reconciliação. O SHA-256 do ZIP fica registrado como artefato, junto com o SQLite e os relatórios JSON.

Isso elimina a divergência artificial causada por duas baixadas independentes quando o Ministério atualiza o arquivo entre etapas. Não garante que a fonte permaneça imutável ao longo do tempo; por isso o hash é parte da evidência da execução.

## Workflow

No modo `carga_completa`, o workflow:

1. baixa o ZIP oficial para um arquivo temporário;
2. calcula e publica o SHA-256;
3. passa o mesmo caminho ao ETL por `--sinan-zip`;
4. passa o mesmo caminho à auditoria por `--zip`;
5. publica SQLite, auditoria, qualidade e hash como artefatos.

O comportamento padrão do ETL continua baixando o ZIP por conta própria quando `--sinan-zip` não é informado. O modo amostra também permanece inalterado.

## Auditoria entre anos

Depois de reunir em um mesmo SQLite as cargas anuais desejadas, execute:

```bash
python -m scripts.auditar_sinan_entre_anos \
  --db data/processed/sinan_historico.db \
  --years 2023,2024,2025 \
  --output data/processed/auditoria_sinan_entre_anos.json
```

O relatório conta registros por ano de arquivo, destaca divergências de `NU_ANO`, resume os anos encontrados nos campos de data e identifica assinaturas clínicas conservadoras presentes em mais de um ano.

Assinaturas coincidentes não são prova de duplicidade de paciente. As linhas de origem de arquivos diferentes podem representar snapshots atualizados, e os dados disponíveis não oferecem uma chave universal de pessoa. Portanto, o relatório apenas sinaliza ocorrências para revisão e não elimina, mescla ou reclassifica registros.

## Critérios de interpretação

- Ano do arquivo, `NU_ANO`, ano de notificação e ano de início de sintomas são conceitos diferentes.
- Datas e anos discordantes devem ser investigados, não corrigidos automaticamente.
- A integridade estrutural aprovada não implica qualidade semântica totalmente aprovada.
- Compare snapshots usando o hash e a data de extração registrados.
