# Projeto Vacina Dengue

Dashboard interativo para explorar dados de vacinação contra a dengue, população e notificações/casos de dengue nos municípios da região de Ribeirão Preto (SP), com Python e Streamlit.

## Objetivos

- Reproduzir e auditar as análises do artigo acadêmico.
- Explorar doses registradas por município, mês, sexo e faixa etária.
- Comparar registros de dengue por município e período.
- Calcular estatísticas descritivas e correlações de Pearson, apresentando o tamanho da amostra e o p-valor.
- Tornar explícitas as limitações das bases e as divergências encontradas na auditoria.

## Estrutura esperada dos dados

Coloque os arquivos fornecidos na pasta `data/raw/` (ou na raiz do repositório):

- `IBGE_TRATADO.xlsx`
- `DADOS_EXTRAIDOS.xlsx`
- `SINAN_2023.xlsx`
- `SINAN_2024.xlsx`
- `SINAN_2025.xlsx`

Os arquivos não são gerados pelo aplicativo. Devem ser incluídos no repositório pelo responsável pelo projeto, respeitando as condições de uso e publicação das fontes originais.

## Executar localmente

Recomendado: Python 3.10 ou superior.

```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\\Scripts\\activate    # Windows
pip install -r requirements.txt
streamlit run app.py
```

Se os arquivos ainda não estiverem em `data/raw/` nem na raiz, o aplicativo abrirá e informará quais arquivos estão faltando.

## Convenções e cautelas analíticas

- Brodowski é excluído das análises principais, seguindo o artigo, mas permanece disponível para auditoria quando os dados permitem.
- O indicador calculado a partir de doses/população é chamado **doses registradas por 100 habitantes**, não cobertura vacinal oficial: doses não equivalem necessariamente a pessoas únicas vacinadas e a população total não é necessariamente a população elegível.
- Os arquivos SINAN são tratados por data de notificação real. Registros cuja data não corresponde ao ano indicado no nome do arquivo são sinalizados, não reclassificados silenciosamente.
- A quantidade de linhas dos arquivos SINAN é apresentada como **registros da base**; só deve ser interpretada como casos confirmados se a extração original garantir essa classificação.
- A base de vacinação de 2025 identificada na auditoria contém janeiro a abril, não maio. O dashboard não inventa dados de maio.
- Correlação municipal não demonstra causalidade nem mede eficácia individual da vacina.
- Valores ausentes não são automaticamente substituídos por zero.

## Auditoria inicial das bases

A conferência inicial identificou, entre outros pontos, diferença entre os dados SINAN de 2025 e o total descrito no artigo para janeiro–maio, além da ausência de maio na planilha de vacinação de 2025. Consulte o painel de qualidade de dados para ver as verificações feitas em tempo de execução. Divergências devem ser resolvidas na origem ou descritas como limitações, nunca corrigidas por ajuste artificial.

## Fontes descritas no artigo

- IBGE — Censo Demográfico 2022: https://www.ibge.gov.br/estatisticas/sociais/rendimento-despesa-e-consumo/22827-censo-demografico-2022.html
- DATASUS — Transferência de arquivos: https://datasus.saude.gov.br/transferencia-de-arquivos/
- RNDS / InfoMS — Vacinação: https://infoms.saude.gov.br/extensions/SEIDIGI_DEMAS_VACINACAO_CALENDARIO_NACIONAL_OCORRENCIA/

## Auditoria

A auditoria inicial das planilhas e as divergências verificadas estão documentadas em [docs/AUDITORIA_DADOS.md](docs/AUDITORIA_DADOS.md).

## Status

Estrutura inicial Python/Streamlit. As análises devem ser validadas contra os arquivos de origem e o artigo antes de serem consideradas resultados finais.
