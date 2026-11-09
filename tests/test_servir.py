"""O `servir` não pode fingir que agenda: sem servidor do Prefect nada dispara, então ele deve recusar."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("prefect")

RAIZ = Path(__file__).resolve().parent.parent


def test_servir_recusa_rodar_sem_servidor_do_prefect():
    env = {k: v for k, v in os.environ.items() if k != "PREFECT_API_URL"}
    r = subprocess.run([sys.executable, "-m", "flows.servir"], cwd=RAIZ, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 1
    assert "prefect server start" in r.stderr
