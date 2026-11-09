-- Pergunta: como o saldo de empregos mudou em relação ao mês anterior?
-- Técnica: LAG() pega o valor da linha anterior na ordem dos meses.
-- Só entram meses cujo arquivo MOV foi carregado (os FOR/EXC trazem pedaços de meses antigos, e
-- compará-los com um mês completo daria uma variação falsa).
-- Com 12 meses carregados, o primeiro mês não tem anterior e a variação dele aparece como NULL.
WITH meses_completos AS (
    SELECT competencia_declaracao AS mes FROM carga_arquivo WHERE arquivo_tipo = 'MOV'
),
saldo_mes AS (
    SELECT m.competencia_declaracao AS mes, sum(m.saldo) AS saldo
    FROM movimentacao m
    JOIN meses_completos c ON c.mes = m.competencia_declaracao
    WHERE m.arquivo_tipo = 'MOV'  -- mesmo critério do painel e dos números do Ministério
    GROUP BY m.competencia_declaracao
)
SELECT
    mes,
    saldo,
    lag(saldo) OVER (ORDER BY mes)                AS saldo_mes_anterior,
    saldo - lag(saldo) OVER (ORDER BY mes)        AS variacao
FROM saldo_mes
ORDER BY mes;
