import os

import psycopg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://radar:radar@localhost:5432/radar")


def conectar():
    return psycopg.connect(DATABASE_URL)
