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
    assert any("pré-calculados" in c.value for c in at.caption)  # avisa que não é ao vivo
    manchete = next(m.value for m in at.markdown if m.value.startswith("### "))
    assert "novembro de 2025" in manchete and "20 empregos formais a mais do que fechou" in manchete
    assert "o mesmo resultado de outubro de 2025" in manchete  # nov e out somam +20
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
    setores = at.multiselect[1].options
    assert "Comércio" in setores and not any("Reparação" in s for s in setores)  # nomes curtos
    manchete = next(m.value for m in at.markdown if m.value.startswith("### "))
    # o número oficial do Ministério para set/2026 é +121.305 (conferido), 44.522 a menos que ago/2026
    assert "setembro de 2026" in manchete and "121.305 empregos formais a mais do que fechou" in manchete
    assert "44.522 a menos que em agosto de 2026" in manchete
    estados = at.multiselect[0].options
    assert "Minas Gerais" in estados and "Minas gerais" not in estados  # grafia corrigida
    assert any("dados até setembro de 2026" in c.value for c in at.caption)


def test_manchete_nomeia_o_estado_quando_ha_um_so_filtro(csv_pequeno):
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.multiselect[0].select("Bahia").run()
    manchete = next(m.value for m in at.markdown if m.value.startswith("### "))
    assert "Bahia" in manchete and "recorte escolhido" not in manchete
    assert "10 empregos formais a mais do que fechou" in manchete  # Bahia em nov/2025: 60 - 50
