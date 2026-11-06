# Radar do Emprego

Pipeline de dados públicos do Novo CAGED: coleta, limpeza, carga em Postgres,
indicadores em SQL e um painel em Streamlit, orquestrado com Prefect,
empacotado com Docker e com parte do fluxo na AWS.

Em construção.

## Rodando localmente

```bash
docker compose up -d                                   # Postgres (cria o schema na 1ª vez)
pip install -r requirements.txt
python -m pipeline.cli dimensoes data/raw/layout.xlsx  # tabelas de apoio (dicionário oficial)
python -m pipeline.cli views                           # materialized view do painel
python -m flows.carga_mensal                           # baixa e carrega os últimos 12 meses
streamlit run app/app.py                               # painel em http://localhost:8501
pytest                                                 # testes de idempotência
```

Para deixar a carga agendada (todo dia às 08:00, só carrega o que for novo):
`python -m flows.servir`.

## Arquitetura

```
FTP do governo ──► pipeline/coleta.py ──► data/raw (.7z) ──► data/extracted (.txt)
                                                                  │
   flows/carga_mensal.py (Prefect: retries, timeouts, agenda)     ▼
                                              pipeline/carga.py (COPY + validação, idempotente)
                                                                  │
                                                         Postgres (movimentacao)
                                                                  │
                                              mv_indicadores (materialized view)
                                                                  │
                                                       app/app.py (Streamlit)
```

## Idempotência e deduplicação

O arquivo do governo não tem identificador de linha, e há movimentações idênticas
(mesmos campos) que são eventos reais distintos. Por isso a deduplicação é **por arquivo**,
não por linha:

- `carga_arquivo` guarda o hash (sha256) de cada arquivo carregado (tipo + mês da declaração).
- Mesmo hash: a carga é pulada. Hash diferente (o governo republicou): apaga o arquivo antigo
  e reinsere, na mesma transação. Se algo falhar no meio, nada é gravado.
- Linhas idênticas dentro do arquivo são mantidas.
- Exclusões (`EXC`) entram com sinal invertido em `saldo_efetivo`; as análises somam essa coluna.

## Decisões de desempenho

A carga de um mês (4,4 milhões de linhas) caiu de 33 min para 6 min. Medindo, o gargalo não era o
Python: eram as chaves estrangeiras da tabela de fatos (uma consulta por linha, 94 s contra 3 s para
500 mil linhas). Elas foram trocadas por uma validação em lote dos códigos antes do `INSERT`, que
aborta a carga se aparecer um código fora do dicionário.
