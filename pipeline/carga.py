"""Carga idempotente dos arquivos CAGED (MOV/FOR/EXC).

Unidade de idempotência: o arquivo (tipo + competência da declaração).
- mesmo hash já carregado  -> pula
- hash diferente (governo republicou) -> apaga o arquivo antigo e reinsere, na mesma transação
- falha no meio -> rollback, nada fica pela metade
Linhas idênticas dentro de um arquivo são mantidas (são eventos distintos).

Desempenho: o arquivo vai cru para uma tabela temporária (COPY, sem parsing em Python) e a
conversão de tipos é feita pelo Postgres num único INSERT ... SELECT.
"""
import hashlib
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

NOME_ARQUIVO = re.compile(r"^CAGED(MOV|FOR|EXC)(\d{6})\.txt$")

# coluna da tabela -> (coluna do arquivo, expressão de conversão; {c} = coluna de staging)
COLUNAS = [
    ("competencia_evento", "competênciamov", "{c}"),
    ("regiao", "região", "{c}::smallint"),
    ("uf", "uf", "{c}::smallint"),
    ("municipio", "município", "{c}::integer"),
    ("secao", "seção", "{c}"),
    ("subclasse", "subclasse", "{c}::integer"),
    ("saldo", "saldomovimentação", "{c}::smallint"),
    ("cbo", "cbo2002ocupação", "{c}::integer"),
    ("categoria", "categoria", "{c}::smallint"),
    ("grau_instrucao", "graudeinstrução", "{c}::smallint"),
    ("idade", "idade", "{c}::smallint"),
    ("horas_contratuais", "horascontratuais",
     "CASE WHEN abs(replace({c}, ',', '.')::numeric) >= 1000 THEN NULL ELSE replace({c}, ',', '.')::numeric END"),
    ("raca_cor", "raçacor", "{c}::smallint"),
    ("sexo", "sexo", "{c}::smallint"),
    ("tipo_movimentacao", "tipomovimentação", "{c}::smallint"),
    ("salario", "salário",
     "CASE WHEN abs(replace({c}, ',', '.')::numeric) >= 10000000000 THEN NULL ELSE replace({c}, ',', '.')::numeric END"),
]


# coluna da tabela de fatos -> tabela de dimensão. Validado em lote antes do INSERT, no lugar de
# FKs (que custavam uma consulta por linha). Colunas nulas não são validadas.
DIMENSOES_VALIDADAS = {
    "uf": "uf",
    "secao": "secao",
    "categoria": "categoria",
    "grau_instrucao": "grau_instrucao",
    "raca_cor": "raca_cor",
    "sexo": "sexo",
    "tipo_movimentacao": "tipo_movimentacao",
}


def identificar(caminho: Path):
    m = NOME_ARQUIVO.match(caminho.name)
    if not m:
        raise ValueError(f"Nome de arquivo inesperado: {caminho.name}")
    return m.group(1), m.group(2)


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _cabecalho(caminho: Path) -> list[str]:
    with open(caminho, encoding="utf-8") as f:
        return f.readline().strip().split(";")


def carregar_arquivo(conn, caminho) -> str:
    """Retorna 'carregado', 'atualizado' ou 'pulado'."""
    caminho = Path(caminho)
    tipo, competencia = identificar(caminho)
    sha = sha256_arquivo(caminho)

    cabecalho = _cabecalho(caminho)
    posicao = {nome: f"c{i}" for i, nome in enumerate(cabecalho)}
    faltando = [o for _, o, _ in COLUNAS if o not in posicao]
    if faltando:
        raise ValueError(f"Colunas ausentes no arquivo: {faltando}")

    origem_de = {c: o for c, o, _ in COLUNAS}

    with conn.transaction():
        cur = conn.cursor()
        cur.execute(
            "SELECT sha256 FROM carga_arquivo WHERE arquivo_tipo=%s AND competencia_declaracao=%s",
            (tipo, competencia),
        )
        existente = cur.fetchone()
        if existente and existente[0] == sha:
            return "pulado"
        if existente:  # republicado: o CASCADE apaga as movimentações antigas
            cur.execute(
                "DELETE FROM carga_arquivo WHERE arquivo_tipo=%s AND competencia_declaracao=%s",
                (tipo, competencia),
            )
        cur.execute(
            "INSERT INTO carga_arquivo (arquivo_tipo, competencia_declaracao, sha256, tamanho_bytes, linhas) "
            "VALUES (%s, %s, %s, %s, 0)",
            (tipo, competencia, sha, caminho.stat().st_size),
        )

        # 1) arquivo cru -> tabela temporária (tudo texto)
        colunas_stg = ", ".join(f"c{i} text" for i in range(len(cabecalho)))
        cur.execute(f"CREATE TEMP TABLE stg ({colunas_stg}) ON COMMIT DROP")
        with open(caminho, "rb") as f, cur.copy(
            "COPY stg FROM STDIN WITH (FORMAT csv, DELIMITER ';', HEADER true, ENCODING 'UTF8')"
        ) as copy:
            while bloco := f.read(1 << 20):
                copy.write(bloco)

        # 2) códigos desconhecidos nas dimensões abortam a carga (rollback)
        expressoes = {c: e for c, _, e in COLUNAS}
        for coluna, dim in DIMENSOES_VALIDADAS.items():
            valor = expressoes[coluna].format(c=posicao[origem_de[coluna]])
            cur.execute(
                f"SELECT s.v FROM (SELECT DISTINCT {valor} AS v FROM stg) s "
                f"LEFT JOIN {dim} d ON d.codigo = s.v WHERE s.v IS NOT NULL AND d.codigo IS NULL"
            )
            desconhecidos = [r[0] for r in cur.fetchall()]
            if desconhecidos:
                raise ValueError(f"{caminho.name}: códigos de {coluna} fora da dimensão {dim}: {desconhecidos}")

        # Valores que não cabem na coluna (erro da fonte, ex.: salário de 7,05e+10) viram NULL e a
        # linha é mantida, pois ela ainda conta para o saldo de empregos. Avisa quantas foram.
        for coluna, limite in (("salario", 10**10), ("horas_contratuais", 1000)):
            ref = posicao[origem_de[coluna]]
            cur.execute(
                f"SELECT count(*) FROM stg WHERE {ref} IS NOT NULL "
                f"AND abs(replace({ref}, ',', '.')::numeric) >= {limite}"
            )
            if (n_ruins := cur.fetchone()[0]):
                log.warning("%s: %d linha(s) com %s >= %s gravadas com NULL", caminho.name, n_ruins, coluna, limite)

        # 3) conversão de tipos e carga final, tudo dentro do Postgres
        destino = ", ".join(["arquivo_tipo", "competencia_declaracao"] + [c for c, _, _ in COLUNAS])
        origem = ", ".join(
            ["%s", "%s"] + [expr.format(c=posicao[orig]) for _, orig, expr in COLUNAS]
        )
        cur.execute(
            f"INSERT INTO movimentacao ({destino}) SELECT {origem} FROM stg",
            (tipo, competencia),
        )
        n = cur.rowcount
        cur.execute(
            "UPDATE carga_arquivo SET linhas=%s WHERE arquivo_tipo=%s AND competencia_declaracao=%s",
            (n, tipo, competencia),
        )
    return "atualizado" if existente else "carregado"
