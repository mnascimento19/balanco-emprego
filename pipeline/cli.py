"""Uso:
  python -m pipeline.cli schema
  python -m pipeline.cli views
  python -m pipeline.cli refresh
  python -m pipeline.cli exportar [app/dados/indicadores.csv]
  python -m pipeline.cli exportar-arquivos [data/extracted] [tests/fixtures/layout.xlsx]   (sem banco)
  python -m pipeline.cli dimensoes data/raw/layout.xlsx
  python -m pipeline.cli carga data/extracted/CAGEDMOV202510.txt [...]
"""
import sys
from pathlib import Path

from .carga import carregar_arquivo
from .db import conectar
from .dimensoes import carregar_dimensoes
from .exportar import CSV_PADRAO, exportar_dos_arquivos, exportar_indicadores


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, args = argv[1], argv[2:]
    if cmd == "exportar-arquivos":  # não precisa de banco nem de Docker
        pasta = Path(args[0]) if args else Path("data/extracted")
        layout = Path(args[1]) if len(args) > 1 else Path("tests/fixtures/layout.xlsx")
        print(f"{exportar_dos_arquivos(pasta, layout)} linhas -> {CSV_PADRAO}")
        return 0
    with conectar() as conn:
        if cmd == "schema":
            for sql in sorted(Path("sql/schema").glob("*.sql")):
                conn.execute(sql.read_text(encoding="utf-8"))
        elif cmd == "views":
            for sql in sorted(Path("sql/views").glob("*.sql")):
                conn.execute(sql.read_text(encoding="utf-8"))
        elif cmd == "refresh":
            conn.execute("REFRESH MATERIALIZED VIEW mv_indicadores")
        elif cmd == "exportar":
            destino = Path(args[0]) if args else CSV_PADRAO
            print(f"{exportar_indicadores(conn, destino)} linhas -> {destino}")
        elif cmd == "dimensoes":
            print(carregar_dimensoes(conn, args[0]))
        elif cmd == "carga":
            for a in args:
                print(a, "->", carregar_arquivo(conn, a))
        else:
            print(__doc__)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
