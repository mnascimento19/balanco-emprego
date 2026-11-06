-- Pergunta: qual foi o saldo de empregos declarado em outubro/2025, e de onde veio?
-- Ideia: agrupar por arquivo (MOV, FOR, EXC) e somar saldo_efetivo (admissão = +1,
-- desligamento = -1, e exclusão entra com sinal invertido).
SELECT
    arquivo_tipo,
    count(*)                                  AS linhas,
    count(*) FILTER (WHERE saldo = 1)         AS admissoes,
    count(*) FILTER (WHERE saldo = -1)        AS desligamentos,
    sum(saldo_efetivo)                        AS saldo
FROM movimentacao
WHERE competencia_declaracao = '202510'
GROUP BY arquivo_tipo
UNION ALL
SELECT 'TOTAL', count(*), count(*) FILTER (WHERE saldo = 1),
       count(*) FILTER (WHERE saldo = -1), sum(saldo_efetivo)
FROM movimentacao
WHERE competencia_declaracao = '202510'
ORDER BY 1;
