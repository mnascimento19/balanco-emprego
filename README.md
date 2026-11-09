# Radar do Emprego

Pipeline de dados públicos do Novo CAGED: coleta, limpeza, carga em Postgres,
indicadores em SQL e um painel em Streamlit, orquestrado com Prefect e
empacotado com Docker.

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

## Painel publicado (Streamlit Community Cloud)

A versão online não tem banco: ela lê `app/dados/indicadores.csv`, um recorte agregado (mês x estado
x setor, ~6,7 mil linhas, só números públicos) exportado do banco. O painel tenta o banco primeiro e,
se não conseguir, usa o arquivo, e avisa na tela qual das duas fontes está usando.

```bash
python -m pipeline.cli exportar     # regenera app/dados/indicadores.csv a partir do banco
```

Para publicar: em share.streamlit.io, "New app", escolha este repositório, branch `main` e o arquivo
`app/app.py`. As dependências vêm de `app/requirements.txt` (só o necessário para o painel). Os dados
da versão online ficam congelados até alguém rodar a exportação e enviar o arquivo atualizado.

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
