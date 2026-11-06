# Radar do Emprego

Pipeline de dados públicos do Novo CAGED: coleta, limpeza, carga em Postgres,
indicadores em SQL e um painel em Streamlit, orquestrado com Prefect,
empacotado com Docker e com parte do fluxo na AWS.

Em construção.

## Rodando localmente

```bash
docker compose up -d                                   # Postgres (cria o schema na 1ª vez)
pip install -r requirements.txt
python -m pipeline.cli dimensoes data/raw/layout.xlsx  # tabelas de apoio
python -m pipeline.cli carga data/extracted/CAGEDMOV202510.txt
pytest                                                 # testes de idempotência
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
