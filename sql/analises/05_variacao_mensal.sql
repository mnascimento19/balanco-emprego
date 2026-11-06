-- Pergunta: como o saldo de empregos mudou em relação ao mês anterior?
-- Técnica: LAG() pega o valor da linha anterior na ordem dos meses.
-- Só entram meses cujo arquivo MOV foi carregado (os FOR/EXC trazem pedaços de meses antigos, e
-- compará-los com um mês completo daria uma variação falsa).
-- Com apenas 1 mês carregado a variação aparece como NULL. Ela passa a funcionar ao carregar mais meses.
WITH meses_completos AS (
    SELECT competencia_declaracao AS mes FROM carga_arquivo WHERE arquivo_tipo = 'MOV'
),
saldo_mes AS (
    SELECT m.competencia_declaracao AS mes, sum(m.saldo_efetivo) AS saldo
    FROM movimentacao m
    JOIN meses_completos c ON c.mes = m.competencia_declaracao
    GROUP BY m.competencia_declaracao
)
SELECT
    mes,
    saldo,
    lag(saldo) OVER (ORDER BY mes)                AS saldo_mes_anterior,
    saldo - lag(saldo) OVER (ORDER BY mes)        AS variacao
FROM saldo_mes
ORDER BY mes;
