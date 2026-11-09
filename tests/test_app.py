"""O painel precisa funcionar sem banco (é como roda na versão publicada), lendo o CSV exportado."""
import csv
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app" / "app.py"
CABECALHO = ["mes", "estado", "setor", "admissoes", "desligamentos", "saldo"]


@pytest.fixture(autouse=True)
def cache_limpo():
    """st.cache_data vive no processo e vazaria os dados de um teste para o outro."""
    import streamlit as st

    st.cache_data.clear()
    yield


@pytest.fixture()
def csv_pequeno(tmp_path, monkeypatch):
    linhas = [
        ["202510", "Acre", "Construção", 100, 60, 40],
        ["202510", "Bahia", "Educação", 50, 70, -20],
        ["202511", "Acre", "Construção", 90, 80, 10],
        ["202511", "Bahia", "Educação", 60, 50, 10],
    ]
    arq = tmp_path / "indicadores.csv"
    with open(arq, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(CABECALHO)
        w.writerows(linhas)
    monkeypatch.setenv("INDICADORES_CSV", str(arq))
    monkeypatch.setenv("DATABASE_URL", "postgresql://radar:radar@127.0.0.1:1/radar")  # porta sem banco
    return arq


def test_sem_banco_usa_o_csv_e_calcula_os_totais(csv_pequeno):
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert any("Dados exportados" in i.value for i in at.info)  # avisa que não é ao vivo
    saldo = {m.label: m.value for m in at.metric}
    assert saldo["Saldo de empregos"] == "+20"  # 10 + 10, último mês (202511)
    assert saldo["Admissões"] == "150"


def test_mes_anterior_aparece_como_comparacao(csv_pequeno):
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    saldo = next(m for m in at.metric if m.label == "Saldo de empregos")
    # out/2025: 40 + (-20) = 20; nov/2025: 10 + 10 = 20, logo a variação é zero
    assert saldo.delta == "+0 vs 10/2025"


def test_csv_real_do_repositorio_carrega(monkeypatch):
    monkeypatch.delenv("INDICADORES_CSV", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://radar:radar@127.0.0.1:1/radar")
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert len(at.selectbox[0].options) == 12  # os 12 meses
