"""Carrega as tabelas de dimensão a partir do dicionário oficial (layout.xlsx).

Idempotente: usa upsert, então rodar de novo só atualiza descrições.
"""
import unicodedata

import openpyxl

# aba do xlsx (sem acento, minúscula) -> tabela
ABAS = {
    "regiao": "regiao",
    "uf": "uf",
    "secao": "secao",
    "tipomovimentacao": "tipo_movimentacao",
    "graudeinstrucao": "grau_instrucao",
    "racacor": "raca_cor",
    "sexo": "sexo",
    "categoria": "categoria",
    "municipio": "municipio",
    "subclasse": "subclasse",
    "cbo2002ocupacao": "cbo",
}


def _normaliza(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def carregar_dimensoes(conn, caminho_xlsx):
    wb = openpyxl.load_workbook(caminho_xlsx, read_only=True)
    totais = {}
    with conn.transaction():
        for aba in wb.sheetnames:
            tabela = ABAS.get(_normaliza(aba))
            if tabela is None:
                continue
            linhas = [
                (str(c).strip() if tabela == "secao" else int(c), str(d).strip())
                for c, d in list(wb[aba].iter_rows(values_only=True))[1:]
                if c is not None
            ]
            conn.cursor().executemany(
                f"INSERT INTO {tabela} (codigo, descricao) VALUES (%s, %s) "
                "ON CONFLICT (codigo) DO UPDATE SET descricao = EXCLUDED.descricao",
                linhas,
            )
            totais[tabela] = len(linhas)
    return totais
