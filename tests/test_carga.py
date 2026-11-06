import shutil
from pathlib import Path

import pytest

from pipeline.carga import carregar_arquivo
from pipeline.dimensoes import carregar_dimensoes

RAIZ = Path(__file__).resolve().parent.parent
LAYOUT = RAIZ / "data" / "raw" / "layout.xlsx"
EXTRAIDO = RAIZ / "data" / "extracted" / "CAGEDMOV202510.txt"

pytestmark = pytest.mark.skipif(not LAYOUT.exists(), reason="dados em data/ não baixados")


@pytest.fixture()
def amostra(tmp_path):
    """Primeiras 1.000 linhas de dados do arquivo real, com 2 linhas idênticas de propósito."""
    destino = tmp_path / "CAGEDMOV202510.txt"
    with open(EXTRAIDO, encoding="utf-8") as f:
        linhas = [next(f) for _ in range(1001)]
    linhas.append(linhas[-1])  # duplicata exata: deve ser mantida
    destino.write_text("".join(linhas), encoding="utf-8")
    return destino


@pytest.fixture()
def banco(conn):
    carregar_dimensoes(conn, LAYOUT)
    return conn


def contar(conn):
    return conn.execute("SELECT count(*) FROM movimentacao").fetchone()[0]


def test_carrega_e_mantem_linhas_identicas(banco, amostra):
    assert carregar_arquivo(banco, amostra) == "carregado"
    assert contar(banco) == 1001


def test_rodar_duas_vezes_nao_duplica(banco, amostra):
    carregar_arquivo(banco, amostra)
    assert carregar_arquivo(banco, amostra) == "pulado"
    assert contar(banco) == 1001


def test_arquivo_republicado_substitui_sem_duplicar(banco, amostra):
    carregar_arquivo(banco, amostra)
    texto = amostra.read_text(encoding="utf-8").splitlines(keepends=True)
    amostra.write_text("".join(texto[:501]), encoding="utf-8")  # governo republicou menor
    assert carregar_arquivo(banco, amostra) == "atualizado"
    assert contar(banco) == 500


def test_falha_no_meio_nao_deixa_carga_pela_metade(banco, amostra):
    texto = amostra.read_text(encoding="utf-8").splitlines(keepends=True)
    texto[600] = texto[600].replace(";", ";XX;", 1)  # linha corrompida
    amostra.write_text("".join(texto), encoding="utf-8")
    with pytest.raises(Exception):
        carregar_arquivo(banco, amostra)
    assert contar(banco) == 0
    assert banco.execute("SELECT count(*) FROM carga_arquivo").fetchone()[0] == 0


def test_codigo_fora_da_dimensao_aborta_a_carga(banco, amostra):
    texto = amostra.read_text(encoding="utf-8").splitlines(keepends=True)
    cab = texto[0].strip().split(";")
    linha = texto[10].strip().split(";")
    linha[cab.index("uf")] = "77"  # UF que não existe no dicionário
    texto[10] = ";".join(linha) + chr(10)
    amostra.write_text("".join(texto), encoding="utf-8")
    with pytest.raises(ValueError, match="uf"):
        carregar_arquivo(banco, amostra)
    assert contar(banco) == 0
    assert banco.execute("SELECT count(*) FROM carga_arquivo").fetchone()[0] == 0


def test_salario_absurdo_vira_null_e_a_linha_e_mantida(banco, amostra):
    """Regressão: um salário de 7,05e+10 (erro da fonte) derrubava a carga inteira."""
    texto = amostra.read_text(encoding="utf-8").splitlines(keepends=True)
    cab = texto[0].strip().split(";")
    linha = texto[10].strip().split(";")
    linha[cab.index("salário")] = "7,05e+10"
    texto[10] = ";".join(linha) + chr(10)
    amostra.write_text("".join(texto), encoding="utf-8")
    assert carregar_arquivo(banco, amostra) == "carregado"
    assert contar(banco) == 1001  # nenhuma linha perdida
    assert banco.execute("SELECT count(*) FROM movimentacao WHERE salario IS NULL").fetchone()[0] >= 1
