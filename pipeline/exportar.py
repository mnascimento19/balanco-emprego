"""Exporta a view de indicadores para CSV, para o painel rodar sem banco (versão publicada)."""
import csv
from pathlib import Path

COLUNAS = ["mes", "estado", "setor", "admissoes", "desligamentos", "saldo"]
CSV_PADRAO = Path("app/dados/indicadores.csv")


def exportar_indicadores(conn, destino: Path = CSV_PADRAO) -> int:
    """Grava mv_indicadores em CSV ordenado (diffs estáveis no git). Retorna o nº de linhas."""
    cur = conn.execute(
        f"SELECT {', '.join(COLUNAS)} FROM mv_indicadores ORDER BY mes, estado, setor"
    )
    linhas = cur.fetchall()
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f, lineterminator="\n")
        escritor.writerow(COLUNAS)
        escritor.writerows(linhas)
    return len(linhas)
