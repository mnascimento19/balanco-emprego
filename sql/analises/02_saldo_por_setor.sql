-- Pergunta: quais setores mais contrataram e quais mais demitiram em outubro/2025?
-- Setor = seção da CNAE. Usa uma CTE para calcular uma vez e depois ranquear.
-- Admissões e desligamentos são líquidos de exclusões (somam saldo_efetivo dentro de cada grupo).
WITH por_setor AS (
    SELECT
        m.secao,
        sum(m.saldo_efetivo) FILTER (WHERE m.saldo = 1)      AS admissoes,
        -sum(m.saldo_efetivo) FILTER (WHERE m.saldo = -1)    AS desligamentos,
        sum(m.saldo_efetivo)                                  AS saldo
    FROM movimentacao m
    WHERE m.arquivo_tipo = 'MOV' AND m.competencia_declaracao = '202510'
    GROUP BY m.secao
)
SELECT
    p.secao,
    s.descricao                                   AS setor,
    p.admissoes,
    p.desligamentos,
    p.saldo,
    rank() OVER (ORDER BY p.saldo DESC)           AS posicao
FROM por_setor p
JOIN secao s ON s.codigo = p.secao
ORDER BY p.saldo DESC;
