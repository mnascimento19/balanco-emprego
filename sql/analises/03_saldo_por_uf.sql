-- Pergunta: em quais estados o emprego mais cresceu ou mais caiu em outubro/2025?
-- Inclui o saldo como % do total de admissões do estado, para comparar estados de tamanhos diferentes.
SELECT
    u.descricao                                                         AS estado,
    sum(m.saldo_efetivo) FILTER (WHERE m.saldo = 1)                     AS admissoes,
    -sum(m.saldo_efetivo) FILTER (WHERE m.saldo = -1)                   AS desligamentos,
    sum(m.saldo_efetivo)                                                AS saldo,
    round(100.0 * sum(m.saldo_efetivo)
          / NULLIF(sum(m.saldo_efetivo) FILTER (WHERE m.saldo = 1), 0), 1) AS saldo_pct_das_admissoes
FROM movimentacao m
JOIN uf u ON u.codigo = m.uf
WHERE m.competencia_declaracao = '202510'
GROUP BY u.descricao
ORDER BY saldo DESC;
