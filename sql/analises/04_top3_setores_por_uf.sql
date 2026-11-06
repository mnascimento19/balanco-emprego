-- Pergunta: quais são os 3 setores que mais geraram emprego em cada estado em outubro/2025?
-- Técnica: window function. ROW_NUMBER() numera os setores dentro de cada estado (PARTITION BY),
-- do maior para o menor saldo; depois filtramos só as posições 1 a 3.
WITH saldo_uf_setor AS (
    SELECT uf, secao, sum(saldo_efetivo) AS saldo
    FROM movimentacao
    WHERE competencia_declaracao = '202510'
    GROUP BY uf, secao
),
ranqueado AS (
    SELECT
        uf, secao, saldo,
        row_number() OVER (PARTITION BY uf ORDER BY saldo DESC) AS posicao
    FROM saldo_uf_setor
)
SELECT u.descricao AS estado, r.posicao, s.descricao AS setor, r.saldo
FROM ranqueado r
JOIN uf    u ON u.codigo = r.uf
JOIN secao s ON s.codigo = r.secao
WHERE r.posicao <= 3
ORDER BY u.descricao, r.posicao;
