"""Carga idempotente dos arquivos CAGED (MOV/FOR/EXC).

Unidade de idempotência: o arquivo (tipo + competência da declaração).
- mesmo hash já carregado  -> pula
- hash diferente (governo republicou) -> apaga o arquivo antigo e reinsere, na mesma transação
- falha no meio -> rollback, nada fica pela metade
Linhas idênticas dentro de um arquivo são mantidas (são eventos distintos).
"""
import csv
import hashlib
import re
from pathlib import Path

NOME_ARQUIVO = re.compile(r"^CAGED(MOV|FOR|EXC)(\d{6})\.txt$")

# coluna da tabela -> coluna do arquivo
COLUNAS = [
    ("arquivo_tipo", None),
    ("competencia_declaracao", None),
    ("competencia_evento", "competênciamov"),
    ("regiao", "região"),
    ("uf", "uf"),
    ("municipio", "município"),
    ("secao", "seção"),
    ("subclasse", "subclasse"),
    ("saldo", "saldomovimentação"),
    ("cbo", "cbo2002ocupação"),
    ("categoria", "categoria"),
    ("grau_instrucao", "graudeinstrução"),
    ("idade", "idade"),
    ("horas_contratuais", "horascontratuais"),
    ("raca_cor", "raçacor"),
    ("sexo", "sexo"),
    ("tipo_movimentacao", "tipomovimentação"),
    ("salario", "salário"),
]
DECIMAIS = {"horascontratuais", "salário"}


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


def _linhas(caminho: Path, tipo: str, competencia: str):
    with open(caminho, encoding="utf-8", newline="") as f:
        for reg in csv.DictReader(f, delimiter=";"):
            saida = []
            for col, origem in COLUNAS:
                if origem is None:
                    saida.append(tipo if col == "arquivo_tipo" else competencia)
                    continue
                v = reg[origem].strip()
                if v == "":
                    v = None
                elif origem in DECIMAIS:
                    v = v.replace(",", ".")
                saida.append(v)
            yield saida


def carregar_arquivo(conn, caminho) -> str:
    """Retorna 'carregado', 'atualizado' ou 'pulado'."""
    caminho = Path(caminho)
    tipo, competencia = identificar(caminho)
    sha = sha256_arquivo(caminho)

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
        colunas = ", ".join(c for c, _ in COLUNAS)
        n = 0
        with cur.copy(f"COPY movimentacao ({colunas}) FROM STDIN") as copy:
            for linha in _linhas(caminho, tipo, competencia):
                copy.write_row(linha)
                n += 1
        cur.execute(
            "UPDATE carga_arquivo SET linhas=%s WHERE arquivo_tipo=%s AND competencia_declaracao=%s",
            (n, tipo, competencia),
        )
    return "atualizado" if existente else "carregado"
