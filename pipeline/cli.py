"""Uso:
  python -m pipeline.cli schema
  python -m pipeline.cli views
  python -m pipeline.cli refresh
  python -m pipeline.cli dimensoes data/raw/layout.xlsx
  python -m pipeline.cli carga data/extracted/CAGEDMOV202510.txt [...]
"""
import sys
from pathlib import Path

from .carga import carregar_arquivo
from .db import conectar
from .dimensoes import carregar_dimensoes


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, args = argv[1], argv[2:]
    with conectar() as conn:
        if cmd == "schema":
            for sql in sorted(Path("sql/schema").glob("*.sql")):
                conn.execute(sql.read_text(encoding="utf-8"))
        elif cmd == "views":
            for sql in sorted(Path("sql/views").glob("*.sql")):
                conn.execute(sql.read_text(encoding="utf-8"))
        elif cmd == "refresh":
            conn.execute("REFRESH MATERIALIZED VIEW mv_indicadores")
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
