-- Base de indicadores do site: uma linha por mês x estado x setor.
-- Materializada porque agrupar dezenas de milhões de linhas a cada clique deixaria o site lento;
-- o flow do Prefect faz REFRESH ao fim de cada carga.
-- Só entram meses completos (com arquivo MOV carregado). Mês = mês de declaração: o que foi
-- informado ao governo naquele mês, somando MOV, FOR e EXC (exclusões entram invertidas).
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_indicadores AS
SELECT
    m.competencia_declaracao                                        AS mes,
    m.uf,
    u.descricao                                                     AS estado,
    m.secao,
    s.descricao                                                     AS setor,
    COALESCE(sum(m.saldo_efetivo) FILTER (WHERE m.saldo = 1), 0)    AS admissoes,
    COALESCE(-sum(m.saldo_efetivo) FILTER (WHERE m.saldo = -1), 0)  AS desligamentos,
    sum(m.saldo_efetivo)                                            AS saldo
FROM movimentacao m
JOIN carga_arquivo c ON c.arquivo_tipo = 'MOV' AND c.competencia_declaracao = m.competencia_declaracao
JOIN uf    u ON u.codigo = m.uf
JOIN secao s ON s.codigo = m.secao
GROUP BY m.competencia_declaracao, m.uf, u.descricao, m.secao, s.descricao;

-- Índice único: permite REFRESH ... CONCURRENTLY (o site continua lendo durante a atualização).
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_indicadores ON mv_indicadores (mes, uf, secao);
