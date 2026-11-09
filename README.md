# Balanço do Emprego

![CI](https://github.com/mnascimento19/balanco-emprego/actions/workflows/ci.yml/badge.svg)

Quantos empregos formais o Brasil abriu ou fechou, mês a mês. Um pipeline de dados públicos do
**Novo CAGED** (Ministério do Trabalho e Emprego): coleta automática, carga idempotente em Postgres,
indicadores em SQL e um painel em Streamlit.

**Painel online: https://balanco-emprego.streamlit.app**

![Painel: saldo por setor](docs/img/painel-setores.png)

![Painel: evolução mensal](docs/img/painel-evolucao.png)

## O que os dados mostram

Doze meses, de outubro de 2025 a setembro de 2026, cerca de 52,8 milhões de movimentações:

- O saldo do período foi de **+803.706 empregos formais**.
- **Dezembro de 2025** sozinho fechou em **−615.689**, um padrão sazonal do emprego formal. Sem ele, o
  saldo dos outros onze meses é de +1,42 milhão. O melhor mês foi fevereiro de 2026 (+260.001).
- Setores que mais geraram vagas: serviços administrativos (+166 mil), saúde (+141 mil) e
  transporte (+104 mil). Os que mais perderam: agropecuária (−16,8 mil) e indústria de
  transformação (−6,5 mil).
- Estados: São Paulo (+138 mil), Rio de Janeiro (+90 mil) e Bahia (+77 mil) lideram. Tocantins
  (+300) e Rio Grande do Sul (+1,9 mil) mal saíram do zero.

Esses números usam o **mês em que a informação foi declarada**. Veja "Conferência com os números
oficiais" abaixo.

## Como funciona

```
FTP do governo ─► pipeline/coleta.py ─► data/raw (.7z) ─► data/extracted (.txt)
                                                               │
   flows/carga_mensal.py (Prefect: retries, timeouts, agenda)  ▼
                                           pipeline/carga.py (COPY + validação, idempotente)
                                                               │
                                                      Postgres (movimentacao)
                                                               │
                                           mv_indicadores (materialized view)
                                                  │                      │
                                        app/app.py (Streamlit)    pipeline exportar ─► CSV (painel online)
```

| Peça | O que faz |
|---|---|
| `pipeline/coleta.py` | Baixa e extrai os arquivos mensais, sem rebaixar o que já existe e sem deixar arquivo incompleto |
| `pipeline/carga.py` | Carga idempotente por arquivo, numa transação, com validação dos códigos |
| `sql/schema`, `sql/views` | Dimensões, tabela de fatos e a view materializada que alimenta o painel |
| `flows/carga_mensal.py` | Flow do Prefect: só processa meses novos, com retries e agenda diária |
| `app/app.py` | Painel com filtros por mês, estado e setor |
| `sql/analises` | Cinco análises em SQL (CTEs e window functions) |

## Decisões de engenharia

**Idempotência e deduplicação por arquivo.** O arquivo do governo não tem identificador de linha, e
há movimentações idênticas (mesmos campos) que são eventos reais distintos, como duas admissões
iguais no mesmo dia. Deduplicar por linha apagaria admissões verdadeiras. Por isso a unidade é o
arquivo:

- `carga_arquivo` guarda o hash (sha256) de cada arquivo carregado (tipo + mês da declaração).
- Mesmo hash: a carga é pulada. Hash diferente (o governo republicou): apaga o arquivo antigo e
  reinsere, na mesma transação. Se algo falhar no meio, nada é gravado.
- Exclusões (`EXC`) entram com sinal invertido em `saldo_efetivo`, a coluna que as análises somam.

**Desempenho, medido antes de mexer.** A carga de um mês (4,4 milhões de linhas) caiu de 33 para 6
minutos. A primeira otimização, no Python, não adiantou. Medindo por etapa, o gargalo eram as chaves
estrangeiras da tabela de fatos: uma consulta por linha, 94 s contra 3 s para 500 mil linhas. Elas
foram trocadas por uma validação em lote dos códigos antes do `INSERT`, que aborta a carga se
aparecer um código fora do dicionário oficial.

**Dados ruins da fonte.** Um único registro de abril de 2026 trazia salário de 70,5 bilhões
(`7,05e+10`) e derrubava a carga. A linha é mantida, porque ainda conta para o saldo, e o salário
vai como `NULL`, com aviso no log. O mesmo vale para `horas_contratuais`.

**Falhas esperadas.** A extração é atômica (um `MemoryError` não deixa um `.txt` vazio que seria
reaproveitado na tentativa seguinte), o Prefect tenta de novo com espera crescente e o banco
reinicia sozinho se o Docker cair.

## Conferência com os números oficiais

O painel conta por **mês de declaração**; o Ministério divulga por mês do evento, com ajustes. Por
isso os valores ficam um pouco abaixo dos divulgados:

| Mês | Divulgado | Painel | Diferença |
|---|---|---|---|
| Dezembro de 2025 | −618.164 | −615.689 | 0,4% |
| Agosto de 2026 | +165.827 | +159.677 | 3,7% |
| Setembro de 2026 | +121.305 | +113.579 | 6,4% |

Os valores divulgados vêm de notícias que reproduzem os números do Ministério, não do painel
oficial. A diferença maior em setembro não foi totalmente explicada. O sinal e a ordem de grandeza
batem em todos os meses conferidos.

## Rodando localmente

```bash
docker compose up -d                                   # Postgres (cria o schema na 1ª vez)
pip install -r requirements.txt
python -m pipeline.cli dimensoes tests/fixtures/layout.xlsx   # tabelas de apoio (dicionário oficial)
python -m pipeline.cli views                           # materialized view do painel
python -m flows.carga_mensal                           # baixa e carrega os últimos 12 meses
streamlit run app/app.py                               # painel em http://localhost:8501
pytest                                                 # testes
```

Para deixar a carga agendada (todo dia às 08:00, só carrega o que for novo):
`python -m flows.servir`.

## Painel online

A versão publicada (Streamlit Community Cloud) não tem banco: ela lê `app/dados/indicadores.csv`, um
recorte agregado (mês x estado x setor, 6.680 linhas, só números públicos) exportado do banco. O
painel tenta o banco primeiro e, se não conseguir, usa o arquivo. Os dados online ficam congelados
até alguém rodar a exportação e enviar o arquivo atualizado:

```bash
python -m pipeline.cli exportar
```

## Testes

Os testes rodam contra um Postgres real, com uma amostra de 1.000 linhas do arquivo de outubro de
2025 (`tests/fixtures`): idempotência, arquivo republicado, rollback em falha no meio da carga,
código fora do dicionário, salário absurdo, extração interrompida e o painel sem banco. O GitHub
Actions roda todos a cada push.
