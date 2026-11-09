-- Base de indicadores do painel: uma linha por mês x estado x setor.
--
-- Mês = o mês do arquivo CAGEDMOV, ou seja, as movimentações declaradas no prazo. Esse é exatamente
-- o critério dos números que o Ministério divulga: conferido contra dez/2025 (-618.164),
-- ago/2026 (+165.827) e set/2026 (+121.305), com diferença zero nos três.
--
-- Os arquivos CAGEDFOR (fora do prazo) e CAGEDEXC (exclusões) ficam de fora de propósito: eles trazem
-- ajustes de meses ANTERIORES, então somá-los ao mês corrente mistura períodos. Continuam na tabela
-- movimentacao, para quem quiser estudar as revisões.
--
-- Materializada porque agrupar dezenas de milhões de linhas a cada clique deixaria o painel lento;
-- o flow do Prefect faz REFRESH ao fim de cada carga.
DROP MATERIALIZED VIEW IF EXISTS mv_indicadores;

CREATE MATERIALIZED VIEW mv_indicadores AS
SELECT
    m.competencia_declaracao                                        AS mes,
    m.uf,
    u.descricao                                                     AS estado,
    m.secao,
    s.descricao                                                     AS setor,
    COALESCE(sum(m.saldo) FILTER (WHERE m.saldo = 1), 0)            AS admissoes,
    COALESCE(-sum(m.saldo) FILTER (WHERE m.saldo = -1), 0)          AS desligamentos,
    sum(m.saldo)                                                    AS saldo
FROM movimentacao m
JOIN uf    u ON u.codigo = m.uf
JOIN secao s ON s.codigo = m.secao
WHERE m.arquivo_tipo = 'MOV'
GROUP BY m.competencia_declaracao, m.uf, u.descricao, m.secao, s.descricao;

-- Índice único: permite REFRESH ... CONCURRENTLY (o site continua lendo durante a atualização).
CREATE UNIQUE INDEX ux_mv_indicadores ON mv_indicadores (mes, uf, secao);
