"""Exporta os indicadores para CSV, para o painel rodar sem banco (versão publicada).

Dois caminhos que dão o mesmo resultado (um teste garante a equivalência):
- `exportar_indicadores`: lê a view mv_indicadores do Postgres.
- `indicadores_dos_arquivos`: calcula direto dos arquivos CAGEDMOV extraídos, sem banco nem Docker.
"""
import csv
import re
from pathlib import Path

import openpyxl
import pandas as pd

from .dimensoes import _normaliza

COLUNAS = ["mes", "estado", "setor", "admissoes", "desligamentos", "saldo"]
CSV_PADRAO = Path("app/dados/indicadores.csv")


def _gravar(linhas, destino: Path) -> int:
    linhas = list(linhas)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f, lineterminator="\n")
        escritor.writerow(COLUNAS)
        escritor.writerows(linhas)
    return len(linhas)


def exportar_indicadores(conn, destino: Path = CSV_PADRAO) -> int:
    """Grava mv_indicadores em CSV ordenado (diffs estáveis no git). Retorna o nº de linhas."""
    linhas = conn.execute(f"SELECT {', '.join(COLUNAS)} FROM mv_indicadores").fetchall()
    # ordena em Python: a ordenação do Postgres depende do idioma do servidor e mudaria o arquivo
    return _gravar(sorted(linhas, key=lambda r: (r[0], r[1], r[2])), destino)


def _dimensao(layout_xlsx: Path, aba: str) -> dict:
    wb = openpyxl.load_workbook(layout_xlsx, read_only=True)
    nome = next(n for n in wb.sheetnames if _normaliza(n) == aba)
    return {str(c).strip(): str(d).strip() for c, d in list(wb[nome].iter_rows(values_only=True))[1:] if c is not None}


def indicadores_dos_arquivos(pasta_extraidos: Path, layout_xlsx: Path) -> pd.DataFrame:
    """Mesma conta da view mv_indicadores, direto dos CAGEDMOV*.txt (só movimentações no prazo)."""
    ufs, secoes = _dimensao(layout_xlsx, "uf"), _dimensao(layout_xlsx, "secao")
    partes = []
    for arq in sorted(Path(pasta_extraidos).glob("CAGEDMOV??????.txt")):
        mes = re.search(r"CAGEDMOV(\d{6})", arq.name).group(1)
        df = pd.read_csv(arq, sep=";", usecols=["uf", "seção", "saldomovimentação"], encoding="utf-8",
                         dtype={"uf": str, "seção": str})
        df["saldo"] = df["saldomovimentação"].astype(int)
        g = df.groupby(["uf", "seção"]).agg(
            admissoes=("saldo", lambda s: int((s == 1).sum())),
            desligamentos=("saldo", lambda s: int((s == -1).sum())),
            saldo=("saldo", "sum"),
        ).reset_index()
        g.insert(0, "mes", mes)
        partes.append(g)
    tudo = pd.concat(partes, ignore_index=True)
    tudo["estado"] = tudo["uf"].map(lambda c: ufs[str(int(c))])
    tudo["setor"] = tudo["seção"].map(secoes)
    tudo["saldo"] = tudo["saldo"].astype(int)
    return tudo[COLUNAS].sort_values(["mes", "estado", "setor"]).reset_index(drop=True)


def exportar_dos_arquivos(pasta_extraidos: Path, layout_xlsx: Path, destino: Path = CSV_PADRAO) -> int:
    df = indicadores_dos_arquivos(pasta_extraidos, layout_xlsx)
    return _gravar(df.itertuples(index=False, name=None), destino)
